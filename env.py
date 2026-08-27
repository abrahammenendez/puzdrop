"""Reading configuration out of the environment, for fetch.py and notify.py."""

import os


class ConfigurationError(RuntimeError):
    """A required environment variable is missing or unusable."""


def optional(name: str) -> str:
    """The stripped value of an environment variable, or "" when it is unset."""
    return os.environ.get(name, "").strip()


def required(name: str) -> str:
    """Like optional(), but raise ConfigurationError when the value is empty."""
    value = optional(name)
    if not value:
        raise ConfigurationError(f"{name} is not set")
    return value
