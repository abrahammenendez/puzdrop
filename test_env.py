import pytest

from env import ConfigurationError, optional, required


def test_optional_strips_surrounding_whitespace(monkeypatch):
    monkeypatch.setenv("PUZDROP_X", "  value\n")
    assert optional("PUZDROP_X") == "value"


def test_optional_is_empty_when_unset_or_blank(monkeypatch):
    monkeypatch.delenv("PUZDROP_X", raising=False)
    assert optional("PUZDROP_X") == ""

    monkeypatch.setenv("PUZDROP_X", "   ")
    assert optional("PUZDROP_X") == ""


def test_required_names_the_missing_variable(monkeypatch):
    monkeypatch.setenv("PUZDROP_X", "  ")

    with pytest.raises(ConfigurationError, match="PUZDROP_X is not set"):
        required("PUZDROP_X")
