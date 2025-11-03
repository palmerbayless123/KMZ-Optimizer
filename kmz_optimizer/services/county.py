"""County enrichment service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..core import CsvLocation


@dataclass(slots=True)
class CountyEnricher:
    """Attach county information to CSV locations."""

    def enrich(self, locations: Iterable[CsvLocation]) -> list[CsvLocation]:
        """Uppercase and normalize county information if provided."""

        enriched: list[CsvLocation] = []
        for location in locations:
            county = location.metadata.get("County")
            if isinstance(county, str) and county.strip():
                location.metadata["County"] = county.strip().upper().replace(" COUNTY", "")
            enriched.append(location)
        return enriched
