from __future__ import annotations

import argparse
import json
from urllib.parse import urlencode

import requests

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Helpers for TikTok OAuth setup")
    subparsers = parser.add_subparsers(dest="command", required=True)

    auth_parser = subparsers.add_parser("auth-url", help="Build TikTok authorization URL")
    auth_parser.add_argument("--client-key", required=True)
    auth_parser.add_argument("--redirect-uri", required=True)
    auth_parser.add_argument("--scope", default="video.publish,user.info.basic")
    auth_parser.add_argument("--state", default="social-video-poster")

    exchange_parser = subparsers.add_parser("exchange-code", help="Exchange TikTok auth code for tokens")
    exchange_parser.add_argument("--client-key", required=True)
    exchange_parser.add_argument("--client-secret", required=True)
    exchange_parser.add_argument("--redirect-uri", required=True)
    exchange_parser.add_argument("--code", required=True)

    refresh_parser = subparsers.add_parser("refresh-token", help="Refresh TikTok access token")
    refresh_parser.add_argument("--client-key", required=True)
    refresh_parser.add_argument("--client-secret", required=True)
    refresh_parser.add_argument("--refresh-token", required=True)

    return parser


def build_auth_url(client_key: str, redirect_uri: str, scope: str, state: str) -> str:
    query = urlencode(
        {
            "client_key": client_key,
            "response_type": "code",
            "scope": scope,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"{AUTH_URL}?{query}"


def exchange_code(client_key: str, client_secret: str, redirect_uri: str, code: str) -> dict:
    response = requests.post(
        TOKEN_URL,
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def refresh_token(client_key: str, client_secret: str, refresh_token_value: str) -> dict:
    response = requests.post(
        TOKEN_URL,
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token_value,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "auth-url":
        print(build_auth_url(args.client_key, args.redirect_uri, args.scope, args.state))
        return

    if args.command == "exchange-code":
        print(
            json.dumps(
                exchange_code(
                    client_key=args.client_key,
                    client_secret=args.client_secret,
                    redirect_uri=args.redirect_uri,
                    code=args.code,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "refresh-token":
        print(
            json.dumps(
                refresh_token(
                    client_key=args.client_key,
                    client_secret=args.client_secret,
                    refresh_token_value=args.refresh_token,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
