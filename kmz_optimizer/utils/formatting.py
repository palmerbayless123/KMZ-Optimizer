"""Formatting helpers."""

from __future__ import annotations

import re

_STATE_PATTERN = re.compile(r"^[A-Za-z]{2}$")


def format_number(value: float | int | None) -> str:
    """Return a comma separated string for numeric values."""

    if value is None:
        return "N/A"
    return f"{int(round(value)):,}"


def normalize_state_code(value: str | None) -> str:
    """Normalize a state code to upper case."""

    if not value:
        return ""
    value = value.strip().upper()
    if _STATE_PATTERN.match(value):
        return value
    return value[:2]
