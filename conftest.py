"""Invented payloads shared by the test modules.

Nothing here is captured from the source: real content must never enter this
repository.
"""

import pytest


@pytest.fixture
def payload():
    def build(board, across, down, author="Autora Ficticia"):
        def entries(items):
            return {
                str(number): {"row": row, "col": col, "clue": clue}
                for number, (row, col, clue) in enumerate(items, start=1)
            }

        return {
            "data": {
                "attributes": {
                    "author": author,
                    "config": {
                        "board": board,
                        "entries": {
                            "across": entries(across),
                            "down": entries(down),
                        },
                    },
                }
            }
        }

    return build


@pytest.fixture
def simple_payload(payload):
    #   S O L
    #   O S O
    #   L A #
    return payload(
        board="SOL\r\nOSO\r\nLA#",
        across=[(0, 0, "Astro rey"), (1, 0, "Plantigrado"), (2, 0, "Nota y vocal")],
        down=[(0, 0, "Astro y nota"), (0, 1, "Contrario a nuevo"), (0, 2, "Articulo")],
    )
