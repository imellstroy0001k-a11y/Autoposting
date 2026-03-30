from __future__ import annotations

import argparse
import logging

from .app import SocialVideoPosterApp
from .config import load_config


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default="config.toml", help="Path to TOML config file")
    common.add_argument("--log-level", default="INFO", help="Logging level")

    parser = argparse.ArgumentParser(
        description="Automatic video uploader for YouTube and TikTok",
        parents=[common],
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="Run forever and publish due videos every cycle", parents=[common])
    subparsers.add_parser("run-once", help="Run one scheduling pass", parents=[common])
    subparsers.add_parser("list-pending", help="Show which video would be picked for each account", parents=[common])
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    config = load_config(args.config)
    app = SocialVideoPosterApp(config)

    if args.command == "run":
        app.run_forever()
        return
    if args.command == "run-once":
        app.run_due_once()
        return
    if args.command == "list-pending":
        for account_id, candidate in app.list_pending():
            print(f"{account_id}: {candidate or 'NO_VIDEO'}")
        return

    parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
