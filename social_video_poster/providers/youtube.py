from __future__ import annotations

from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from ..models import AccountConfig, VideoAsset
from ..state import StateStore
from .base import PublishResult, render_text

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_TOKEN_URI = "https://oauth2.googleapis.com/token"


class YouTubePublisher:
    def publish(self, account: AccountConfig, asset: VideoAsset, state: StateStore) -> PublishResult:
        if not account.youtube_client_id or not account.youtube_client_secret or not account.youtube_refresh_token:
            raise ValueError(f"YouTube credentials are incomplete for account {account.id}")

        credentials = Credentials(
            token=None,
            refresh_token=account.youtube_refresh_token,
            token_uri=YOUTUBE_TOKEN_URI,
            client_id=account.youtube_client_id,
            client_secret=account.youtube_client_secret,
            scopes=[YOUTUBE_UPLOAD_SCOPE],
        )
        youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
        title = render_text(account.title_template, account, asset, asset.title)[:100]
        description = render_text(account.description_template, account, asset, asset.description)[:5000]

        body: dict[str, Any] = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": (account.tags + asset.tags)[:500],
                "categoryId": account.youtube_category_id,
            },
            "status": {
                "privacyStatus": account.youtube_privacy_status,
            },
        }
        media = MediaFileUpload(str(asset.path), resumable=True)
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            try:
                _, response = request.next_chunk()
            except HttpError as exc:  # pragma: no cover - live API path
                raise RuntimeError(f"YouTube upload failed for {account.id}: {exc}") from exc

        video_id = response.get("id")
        return PublishResult(
            external_id=video_id,
            public_url=f"https://youtu.be/{video_id}" if video_id else None,
            raw=response,
        )
