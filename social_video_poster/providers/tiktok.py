from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from ..models import AccountConfig, VideoAsset
from ..state import StateStore
from .base import PublishResult, render_text

TIKTOK_API_BASE = "https://open.tiktokapis.com"
TIKTOK_OAUTH_TOKEN_URL = f"{TIKTOK_API_BASE}/v2/oauth/token/"
TIKTOK_CREATOR_INFO_URL = f"{TIKTOK_API_BASE}/v2/post/publish/creator_info/query/"
TIKTOK_VIDEO_INIT_URL = f"{TIKTOK_API_BASE}/v2/post/publish/video/init/"
DEFAULT_CHUNK_SIZE = 10 * 1024 * 1024
MIN_CHUNK_SIZE = 5 * 1024 * 1024


def _iso_utc_after(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _build_chunks(file_size: int) -> list[tuple[int, int]]:
    if file_size <= DEFAULT_CHUNK_SIZE:
        return [(0, file_size - 1)]

    chunks: list[tuple[int, int]] = []
    offset = 0
    while offset < file_size:
        next_offset = min(offset + DEFAULT_CHUNK_SIZE, file_size)
        chunks.append((offset, next_offset - 1))
        offset = next_offset

    if len(chunks) > 1:
        start, end = chunks[-1]
        if end - start + 1 < MIN_CHUNK_SIZE:
            prev_start, _ = chunks[-2]
            chunks[-2] = (prev_start, end)
            chunks.pop()
    return chunks


class TikTokPublisher:
    def __init__(self) -> None:
        self.session = requests.Session()

    def _load_token_file(self, account: AccountConfig) -> dict[str, str] | None:
        if not account.tiktok_token_file or not account.tiktok_token_file.exists():
            return None
        payload = json.loads(account.tiktok_token_file.read_text(encoding="utf-8"))
        return {
            "access_token": payload.get("access_token", ""),
            "refresh_token": payload.get("refresh_token", ""),
            "open_id": payload.get("open_id", ""),
            "expires_at": _iso_utc_after(int(payload.get("expires_in", 3600))),
        }

    def _load_token_bundle(self, account: AccountConfig, state: StateStore) -> dict[str, str]:
        return state.load_tokens(account.id) or self._load_token_file(account) or {
            "access_token": account.tiktok_access_token or "",
            "refresh_token": account.tiktok_refresh_token or "",
        }

    def _refresh_access_token(self, account: AccountConfig, state: StateStore) -> dict[str, str]:
        if not account.tiktok_client_key or not account.tiktok_client_secret:
            raise ValueError(f"TikTok client credentials are missing for account {account.id}")

        token_bundle = self._load_token_bundle(account, state)
        refresh_token = token_bundle.get("refresh_token") or account.tiktok_refresh_token
        access_token = token_bundle.get("access_token")
        expires_at = token_bundle.get("expires_at")
        now = datetime.now(timezone.utc)

        if access_token and expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at)
            except ValueError:
                expiry = now
            if expiry > now + timedelta(minutes=2):
                return token_bundle

        if not refresh_token:
            raise ValueError(f"TikTok refresh token is missing for account {account.id}")

        response = self.session.post(
            TIKTOK_OAUTH_TOKEN_URL,
            data={
                "client_key": account.tiktok_client_key,
                "client_secret": account.tiktok_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise RuntimeError(f"TikTok token refresh failed for {account.id}: {payload}")

        updated_bundle = {
            "access_token": access_token,
            "refresh_token": payload.get("refresh_token", refresh_token),
            "open_id": payload.get("open_id", token_bundle.get("open_id", "")),
            "expires_at": _iso_utc_after(int(payload.get("expires_in", 3600))),
        }
        state.save_tokens(account.id, updated_bundle)
        return updated_bundle

    def _query_creator_info(self, access_token: str) -> dict[str, Any]:
        response = self.session.post(
            TIKTOK_CREATOR_INFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", {})
        if not data:
            raise RuntimeError(f"TikTok creator info query failed: {payload}")
        return data

    def _resolve_privacy_level(self, account: AccountConfig, creator_info: dict[str, Any]) -> str:
        options = creator_info.get("privacy_level_options") or []
        if account.tiktok_privacy_level in options:
            return account.tiktok_privacy_level
        if options:
            return str(options[0])
        return account.tiktok_privacy_level

    def _init_upload(self, access_token: str, account: AccountConfig, asset: VideoAsset) -> dict[str, Any]:
        chunks = _build_chunks(asset.size_bytes)
        creator_info = self._query_creator_info(access_token)
        privacy_level = self._resolve_privacy_level(account, creator_info)
        title = render_text(account.title_template, account, asset, asset.title)[:150]
        post_info = {
            "title": title,
            "privacy_level": privacy_level,
            "disable_comment": account.tiktok_disable_comment,
            "disable_duet": account.tiktok_disable_duet,
            "disable_stitch": account.tiktok_disable_stitch,
        }
        source_info = {
            "source": "FILE_UPLOAD",
            "video_size": asset.size_bytes,
            "chunk_size": chunks[0][1] - chunks[0][0] + 1,
            "total_chunk_count": len(chunks),
        }
        response = self.session.post(
            TIKTOK_VIDEO_INIT_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            json={"post_info": post_info, "source_info": source_info},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", {})
        upload_url = data.get("upload_url")
        if not upload_url:
            raise RuntimeError(f"TikTok upload init failed: {payload}")
        data["_chunks"] = chunks
        return data

    def _upload_binary(self, upload_url: str, path: Path, chunks: list[tuple[int, int]]) -> None:
        with path.open("rb") as fh:
            total = path.stat().st_size
            for start, end in chunks:
                fh.seek(start)
                body = fh.read(end - start + 1)
                response = self.session.put(
                    upload_url,
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Length": str(len(body)),
                        "Content-Range": f"bytes {start}-{end}/{total}",
                    },
                    data=body,
                    timeout=300,
                )
                response.raise_for_status()

    def publish(self, account: AccountConfig, asset: VideoAsset, state: StateStore) -> PublishResult:
        token_bundle = self._refresh_access_token(account, state)
        access_token = token_bundle["access_token"]
        init_payload = self._init_upload(access_token, account, asset)
        upload_url = init_payload["upload_url"]
        chunks = init_payload.pop("_chunks")
        self._upload_binary(upload_url, asset.path, chunks)
        publish_id = init_payload.get("publish_id") or init_payload.get("share_id")
        return PublishResult(
            external_id=publish_id,
            raw=init_payload,
        )
