import json
import traceback
import urllib.error
import urllib.request
from datetime import UTC, datetime
from io import BytesIO

import puz
import pytest

import fetch
from fetch import Config, ConfigurationError, FetchError, NotPublishedError

# .invalid is reserved, so any hostname that leaks into a message came from here.
HOST = "api.invalid"
ORIGIN = "https://site.invalid"
TEMPLATE = f"https://{HOST}/puzzles/{{date}}"
DATE = "2026-08-25"
TITLE = "Crucigrama"


class _Urlopen:
    """Stands in for urlopen and records every request it gets."""

    def __init__(self, body):
        self.body = body
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        return BytesIO(self.body)


def _failing(error):
    def stub(request, timeout):
        raise error

    return stub


def _http_error(code):
    return urllib.error.HTTPError(TEMPLATE.format(date=DATE), code, "", {}, None)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("PUZZLE_API_URL_TEMPLATE", TEMPLATE)
    monkeypatch.setenv("PUZZLE_API_ORIGIN", ORIGIN)
    monkeypatch.setenv("PUZZLE_TITLE", TITLE)


def test_the_request_substitutes_the_date_and_sends_the_origin(monkeypatch):
    urlopen = _Urlopen(b'{"ok": true}')
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)

    assert fetch.fetch(DATE, TEMPLATE, ORIGIN) == {"ok": True}

    (request,) = urlopen.requests
    assert request.full_url == f"https://{HOST}/puzzles/{DATE}"
    assert request.get_header("Origin") == ORIGIN


def test_a_missing_day_is_reported_as_not_yet_published(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _failing(_http_error(404)))

    with pytest.raises(NotPublishedError, match="no puzzle published for 2026-08-25"):
        fetch.fetch(DATE, TEMPLATE, ORIGIN)


def test_other_http_failures_report_only_the_status_code(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _failing(_http_error(503)))

    with pytest.raises(FetchError, match="HTTP 503") as raised:
        fetch.fetch(DATE, TEMPLATE, ORIGIN)

    assert not isinstance(raised.value, NotPublishedError)


@pytest.mark.parametrize(
    "failure",
    [
        _http_error(404),
        _http_error(503),
        urllib.error.URLError(f"certificate is not valid for '{HOST}'"),
        TimeoutError(f"timed out reading from {HOST}"),
    ],
)
def test_no_failure_leaks_the_url_or_the_origin(monkeypatch, failure):
    monkeypatch.setattr(urllib.request, "urlopen", _failing(failure))

    with pytest.raises(FetchError) as raised:
        fetch.fetch(DATE, TEMPLATE, ORIGIN)

    report = "".join(traceback.format_exception(raised.value))
    assert HOST not in report
    assert ORIGIN not in report


def test_a_non_json_response_is_rejected(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _Urlopen(b"<html>nope</html>"))

    with pytest.raises(FetchError, match="was not JSON"):
        fetch.fetch(DATE, TEMPLATE, ORIGIN)


class _FrozenClock:
    """Late evening UTC, when Madrid has already rolled over to the next day."""

    @staticmethod
    def now(tz):
        return datetime(2026, 8, 25, 23, 30, tzinfo=UTC).astimezone(tz)


def test_the_default_date_is_the_current_day_in_madrid(monkeypatch):
    monkeypatch.setattr(fetch, "datetime", _FrozenClock)

    assert fetch.default_date() == "2026-08-26"


def test_a_malformed_date_is_rejected_before_any_request(monkeypatch, configured):
    monkeypatch.setattr(
        urllib.request, "urlopen", _failing(AssertionError("no request expected"))
    )

    with pytest.raises(SystemExit) as raised:
        fetch.main(["--date", "25-08-2026"])

    assert raised.value.code == 2


def test_a_missing_variable_is_named_without_revealing_the_others(
    monkeypatch, configured
):
    monkeypatch.delenv("PUZZLE_TITLE")

    with pytest.raises(ConfigurationError) as raised:
        Config.from_env()

    assert str(raised.value) == "PUZZLE_TITLE is not set"


def test_a_template_without_the_date_placeholder_is_rejected(monkeypatch, configured):
    monkeypatch.setenv("PUZZLE_API_URL_TEMPLATE", f"https://{HOST}/puzzles/latest")

    with pytest.raises(ConfigurationError, match="placeholder"):
        Config.from_env()


def test_a_generated_file_is_named_after_the_date_and_reads_back(
    monkeypatch, configured, capsys, tmp_path, simple_payload
):
    body = json.dumps(simple_payload).encode()
    monkeypatch.setattr(urllib.request, "urlopen", _Urlopen(body))

    assert fetch.main(["--date", DATE, "--output", str(tmp_path)]) == 0

    path = tmp_path / f"{DATE}.puz"
    assert puz.read(str(path)).title == f"{TITLE} - {DATE}"
    assert capsys.readouterr().out.strip() == str(path)


def test_an_unpublished_day_exits_non_zero_with_a_plain_message(
    monkeypatch, configured, capsys, tmp_path
):
    monkeypatch.setattr(urllib.request, "urlopen", _failing(_http_error(404)))

    assert fetch.main(["--date", DATE, "--output", str(tmp_path)]) == 1

    captured = capsys.readouterr()
    assert captured.err.strip() == f"error: no puzzle published for {DATE}"
    assert not list(tmp_path.iterdir())
