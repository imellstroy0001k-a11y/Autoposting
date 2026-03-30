from __future__ import annotations

import tomllib
from pathlib import Path

from .models import AccountConfig, AppConfig, AppSettings


def _resolve_path(base_dir: Path, raw: str | None, default: str | None = None) -> Path:
    value = raw or default
    if value is None:
        raise ValueError("Path value is required")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def load_config(config_path: str | Path) -> AppConfig:
    path = Path(config_path).expanduser().resolve()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    base_dir = path.parent

    app_section = data.get("app", {})
    settings = AppSettings(
        state_db=_resolve_path(base_dir, app_section.get("state_db"), "./state.sqlite3"),
        poll_seconds=int(app_section.get("poll_seconds", 60)),
        default_interval_hours=int(app_section.get("default_interval_hours", 4)),
        dedupe_scope=app_section.get("dedupe_scope", "global"),
        video_dir=_resolve_path(base_dir, app_section.get("video_dir"), "./videos"),
        supported_extensions=tuple(app_section.get("supported_extensions", [".mp4", ".mov", ".m4v", ".webm"])),
    )

    accounts: list[AccountConfig] = []
    for raw_account in data.get("accounts", []):
        account_id = str(raw_account["id"])
        platform = raw_account["platform"]
        interval_hours = int(raw_account.get("interval_hours", settings.default_interval_hours))
        video_dir = _resolve_path(
            base_dir,
            raw_account.get("video_dir"),
            str(settings.video_dir),
        )
        account = AccountConfig(
            id=account_id,
            platform=platform,
            enabled=bool(raw_account.get("enabled", True)),
            video_dir=video_dir,
            interval_hours=interval_hours,
            title_template=str(raw_account.get("title_template", "{stem}")),
            description_template=str(raw_account.get("description_template", "{description}")),
            tags=list(raw_account.get("tags", [])),
            youtube_category_id=str(raw_account.get("youtube_category_id", "22")),
            youtube_privacy_status=str(raw_account.get("youtube_privacy_status", "private")),
            youtube_client_id=raw_account.get("youtube_client_id"),
            youtube_client_secret=raw_account.get("youtube_client_secret"),
            youtube_refresh_token=raw_account.get("youtube_refresh_token"),
            tiktok_client_key=raw_account.get("tiktok_client_key"),
            tiktok_client_secret=raw_account.get("tiktok_client_secret"),
            tiktok_access_token=raw_account.get("tiktok_access_token"),
            tiktok_refresh_token=raw_account.get("tiktok_refresh_token"),
            tiktok_token_file=(
                _resolve_path(base_dir, raw_account.get("tiktok_token_file"))
                if raw_account.get("tiktok_token_file")
                else None
            ),
            tiktok_privacy_level=str(raw_account.get("tiktok_privacy_level", "SELF_ONLY")),
            tiktok_disable_comment=bool(raw_account.get("tiktok_disable_comment", False)),
            tiktok_disable_duet=bool(raw_account.get("tiktok_disable_duet", False)),
            tiktok_disable_stitch=bool(raw_account.get("tiktok_disable_stitch", False)),
            extra={
                key: value
                for key, value in raw_account.items()
                if key
                not in {
                    "id",
                    "platform",
                    "enabled",
                    "video_dir",
                    "interval_hours",
                    "title_template",
                    "description_template",
                    "tags",
                    "youtube_category_id",
                    "youtube_privacy_status",
                    "youtube_client_id",
                    "youtube_client_secret",
                    "youtube_refresh_token",
                    "tiktok_client_key",
                    "tiktok_client_secret",
                    "tiktok_access_token",
                    "tiktok_refresh_token",
                    "tiktok_token_file",
                    "tiktok_privacy_level",
                    "tiktok_disable_comment",
                    "tiktok_disable_duet",
                    "tiktok_disable_stitch",
                }
            },
        )
        accounts.append(account)

    if not accounts:
        raise ValueError("Config must contain at least one [[accounts]] entry")

    return AppConfig(settings=settings, accounts=accounts)
