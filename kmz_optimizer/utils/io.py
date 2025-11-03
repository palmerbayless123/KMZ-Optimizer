"""File IO utilities."""

from __future__ import annotations

import os
import unicodedata
from pathlib import Path

import chardet


def detect_encoding(path: os.PathLike[str] | str) -> str:
    """Detect the encoding of a text file."""

    with open(path, "rb") as handle:
        raw = handle.read()
    detection = chardet.detect(raw)
    return detection.get("encoding") or "utf-8"


def safe_filename(filename: str) -> str:
    """Return a filesystem safe filename."""

    normalized = unicodedata.normalize("NFKD", filename)
    sanitized = [c for c in normalized if c.isalnum() or c in {"-", "_", "."}]
    return "".join(sanitized)


def ensure_directory(path: os.PathLike[str] | str) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory
