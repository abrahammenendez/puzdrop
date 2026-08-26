"""Deliver the day's puzzle to Telegram and print the run summary."""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date
from pathlib import Path

TELEGRAM_API = "https://api.telegram.org"
REQUEST_TIMEOUT_SECONDS = 30


class DeliveryError(RuntimeError):
    """Telegram would not take the file."""


def message(day: date) -> str:
    """The one line both WhatsApp and Telegram get."""
    return f"🤖 Crucigrama del {day:%d/%m/%Y}"


def whatsapp_link(text: str) -> str:
    return "https://wa.me/?text=" + urllib.parse.quote(text, safe="")


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


def _refusal(error: urllib.error.HTTPError) -> str:
    """Telegram explains refusals in the body, and never echoes the token."""
    try:
        detail = json.loads(error.read()).get("description", "no detail")
    except (ValueError, OSError):
        detail = "no detail"
    return f"telegram refused the upload (HTTP {error.code}: {detail})"


def send_to_telegram(path: Path, caption: str, token: str, chat_id: str) -> None:
    """Upload one puzzle to a chat.

    The bot token is part of the request URL, so failures are re-raised
    without it, the same way fetch.py handles the source URL.
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
        raise DeliveryError(
            f"telegram refused the upload ({answer.get('description')})"
        )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True, help="the .puz to send")
    parser.add_argument(
        "--date", type=date.fromisoformat, required=True, help="the day it is for"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    text = message(args.date)

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    delivered = True
    if not (token and chat_id):
        status = "Telegram is not configured, so the artifact is the only copy."
    else:
        try:
            send_to_telegram(args.file, text, token, chat_id)
        except DeliveryError as error:
            delivered = False
            status = f"Telegram delivery failed: {error}"
        else:
            status = f"Sent to Telegram as `{args.file.name}`."

    print(f"## {args.date}")
    print()
    print(status)
    print()
    print(f"[Open WhatsApp with the message ready]({whatsapp_link(text)})")

    return 0 if delivered else 1


if __name__ == "__main__":
    sys.exit(main())
