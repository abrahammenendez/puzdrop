"""Deliver the day's puzzle to Telegram and report the outcome."""

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from env import optional

TELEGRAM_API = "https://api.telegram.org"
REQUEST_TIMEOUT_SECONDS = 30


class DeliveryError(RuntimeError):
    """Telegram would not take the file."""


def message(day: date) -> str:
    """The caption Telegram gets."""
    return f"🤖 Crucigrama del {day:%d/%m/%Y}"


def _multipart(fields: dict[str, str], name: str, document: bytes) -> tuple[str, bytes]:
    boundary = uuid.uuid4().hex
    body = bytearray()
    for field, value in fields.items():
        body += (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field}"\r\n\r\n'
            f"{value}\r\n"
        ).encode()
    body += (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="document"; filename="{name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    body += document
    body += f"\r\n--{boundary}--\r\n".encode()
    return f"multipart/form-data; boundary={boundary}", bytes(body)


def _description(answer: dict[str, Any]) -> str:
    """The reason Telegram gives for a refusal, which it can also omit."""
    return answer.get("description") or "no detail"


def _refusal(error: urllib.error.HTTPError) -> str:
    """Turn a Telegram HTTPError into the reason it carries in its body."""
    try:
        detail = _description(json.loads(error.read()))
    except (ValueError, OSError):
        detail = "no detail"
    return f"telegram refused the upload (HTTP {error.code}: {detail})"


def send_to_telegram(path: Path, caption: str, token: str, chat_id: str) -> None:
    """Upload one puzzle to a chat.

    The bot token sits in the request URL, so failures are re-raised without it.
    """
    content_type, body = _multipart(
        {"chat_id": chat_id, "caption": caption},
        path.name,
        path.read_bytes(),
    )
    request = urllib.request.Request(
        f"{TELEGRAM_API}/bot{token}/sendDocument",
        data=body,
        headers={"Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(
            request, timeout=REQUEST_TIMEOUT_SECONDS
        ) as response:
            answer = json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise DeliveryError(_refusal(error)) from None
    except OSError as error:
        raise DeliveryError(
            f"telegram upload failed ({type(error).__name__})"
        ) from None

    if not answer.get("ok"):
        raise DeliveryError(f"telegram refused the upload ({_description(answer)})")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True, help="the .puz to send")
    parser.add_argument(
        "--date", type=date.fromisoformat, required=True, help="the day it is for"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    caption = message(args.date)

    token = optional("TELEGRAM_BOT_TOKEN")
    chat_id = optional("TELEGRAM_CHAT_ID")

    delivered = True
    if not (token and chat_id):
        status = "⏭️ Telegram is not configured; nothing was sent."
    else:
        try:
            send_to_telegram(args.file, caption, token, chat_id)
        except DeliveryError as error:
            delivered = False
            status = f"❌ Telegram delivery failed: {error}"
        else:
            status = f"✅ Sent {args.file.name} to Telegram."

    print(status)

    return 0 if delivered else 1


if __name__ == "__main__":
    sys.exit(main())
