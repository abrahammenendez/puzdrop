import puz
import pytest

from convert import SourcePayloadError, build_puzzle, to_latin1, validate

TITLE = "Crucigrama"
DATE = "2026-08-25"


def test_grid_maps_black_squares_and_solution(simple_payload):
    puzzle = build_puzzle(simple_payload, DATE, TITLE)

    assert (puzzle.width, puzzle.height) == (3, 3)
    assert puzzle.solution == "SOLOSOLA."
    assert puzzle.fill == "--------."


def test_clues_are_ordered_by_grid_position_not_source_numbering(simple_payload):
    numbering = build_puzzle(simple_payload, DATE, TITLE).clue_numbering()

    assert [c["clue"] for c in numbering.across] == [
        "Astro rey",
        "Plantigrado",
        "Nota y vocal",
    ]
    assert [c["clue"] for c in numbering.down] == [
        "Astro y nota",
        "Contrario a nuevo",
        "Articulo",
    ]


def test_short_rows_are_padded_with_black_squares(payload):
    puzzle = build_puzzle(
        payload(
            board="SOL\r\nOSO\r\nLA",
            across=[(0, 0, "a"), (1, 0, "b"), (2, 0, "c")],
            down=[(0, 0, "d"), (0, 1, "e"), (0, 2, "f")],
        ),
        DATE,
        TITLE,
    )

    assert puzzle.solution == "SOLOSOLA."


def test_spanish_characters_survive_the_round_trip(payload, tmp_path):
    puzzle = build_puzzle(
        payload(
            board="AÑO\r\nÉSE\r\nOS#",
            across=[(0, 0, "Periodo de 12 meses"), (1, 0, "Aquél"), (2, 0, "Plural")],
            down=[(0, 0, "Prefijo"), (0, 1, "Con eñe"), (0, 2, "Vocal doble")],
        ),
        DATE,
        TITLE,
    )
    path = tmp_path / "puzzle.puz"
    puzzle.save(str(path))

    # Reading validates all three checksums, so a corrupt file raises here.
    reloaded = puz.read(str(path))

    assert "Ñ" in reloaded.solution
    assert "É" in reloaded.solution
    assert reloaded.clue_numbering().down[1]["clue"] == "Con eñe"


def test_characters_outside_latin1_fold_to_their_base_letter():
    # ë is in Latin-1 and survives. Ć is not, so it loses the accent.
    assert to_latin1("Zoë Ćurić") == "Zoë Curic"
    assert to_latin1("puntos…") == "puntos..."
    assert to_latin1("€€") == "EUREUR"
    assert to_latin1("mañana áéíóú") == "mañana áéíóú"


def test_characters_with_no_latin1_form_become_question_marks():
    assert to_latin1("≈ 3 •") == "? 3 ?"


def test_validate_rejects_a_puzzle_with_empty_clues(payload):
    puzzle = build_puzzle(
        payload(
            board="SOL\r\nOSO\r\nLA#",
            across=[(0, 0, "Astro rey"), (1, 0, ""), (2, 0, "Nota y vocal")],
            down=[(0, 0, "d"), (0, 1, "e"), (0, 2, "f")],
        ),
        DATE,
        TITLE,
    )

    with pytest.raises(SourcePayloadError, match="clues are empty"):
        validate(puzzle)


def test_validate_rejects_a_grid_letter_outside_latin1(payload):
    puzzle = build_puzzle(
        payload(
            board="SOĆ\r\nOSO\r\nLA#",
            across=[(0, 0, "a"), (1, 0, "b"), (2, 0, "c")],
            down=[(0, 0, "d"), (0, 1, "e"), (0, 2, "f")],
        ),
        DATE,
        TITLE,
    )

    with pytest.raises(SourcePayloadError, match="Latin-1 cannot store"):
        validate(puzzle)


def test_validate_accepts_a_complete_puzzle(simple_payload):
    validate(build_puzzle(simple_payload, DATE, TITLE))


def test_empty_board_is_rejected(payload):
    with pytest.raises(SourcePayloadError, match="no grid rows"):
        build_puzzle(payload(board="", across=[], down=[]), DATE, TITLE)


def test_unexpected_payload_shape_is_rejected():
    with pytest.raises(SourcePayloadError, match="unexpected payload shape"):
        build_puzzle({"data": {}}, DATE, TITLE)


def test_title_carries_the_requested_date(simple_payload):
    assert build_puzzle(simple_payload, DATE, TITLE).title == "Crucigrama - 2026-08-25"
