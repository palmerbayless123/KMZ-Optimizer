"""Utilities for enriching tabular data with U.S. county information."""

from __future__ import annotations

import csv
import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request


LOGGER = logging.getLogger(__name__)


class CountyLookupError(RuntimeError):
    """Raised when a county lookup cannot be completed."""


@dataclass(frozen=True)
class LookupKey:
    """Cache key for county lookups."""

    latitude: Optional[float]
    longitude: Optional[float]
    zip_code: Optional[str]


def _normalize_float(value: Optional[str]) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def _normalize_zip(zip_code: Optional[str]) -> Optional[str]:
    if not zip_code:
        return None
    digits = "".join(ch for ch in str(zip_code) if ch.isdigit())
    if len(digits) < 5:
        return None
    return digits[:5]


class _HTTPClient:
    """Small wrapper around :func:`urllib.request.urlopen` with headers."""

    _DEFAULT_HEADERS = {"User-Agent": "KMZOptimizer/1.0 (+https://github.com/)"}

    def get_json(self, url: str, params: Dict[str, object], timeout: int) -> Dict[str, object]:
        query = urllib_parse.urlencode(params)
        full_url = f"{url}?{query}"
        request = urllib_request.Request(full_url, headers=self._DEFAULT_HEADERS)
        with urllib_request.urlopen(request, timeout=timeout) as response:
            data = response.read()
        return json.loads(data.decode("utf-8"))


class CountyLookup:
    """Resolve U.S. county names using FCC geographic services."""

    block_url = "https://geo.fcc.gov/api/census/block/find"
    area_url = "https://geo.fcc.gov/api/census/area"

    def __init__(self, http_client: Optional[_HTTPClient] = None, timeout: int = 10):
        self.http_client = http_client or _HTTPClient()
        self.timeout = timeout
        self._cache: Dict[LookupKey, Optional[str]] = {}

    def lookup(
        self,
        *,
        latitude: Optional[float],
        longitude: Optional[float],
        zip_code: Optional[str],
    ) -> Optional[str]:
        key = LookupKey(latitude, longitude, zip_code)
        if key in self._cache:
            return self._cache[key]

        county = None
        if latitude is not None and longitude is not None:
            county = self._lookup_by_coords(latitude, longitude)
        if county is None and zip_code is not None:
            county = self._lookup_by_zip(zip_code)

        self._cache[key] = county
        return county

    def _lookup_by_coords(self, latitude: float, longitude: float) -> Optional[str]:
        params = {"latitude": latitude, "longitude": longitude, "format": "json"}
        try:
            payload = self.http_client.get_json(self.block_url, params, self.timeout)
        except (urllib_error.URLError, ValueError, json.JSONDecodeError) as exc:  # pragma: no cover - network errors
            LOGGER.warning("County lookup by coordinates failed: %s", exc)
            return None

        county = payload.get("County") if isinstance(payload, dict) else None
        if isinstance(county, dict):
            name = county.get("name")
            if name:
                return name
        return None

    def _lookup_by_zip(self, zip_code: str) -> Optional[str]:
        params = {"format": "json", "zip": zip_code}
        try:
            payload = self.http_client.get_json(self.area_url, params, self.timeout)
        except (urllib_error.URLError, ValueError, json.JSONDecodeError) as exc:  # pragma: no cover - network errors
            LOGGER.warning("County lookup by ZIP failed: %s", exc)
            return None

        if isinstance(payload, dict):
            # The response embeds results within 'results', while 'counties' can be a list
            results = payload.get("results")
            if isinstance(results, list) and results:
                county = results[0].get("county_name")
                if county:
                    return county
            counties = payload.get("counties")
            if isinstance(counties, list) and counties:
                name = counties[0].get("name")
                if name:
                    return name
        return None


def iter_enriched_rows(
    rows: Iterable[Dict[str, str]],
    lookup: CountyLookup,
    *,
    county_field: str = "County",
    fail_on_missing: bool = False,
) -> Iterable[Dict[str, str]]:
    for row in rows:
        latitude = _normalize_float(row.get("lat") or row.get("Latitude"))
        longitude = _normalize_float(row.get("lng") or row.get("Longitude"))
        zip_code = _normalize_zip(row.get("Zip Code") or row.get("zip") or row.get("postal_code"))

        county = lookup.lookup(latitude=latitude, longitude=longitude, zip_code=zip_code)
        if county:
            row[county_field] = county
        elif fail_on_missing:
            identifier = row.get("Id") or row.get("Property Name") or zip_code or "unknown"
            raise CountyLookupError(f"Unable to resolve county for record {identifier!r}")
        else:
            row[county_field] = ""

        yield row


def add_counties_to_csv(
    input_path: Path,
    output_path: Optional[Path] = None,
    *,
    county_field: str = "County",
    fail_on_missing: bool = False,
    lookup: Optional[CountyLookup] = None,
) -> Path:
    input_path = Path(input_path)
    if output_path is None:
        output_path = input_path.with_name(input_path.stem + "_with_counties" + input_path.suffix)

    lookup = lookup or CountyLookup()

    with input_path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        fieldnames = list(reader.fieldnames or [])
        if county_field not in fieldnames:
            fieldnames.append(county_field)

        rows = list(iter_enriched_rows(reader, lookup, county_field=county_field, fail_on_missing=fail_on_missing))

    with output_path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def build_argument_parser() -> "argparse.ArgumentParser":
    import argparse

    parser = argparse.ArgumentParser(description="Add county information to a ranked locations CSV.")
    parser.add_argument("input", type=Path, help="Path to the ranked locations CSV file")
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        help="Optional output path; defaults to '<name>_with_counties.csv'",
    )
    parser.add_argument(
        "--output",
        dest="output",
        type=Path,
        help="Optional output path; defaults to '<name>_with_counties.csv'",
    )
    parser.add_argument("--county-field", default="County", help="Name of the column to populate with county names")
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Raise an error if a county cannot be resolved instead of leaving the field blank.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Timeout (seconds) for FCC API requests (default: 10)",
    )
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    lookup = CountyLookup(timeout=args.timeout)
    try:
        output_path = add_counties_to_csv(
            args.input,
            output_path=args.output,
            county_field=args.county_field,
            fail_on_missing=args.fail_on_missing,
            lookup=lookup,
        )
    except CountyLookupError as error:
        LOGGER.error("%s", error)
        return 1

    LOGGER.info("Wrote county-enriched CSV to %s", output_path)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
