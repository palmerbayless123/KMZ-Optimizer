"""Merge CSV locations with KMZ placemarks."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from ..core import CsvLocation, KmzMetadata, LocationBundle
from ..utils import normalize_state_code


@dataclass(slots=True)
class MergeOutcome:
    bundles: list[LocationBundle]
    metadata: KmzMetadata


class DataMerger:
    """Combine CSV data, enriched KMZ entries and compute metadata."""

    def merge(self, csv_locations: Iterable[CsvLocation]) -> MergeOutcome:
        csv_locations = list(csv_locations)

        state_counts: dict[str, int] = defaultdict(int)
        for location in csv_locations:
            state_counts[normalize_state_code(location.state_code)] += 1

        metadata = KmzMetadata(
            date_range=self._infer_date_range(csv_locations),
            total_ranked_stores=len(csv_locations),
            state_store_counts=dict(sorted(state_counts.items())),
        )

        bundle = LocationBundle(csv_locations=csv_locations, kmz_placemarks=[])
        return MergeOutcome(bundles=[bundle], metadata=metadata)

    def _infer_date_range(self, csv_locations: list[CsvLocation]) -> str:
        dates: list[datetime] = []
        for location in csv_locations:
            raw = location.metadata.get("Observation Date")
            if not raw:
                continue
            try:
                dates.append(datetime.fromisoformat(str(raw)))
            except ValueError:
                continue
        if not dates:
            return "Unknown"
        return f"{min(dates).date().isoformat()} - {max(dates).date().isoformat()}"
