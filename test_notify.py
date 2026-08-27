import io
import json
import traceback
import urllib.error
import urllib.request
from datetime import date

import pytest

import notify
from notify import DeliveryError, message, send_to_telegram

TOKEN = "1234567:AAdummy-token-value"
CHAT_ID = "-1009876543210"
DAY = date(2026, 8, 26)


class _Urlopen:
    """Stands in for urlopen and records every request it gets."""

    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        return io.BytesIO(json.dumps(self.payload).encode())


def _failing(error):
    def stub(request, timeout):
        raise error

    return stub


def _http_error(code, description):
    body = io.BytesIO(json.dumps({"ok": False, "description": description}).encode())
    return urllib.error.HTTPError(
        f"{notify.TELEGRAM_API}/bot{TOKEN}/sendDocument", code, "", {}, body
    )


@pytest.fixture
def puzzle(tmp_path):
    path = tmp_path / "pfx-2026-08-26.puz"
    path.write_bytes(b"ACROSS&DOWN\x00binary")
    return path


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", CHAT_ID)


def test_the_message_is_a_spanish_date_with_the_robot():
    assert message(DAY) == "🤖 Crucigrama del 26/08/2026"


def test_the_upload_carries_the_file_the_caption_and_the_chat(monkeypatch, puzzle):
    urlopen = _Urlopen({"ok": True})
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)

    send_to_telegram(puzzle, message(DAY), TOKEN, CHAT_ID)

    (request,) = urlopen.requests
    assert request.full_url == f"{notify.TELEGRAM_API}/bot{TOKEN}/sendDocument"
    assert request.get_header("Content-type").startswith(
        "multipart/form-data; boundary="
    )

    body = request.data
    assert puzzle.read_bytes() in body
    assert b'filename="pfx-2026-08-26.puz"' in body
    assert CHAT_ID.encode() in body
    assert message(DAY).encode() in body


def test_a_refusal_reports_telegrams_own_description(monkeypatch, puzzle):
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        _failing(_http_error(400, "Bad Request: chat not found")),
    )

    with pytest.raises(DeliveryError, match="chat not found"):
        send_to_telegram(puzzle, "x", TOKEN, CHAT_ID)


def test_an_ok_false_body_is_still_a_failure(monkeypatch, puzzle):
    monkeypatch.setattr(
        urllib.request, "urlopen", _Urlopen({"ok": False, "description": "blocked"})
    )

    with pytest.raises(DeliveryError, match="blocked"):
        send_to_telegram(puzzle, "x", TOKEN, CHAT_ID)


def test_a_refusal_without_a_description_does_not_say_none(monkeypatch, puzzle):
    monkeypatch.setattr(urllib.request, "urlopen", _Urlopen({"ok": False}))

    with pytest.raises(DeliveryError, match=r"refused the upload \(no detail\)"):
        send_to_telegram(puzzle, "x", TOKEN, CHAT_ID)


def test_a_reply_that_is_not_json_is_a_delivery_failure(monkeypatch, puzzle):
    # A proxy or an outage page can answer 200 with HTML.
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout: io.BytesIO(b"<html>502 Bad Gateway</html>"),
    )

    with pytest.raises(DeliveryError, match="not JSON"):
        send_to_telegram(puzzle, "x", TOKEN, CHAT_ID)


@pytest.mark.parametrize(
    "failure",
    [
        _http_error(400, "Bad Request: chat not found"),
        _http_error(401, "Unauthorized"),
        # The token lives in the URL path, so a library that echoes the URL is
        # the failure this guards against.
        urllib.error.URLError(f"could not reach {notify.TELEGRAM_API}/bot{TOKEN}/x"),
        TimeoutError(f"timed out on /bot{TOKEN}/sendDocument"),
    ],
)
def test_no_failure_leaks_the_bot_token(monkeypatch, puzzle, failure):
    monkeypatch.setattr(urllib.request, "urlopen", _failing(failure))

    with pytest.raises(DeliveryError) as raised:
        send_to_telegram(puzzle, "x", TOKEN, CHAT_ID)

    assert TOKEN not in "".join(traceback.format_exception(raised.value))


def test_without_credentials_nothing_is_sent_and_the_run_still_passes(
    monkeypatch, capsys, puzzle
):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr(
        urllib.request, "urlopen", _failing(AssertionError("no request expected"))
    )

    assert notify.main(["--file", str(puzzle), "--date", "2026-08-26"]) == 0

    out = capsys.readouterr().out
    assert "not configured" in out


def test_a_delivered_puzzle_reports_success(monkeypatch, capsys, configured, puzzle):
    monkeypatch.setattr(urllib.request, "urlopen", _Urlopen({"ok": True}))

    assert notify.main(["--file", str(puzzle), "--date", "2026-08-26"]) == 0

    out = capsys.readouterr().out
    assert "Sent pfx-2026-08-26.puz to Telegram" in out


def test_a_failed_delivery_exits_non_zero_but_still_prints_the_summary(
    monkeypatch, capsys, configured, puzzle
):
    monkeypatch.setattr(
        urllib.request, "urlopen", _failing(_http_error(400, "chat not found"))
    )

    assert notify.main(["--file", str(puzzle), "--date", "2026-08-26"]) == 1

    out = capsys.readouterr().out
    assert "Telegram delivery failed" in out
    assert TOKEN not in out
