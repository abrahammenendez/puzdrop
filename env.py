"""Reading configuration out of the environment, for fetch.py and notify.py."""

import os


class ConfigurationError(RuntimeError):
    """A required environment variable is missing or unusable."""


def optional(name: str) -> str:
    """Whitespace is stripped, so a variable set to blanks counts as unset."""
    return os.environ.get(name, "").strip()


def required(name: str) -> str:
    value = optional(name)
    if not value:
        raise ConfigurationError(f"{name} is not set")
    return value
