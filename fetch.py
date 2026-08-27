"""Fetch one day's crossword and write it as an Across Lite (.puz) file."""

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Self
from zoneinfo import ZoneInfo

import puz

from convert import SourcePayloadError, build_puzzle, validate
from env import ConfigurationError, optional, required

# The source publishes on Spanish calendar days, so neither UTC nor whatever
# clock the runner happens to have gives the right answer for "today".
PUBLICATION_TIMEZONE = ZoneInfo("Europe/Madrid")

DEFAULT_OUTPUT = Path("output")
REQUEST_TIMEOUT_SECONDS = 15

# This endpoint feeds a browser widget and already checks Origin, so send the
# browser User-Agent it expects rather than a Python one.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36"
)


class FetchError(RuntimeError):
    """The request failed."""


class OutputError(RuntimeError):
    """Saving worked, but the file does not read back as a valid .puz."""


@dataclass(frozen=True)
class Config:
    api_url_template: str
    api_origin: str
    title: str
    file_prefix: str

    @classmethod
    def from_env(cls) -> Self:
        config = cls(
            api_url_template=required("PUZZLE_API_URL_TEMPLATE"),
            api_origin=required("PUZZLE_API_ORIGIN"),
            title=required("PUZZLE_TITLE"),
            file_prefix=optional("PUZZLE_FILE_PREFIX"),
        )
        # Without the placeholder every run would silently fetch the same day.
        if "{date}" not in config.api_url_template:
            raise ConfigurationError(
                "PUZZLE_API_URL_TEMPLATE has no {date} placeholder"
            )
        return config


def filename(day: str, prefix: str) -> str:
    return f"{prefix}-{day}.puz" if prefix else f"{day}.puz"


def fetch(day: str, api_url_template: str, api_origin: str) -> dict[str, Any]:
    """Request the payload for one date.

    Failures are re-raised without the URL or Origin header and with no chained
    context, so the endpoint stays out of tracebacks.
    """
    request = urllib.request.Request(
        api_url_template.format(date=day),
        headers={"Origin": api_origin, "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(
            request, timeout=REQUEST_TIMEOUT_SECONDS
        ) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise FetchError(f"no puzzle published for {day}") from None
        raise FetchError(f"request for {day} failed with HTTP {error.code}") from None
    except OSError as error:
        raise FetchError(f"request for {day} failed ({type(error).__name__})") from None

    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise FetchError(f"response for {day} was not JSON") from None


def save(puzzle: puz.Puzzle, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    puzzle.save(str(path))

    # Reading it back is the only thing that proves the checksums. save()
    # returning without raising proves nothing.
    try:
        puz.read(str(path))
    except puz.PuzzleFormatError as error:
        # PuzzleFormatError never hands its text to Exception, so str() is empty.
        raise OutputError(error.message or "checksums do not validate") from None


def default_date() -> str:
    return datetime.now(PUBLICATION_TIMEZONE).date().isoformat()


def _date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected YYYY-MM-DD, got {value!r}"
        ) from None


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        type=_date,
        default=None,
        help="day to fetch, as YYYY-MM-DD (default: today in Europe/Madrid)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"directory to write the .puz into (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    day = args.date or default_date()

    try:
        config = Config.from_env()
        payload = fetch(day, config.api_url_template, config.api_origin)
        puzzle = build_puzzle(payload, day, config.title)
        validate(puzzle)
        path = args.output / filename(day, config.file_prefix)
        save(puzzle, path)
    except (ConfigurationError, FetchError, SourcePayloadError, OutputError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
