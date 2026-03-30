from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..models import AccountConfig, VideoAsset
from ..state import StateStore


@dataclass(slots=True)
class PublishResult:
    external_id: str | None
    public_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class Publisher(Protocol):
    def publish(self, account: AccountConfig, asset: VideoAsset, state: StateStore) -> PublishResult:
        ...


def render_text(template: str, account: AccountConfig, asset: VideoAsset, fallback: str) -> str:
    context = {
        "account_id": account.id,
        "platform": account.platform,
        "filename": asset.path.name,
        "stem": asset.stem,
        "title": asset.title,
        "description": asset.description,
    }
    try:
        rendered = template.format(**context).strip()
    except Exception:
        rendered = fallback
    return rendered or fallback
