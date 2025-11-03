"""CSV ingestion service."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Sequence

from ..core import CsvLocation
from ..core.exceptions import ProcessingError
from ..utils import detect_encoding


class CSVIngestor:
    """Load CSV files into :class:`CsvLocation` objects."""

    REQUIRED_COLUMNS: Sequence[str] = (
        "Rank",
        "Property Name",
        "Latitude",
        "Longitude",
        "City",
        "State",
        "State Code",
        "Zip Code",
    )

    def __init__(self, *, encoding: str | None = None):
        self.encoding = encoding or "utf-8-sig"

    def load(self, paths: Iterable[Path | str]) -> list[CsvLocation]:
        locations: list[CsvLocation] = []
        for path in paths:
            locations.extend(self._load_single(Path(path)))
        return locations

    def _load_single(self, path: Path) -> list[CsvLocation]:
        if not path.exists():
            raise ProcessingError(f"CSV file not found: {path}")

        encoding = self.encoding
        if encoding == "auto":
            encoding = detect_encoding(path)

        with path.open("r", encoding=encoding, errors="replace") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames or []
            self._validate_headers(headers, path)

            rows = [CsvLocation.from_row(row) for row in reader if any(row.values())]

        return rows

    def _validate_headers(self, headers: Sequence[str], path: Path) -> None:
        missing = [column for column in self.REQUIRED_COLUMNS if column not in headers]
        if missing:
            raise ProcessingError(
                "CSV file is missing required columns",
                details={"path": str(path), "missing": missing},
            )
