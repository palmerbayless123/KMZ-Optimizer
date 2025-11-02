"""Match CSV locations against KMZ placemarks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..core import CsvLocation, KmzPlacemark
from ..utils import haversine_distance


@dataclass(slots=True)
class MatchResult:
    csv_location: CsvLocation
    kmz_placemark: KmzPlacemark
    distance_meters: float
    confidence: float


class LocationMatcher:
    """Perform geospatial matching between CSV and KMZ entries."""

    def __init__(self, *, strict_distance: float = 50.0, loose_distance: float = 500.0):
        self.strict_distance = strict_distance
        self.loose_distance = loose_distance

    def match(self, csv_locations: Iterable[CsvLocation], placemarks: Iterable[KmzPlacemark]) -> list[MatchResult]:
        matches: list[MatchResult] = []
        for csv_location in csv_locations:
            best_match = self._match_single(csv_location, placemarks)
            if best_match:
                matches.append(best_match)
        return matches

    def _match_single(self, csv_location: CsvLocation, placemarks: Iterable[KmzPlacemark]) -> MatchResult | None:
        best: MatchResult | None = None
        for placemark in placemarks:
            if placemark.city and placemark.city.upper() != csv_location.city.upper():
                continue
            if placemark.state and placemark.state.upper() != csv_location.state.upper():
                continue

            distance = haversine_distance(
                csv_location.latitude,
                csv_location.longitude,
                placemark.latitude,
                placemark.longitude,
            )

            confidence = self._confidence(distance)
            if confidence == 0:
                continue

            candidate = MatchResult(
                csv_location=csv_location,
                kmz_placemark=placemark,
                distance_meters=distance,
                confidence=confidence,
            )
            if best is None or candidate.confidence > best.confidence:
                best = candidate
        return best

    def _confidence(self, distance: float) -> float:
        if distance <= self.strict_distance:
            return 1.0
        if distance <= self.loose_distance / 2:
            return 0.8
        if distance <= self.loose_distance:
            return 0.6
        return 0.0
