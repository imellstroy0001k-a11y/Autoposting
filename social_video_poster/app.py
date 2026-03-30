from __future__ import annotations

import logging
import time
from datetime import timedelta

from .models import AccountConfig, AppConfig
from .providers import TikTokPublisher, YouTubePublisher
from .providers.base import PublishResult
from .state import StateStore, utc_now
from .video_store import VideoStore

logger = logging.getLogger(__name__)


class SocialVideoPosterApp:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.state = StateStore(config.settings.state_db)
        self.video_store = VideoStore(config.settings, self.state)
        self.publishers = {
            "youtube": YouTubePublisher(),
            "tiktok": TikTokPublisher(),
        }

    def account_is_due(self, account: AccountConfig) -> bool:
        if not account.enabled:
            return False
        last_success = self.state.get_last_success_at(account.id)
        if last_success is None:
            return True
        return utc_now() >= last_success + timedelta(hours=account.interval_hours)

    def publish_for_account(self, account: AccountConfig) -> PublishResult | None:
        asset = self.video_store.next_asset_for_account(account)
        if asset is None:
            logger.info("No fresh videos found for account=%s in %s", account.id, account.video_dir)
            return None

        logger.info("Publishing %s to account=%s platform=%s", asset.path.name, account.id, account.platform)
        publisher = self.publishers[account.platform]
        result = publisher.publish(account, asset, self.state)
        self.state.mark_upload(account, asset, result.external_id)
        logger.info(
            "Published %s to account=%s external_id=%s",
            asset.path.name,
            account.id,
            result.external_id,
        )
        return result

    def run_due_once(self) -> None:
        for account in self.config.accounts:
            if not self.account_is_due(account):
                continue
            try:
                self.publish_for_account(account)
            except Exception as exc:  # pragma: no cover - runtime integration path
                logger.exception("Failed publishing for account=%s: %s", account.id, exc)

    def list_pending(self) -> list[tuple[str, str | None]]:
        pending: list[tuple[str, str | None]] = []
        for account in self.config.accounts:
            asset = self.video_store.next_asset_for_account(account)
            pending.append((account.id, asset.path.name if asset else None))
        return pending

    def run_forever(self) -> None:
        logger.info("Scheduler started. Poll interval: %ss", self.config.settings.poll_seconds)
        while True:
            self.run_due_once()
            time.sleep(self.config.settings.poll_seconds)
