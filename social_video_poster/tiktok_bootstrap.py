from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"


@dataclass
class CallbackPayload:
    code: str | None = None
    state: str | None = None
    error: str | None = None
    error_description: str | None = None


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


class _CallbackHandler(BaseHTTPRequestHandler):
    payload = CallbackPayload()
    event = threading.Event()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        self.__class__.payload = CallbackPayload(
            code=_first(params.get("code")),
            state=_first(params.get("state")),
            error=_first(params.get("error")),
            error_description=_first(params.get("error_description")),
        )

        if self.__class__.payload.error:
            body = (
                "<html><body><h1>TikTok authorization failed</h1>"
                f"<p>{self.__class__.payload.error}</p>"
                f"<p>{self.__class__.payload.error_description or ''}</p>"
                "</body></html>"
            )
        else:
            body = (
                "<html><body><h1>TikTok authorization received</h1>"
                "<p>You can close this tab and return to the terminal.</p>"
                "</body></html>"
            )

        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
        self.__class__.event.set()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def _first(values: list[str] | None) -> str | None:
    if not values:
        return None
    return values[0]


def _save_token_file(output_dir: Path, account_id: str, payload: dict) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{account_id}.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local TikTok OAuth bootstrap for desktop usage")
    parser.add_argument("--client-key", required=True)
    parser.add_argument("--client-secret", required=True)
    parser.add_argument("--account-id", required=True, help="Friendly account label, for example tiktok_1")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--callback-path", default="/callback/")
    parser.add_argument("--scope", default="video.publish,user.info.basic")
    parser.add_argument("--output-dir", default="runtime/tiktok_tokens")
    parser.add_argument("--state", default=None)
    parser.add_argument("--no-open", action="store_true", help="Do not auto-open browser")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    state = args.state or args.account_id
    redirect_uri = f"http://{args.host}:{args.port}{args.callback_path}"
    auth_url = build_auth_url(args.client_key, redirect_uri, args.scope, state)

    _CallbackHandler.payload = CallbackPayload()
    _CallbackHandler.event = threading.Event()

    server = HTTPServer((args.host, args.port), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    print("Register this redirect URI in TikTok Login Kit before continuing:")
    print(redirect_uri)
    print()
    print("Open this URL and authorize the target TikTok account:")
    print(auth_url)
    print()

    if not args.no_open:
        webbrowser.open(auth_url)

    thread.join(timeout=300)
    server.server_close()

    payload = _CallbackHandler.payload
    if not payload.code:
        if payload.error:
            raise SystemExit(
                f"TikTok authorization failed: {payload.error} {payload.error_description or ''}".strip()
            )
        raise SystemExit("Timed out waiting for TikTok callback")

    if payload.state != state:
        raise SystemExit(f"State mismatch: expected {state!r}, got {payload.state!r}")

    token_payload = exchange_code(
        client_key=args.client_key,
        client_secret=args.client_secret,
        redirect_uri=redirect_uri,
        code=payload.code,
    )
    output_path = _save_token_file(Path(args.output_dir), args.account_id, token_payload)
    print("Token payload saved to:")
    print(output_path.resolve())


if __name__ == "__main__":
    main()
