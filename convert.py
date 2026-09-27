"""Convert a source crossword payload into the Across Lite (.puz) format."""

import unicodedata
from typing import Any

import puz

BLACK = "#"
PUZ_BLACK = "."
PUZ_BLANK = "-"

# Clues keyed by the coordinate of the square their entry starts at.
Clues = dict[tuple[int, int], str]

# .puz stores text as Latin-1, which has no room for smart quotes, long dashes,
# an ellipsis or the euro sign. Swap those for ASCII before anything tries to
# encode them.
# The non-breaking space is the odd one out: Latin-1 has it, but it reads as a
# space and solvers are happier with a real one.
_REPLACEMENTS = {
    "…": "...",
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "–": "-",
    "—": "-",
    "€": "EUR",
    "\u00a0": " ",
}


class SourcePayloadError(ValueError):
    """The payload is not shaped the way the converter expects."""


def to_latin1(text: str) -> str:
    """Fold text into Latin-1, dropping accents only where there is no choice.

    Spanish accents and eñe are already in Latin-1, so they come through
    untouched. Anything outside it loses its accent, and anything with no
    accent to lose becomes "?".
    """
    for original, replacement in _REPLACEMENTS.items():
        text = text.replace(original, replacement)

    folded = []
    for char in text:
        try:
            char.encode("latin-1")
        except UnicodeEncodeError:
            char = "".join(
                c
                for c in unicodedata.normalize("NFKD", char)
                if not unicodedata.combining(c)
            )
        folded.append(char)
    # Stripping leaves a character with no accent, like "≈", as it was, and
    # .save() cannot encode it.
    return "".join(folded).encode("latin-1", "replace").decode("latin-1")


def _parse_grid(board: str) -> tuple[list[str], int, int]:
    rows = [row for row in board.splitlines() if row]
    if not rows:
        raise SourcePayloadError("payload contains no grid rows")

    width = max(len(row) for row in rows)

    # The source sometimes leaves the trailing black squares off a row.
    return [row.ljust(width, BLACK) for row in rows], width, len(rows)


def _entries(payload_entries: dict[str, Any], direction: str) -> Clues:
    return {
        (raw["row"], raw["col"]): to_latin1(raw["clue"])
        for raw in payload_entries.get(direction, {}).values()
    }


def _unpack(payload: dict[str, Any]) -> tuple[str, Clues, Clues, str]:
    try:
        attributes = payload["data"]["attributes"]
        config = attributes["config"]
        return (
            config["board"],
            _entries(config["entries"], "across"),
            _entries(config["entries"], "down"),
            attributes.get("author") or "",
        )
    except (KeyError, TypeError) as error:
        raise SourcePayloadError(f"unexpected payload shape ({error})") from None


def build_puzzle(payload: dict[str, Any], date: str, title: str) -> puz.Puzzle:
    board, across_clues, down_clues, author = _unpack(payload)

    rows, width, height = _parse_grid(board)
    solution = "".join(
        PUZ_BLACK if cell == BLACK else cell for row in rows for cell in row
    )
    fill = "".join(PUZ_BLACK if cell == PUZ_BLACK else PUZ_BLANK for cell in solution)

    # .puz takes clue order from the grid, not from the source's numbering, so
    # match each slot on (row, col). Going by the number puts every clue on the
    # wrong entry.
    across, down = puz.get_grid_numbering(solution, width, height)
    clues = [""] * (len(across) + len(down))
    for slot in across:
        clues[slot["clue_index"]] = across_clues.get((slot["row"], slot["col"]), "")
    for slot in down:
        clues[slot["clue_index"]] = down_clues.get((slot["row"], slot["col"]), "")

    puzzle = puz.Puzzle()
    puzzle.width = width
    puzzle.height = height
    puzzle.solution = solution
    puzzle.fill = fill
    puzzle.clues = clues
    puzzle.title = to_latin1(f"{title} - {date}")
    puzzle.author = to_latin1(author)
    return puzzle


def validate(puzzle: puz.Puzzle) -> None:
    """Reject a puzzle that is structurally fine but useless.

    Checksums would happily pass a grid whose clues all came back empty, so
    catch that here, before the file reaches a solver.
    """
    if puzzle.width <= 0 or puzzle.height <= 0:
        raise SourcePayloadError("puzzle has empty dimensions")

    if len(puzzle.solution) != puzzle.width * puzzle.height:
        raise SourcePayloadError("solution length does not match grid size")

    # Clue text gets folded into Latin-1. A grid letter never does: change one
    # and it stops matching the clue that answers it.
    try:
        puzzle.solution.encode("latin-1")
    except UnicodeEncodeError:
        raise SourcePayloadError(
            "solution has characters Latin-1 cannot store"
        ) from None

    numbering = puzzle.clue_numbering()
    expected = len(numbering.across) + len(numbering.down)
    if len(puzzle.clues) != expected:
        raise SourcePayloadError(
            f"expected {expected} clues, payload produced {len(puzzle.clues)}"
        )

    empty = sum(1 for clue in puzzle.clues if not clue.strip())
    if empty:
        raise SourcePayloadError(f"{empty} clues are empty")
