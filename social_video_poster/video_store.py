from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import AccountConfig, AppSettings, VideoAsset
from .state import StateStore


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_sidecar_text(path: Path) -> str:
    sidecar = path.with_suffix(".txt")
    if not sidecar.exists():
        return ""
    return sidecar.read_text(encoding="utf-8").strip()


def _read_sidecar_json(path: Path) -> dict:
    sidecar = path.with_suffix(".json")
    if not sidecar.exists():
        return {}
    return json.loads(sidecar.read_text(encoding="utf-8"))


def _build_asset(path: Path) -> VideoAsset:
    metadata = _read_sidecar_json(path)
    sidecar_text = _read_sidecar_text(path)
    title = str(metadata.get("title") or path.stem.replace("_", " ").strip())
    description = str(metadata.get("description") or sidecar_text)
    tags = list(metadata.get("tags") or [])
    return VideoAsset(
        path=path,
        sha256=sha256_file(path),
        title=title,
        description=description,
        tags=tags,
        metadata=metadata,
    )


class VideoStore:
    def __init__(self, settings: AppSettings, state: StateStore) -> None:
        self.settings = settings
        self.state = state

    def list_candidates(self, account: AccountConfig) -> list[Path]:
        video_dir = account.video_dir
        video_dir.mkdir(parents=True, exist_ok=True)
        files = [
            path
            for path in video_dir.iterdir()
            if path.is_file() and path.suffix.lower() in self.settings.supported_extensions
        ]
        files.sort(key=lambda item: (item.stat().st_mtime, item.name))
        return files

    def next_asset_for_account(self, account: AccountConfig) -> VideoAsset | None:
        for path in self.list_candidates(account):
            asset = _build_asset(path)
            if self.state.is_video_used(asset, account, self.settings.dedupe_scope):
                continue
            return asset
        return None
