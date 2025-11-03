"""Domain models used throughout the KMZ Optimizer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Iterator, Mapping, Sequence


@dataclass(slots=True)
class CsvLocation:
    """Representation of a row inside a Placer.ai CSV export."""

    identifier: str | None
    property_name: str
    address: str | None
    city: str
    state: str
    state_code: str
    zip_code: str | None
    latitude: float
    longitude: float
    rank: int | None = None
    visits: float | None = None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: Mapping[str, object]) -> "CsvLocation":
        def parse_float(value: object) -> float | None:
            if value in (None, "", "null"):
                return None
            try:
                return float(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None

        def parse_int(value: object) -> int | None:
            if value in (None, "", "null"):
                return None
            try:
                return int(float(value))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None

        identifier = str(row.get("Id")) if row.get("Id") not in (None, "") else None

        return cls(
            identifier=identifier,
            property_name=str(row.get("Property Name", "")).strip(),
            address=(str(row.get("Address")) or None),
            city=str(row.get("City", "")).strip(),
            state=str(row.get("State", "")).strip(),
            state_code=str(row.get("State Code", "")).strip(),
            zip_code=(str(row.get("Zip Code")) or None),
            latitude=parse_float(row.get("Latitude")) or 0.0,
            longitude=parse_float(row.get("Longitude")) or 0.0,
            rank=parse_int(row.get("Rank")),
            visits=parse_float(row.get("Visits")),
            metadata={k: row.get(k) for k in row.keys()},
        )


@dataclass(slots=True)
class KmzPlacemark:
    """Representation of a placemark extracted from a KMZ file."""

    name: str
    latitude: float
    longitude: float
    address: str | None
    city: str | None
    state: str | None
    zip_code: str | None
    county: str | None = None
    attributes: dict = field(default_factory=dict)


@dataclass(slots=True)
class LocationBundle:
    """Aggregates CSV locations and optional KMZ placemarks."""

    csv_locations: list[CsvLocation]
    kmz_placemarks: list[KmzPlacemark]

    def states(self) -> set[str]:
        return {location.state_code for location in self.csv_locations if location.state_code}


@dataclass(slots=True)
class KmzMetadata:
    """Metadata required to craft KMZ exports."""

    date_range: str
    total_ranked_stores: int
    state_store_counts: dict[str, int]


@dataclass(slots=True)
class ProcessingSummary:
    """Information returned to API callers after job completion."""

    job_id: str
    created_at: datetime
    completed_at: datetime
    generated_files: Sequence[str]
    metadata: KmzMetadata

    def as_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "generated_files": list(self.generated_files),
            "metadata": {
                "date_range": self.metadata.date_range,
                "total_ranked_stores": self.metadata.total_ranked_stores,
                "state_store_counts": self.metadata.state_store_counts,
            },
        }


def flatten_bundles(bundles: Iterable[LocationBundle]) -> Iterator[CsvLocation]:
    """Yield all CSV locations from a sequence of bundles."""

    for bundle in bundles:
        yield from bundle.csv_locations
