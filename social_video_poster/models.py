from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Platform = Literal["youtube", "tiktok"]
DedupeScope = Literal["global", "platform", "account"]


@dataclass(slots=True)
class AppSettings:
    state_db: Path
    poll_seconds: int = 60
    default_interval_hours: int = 4
    dedupe_scope: DedupeScope = "global"
    video_dir: Path = Path("videos")
    supported_extensions: tuple[str, ...] = (".mp4", ".mov", ".m4v", ".webm")


@dataclass(slots=True)
class AccountConfig:
    id: str
    platform: Platform
    enabled: bool
    video_dir: Path
    interval_hours: int
    title_template: str = "{stem}"
    description_template: str = "{description}"
    tags: list[str] = field(default_factory=list)
    youtube_category_id: str = "22"
    youtube_privacy_status: str = "private"
    youtube_client_id: str | None = None
    youtube_client_secret: str | None = None
    youtube_refresh_token: str | None = None
    tiktok_client_key: str | None = None
    tiktok_client_secret: str | None = None
    tiktok_access_token: str | None = None
    tiktok_refresh_token: str | None = None
    tiktok_token_file: Path | None = None
    tiktok_privacy_level: str = "SELF_ONLY"
    tiktok_disable_comment: bool = False
    tiktok_disable_duet: bool = False
    tiktok_disable_stitch: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AppConfig:
    settings: AppSettings
    accounts: list[AccountConfig]


@dataclass(slots=True)
class VideoAsset:
    path: Path
    sha256: str
    title: str
    description: str
    tags: list[str]
    metadata: dict[str, Any]

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def size_bytes(self) -> int:
        return self.path.stat().st_size
