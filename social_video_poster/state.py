from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .models import AccountConfig, DedupeScope, VideoAsset


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StateStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    video_hash TEXT NOT NULL,
                    video_path TEXT NOT NULL,
                    external_id TEXT,
                    published_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS account_runs (
                    account_id TEXT PRIMARY KEY,
                    last_success_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS account_tokens (
                    account_id TEXT PRIMARY KEY,
                    token_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def get_last_success_at(self, account_id: str) -> datetime | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT last_success_at FROM account_runs WHERE account_id = ?",
                (account_id,),
            ).fetchone()
        if not row:
            return None
        return datetime.fromisoformat(row["last_success_at"])

    def mark_upload(self, account: AccountConfig, asset: VideoAsset, external_id: str | None) -> None:
        now = utc_now().isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO uploads (account_id, platform, video_hash, video_path, external_id, published_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (account.id, account.platform, asset.sha256, str(asset.path), external_id, now),
            )
            conn.execute(
                """
                INSERT INTO account_runs (account_id, last_success_at)
                VALUES (?, ?)
                ON CONFLICT(account_id) DO UPDATE SET last_success_at = excluded.last_success_at
                """,
                (account.id, now),
            )

    def is_video_used(self, asset: VideoAsset, account: AccountConfig, scope: DedupeScope) -> bool:
        query = "SELECT 1 FROM uploads WHERE video_hash = ?"
        params: list[str] = [asset.sha256]
        if scope == "platform":
            query += " AND platform = ?"
            params.append(account.platform)
        elif scope == "account":
            query += " AND account_id = ?"
            params.append(account.id)
        query += " LIMIT 1"
        with self.connection() as conn:
            row = conn.execute(query, params).fetchone()
        return row is not None

    def load_tokens(self, account_id: str) -> dict[str, str] | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT token_json FROM account_tokens WHERE account_id = ?",
                (account_id,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["token_json"])

    def save_tokens(self, account_id: str, token_payload: dict[str, str]) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO account_tokens (account_id, token_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(account_id) DO UPDATE SET
                    token_json = excluded.token_json,
                    updated_at = excluded.updated_at
                """,
                (account_id, json.dumps(token_payload), utc_now().isoformat()),
            )
