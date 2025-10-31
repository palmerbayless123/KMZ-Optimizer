from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict

import pytest

from kmz_optimizer.county_enricher import (
    CountyLookup,
    CountyLookupError,
    add_counties_to_csv,
    iter_enriched_rows,
)


class DummyHttpClient:
    def __init__(self) -> None:
        self.responses: Dict[str, Dict[str, object]] = {}

    def queue(self, url: str, payload: Dict[str, object]) -> None:
        self.responses[url] = payload

    def get_json(self, url: str, params: Dict[str, object], timeout: int) -> Dict[str, object]:  # pragma: no cover - trivial
        if url not in self.responses:
            raise AssertionError(f"Unexpected request for {url}")
        return self.responses[url]


def build_lookup_with_responses(block_payload=None, area_payload=None) -> CountyLookup:
    client = DummyHttpClient()
    if block_payload is not None:
        client.queue(CountyLookup.block_url, block_payload)
    if area_payload is not None:
        client.queue(CountyLookup.area_url, area_payload)
    return CountyLookup(http_client=client)


def test_lookup_prefers_coordinates():
    lookup = build_lookup_with_responses(block_payload={"County": {"name": "Travis County"}})
    county = lookup.lookup(latitude=30.2672, longitude=-97.7431, zip_code="78701")
    assert county == "Travis County"


def test_lookup_falls_back_to_zip():
    lookup = build_lookup_with_responses(block_payload={}, area_payload={"results": [{"county_name": "Bexar County"}]})
    county = lookup.lookup(latitude=None, longitude=None, zip_code="78205")
    assert county == "Bexar County"


def test_iter_enriched_rows_sets_missing_county_without_failure():
    lookup = build_lookup_with_responses(block_payload={})
    rows = list(
        iter_enriched_rows(
            [{"Id": "1", "lat": "0", "lng": "0"}],
            lookup,
            fail_on_missing=False,
        )
    )
    assert rows[0]["County"] == ""


def test_iter_enriched_rows_extracts_zip_from_address():
    lookup = build_lookup_with_responses(
        block_payload={},
        area_payload={"results": [{"county_name": "Franklin County"}]},
    )
    rows = list(
        iter_enriched_rows(
            [
                {
                    "Id": "1",
                    "Address": "123 Example St, Columbus, OH 43215",
                }
            ],
            lookup,
            fail_on_missing=False,
        )
    )
    assert rows[0]["County"] == "Franklin County"


def test_iter_enriched_rows_raises_when_requested():
    lookup = build_lookup_with_responses(block_payload={})
    with pytest.raises(CountyLookupError):
        list(
            iter_enriched_rows(
                [{"Id": "1", "lat": "0", "lng": "0"}],
                lookup,
                fail_on_missing=True,
            )
        )


def test_add_counties_to_csv(tmp_path: Path):
    input_csv = tmp_path / "input.csv"
    with input_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Id", "lat", "lng", "Zip Code"])
        writer.writeheader()
        writer.writerow({"Id": "1", "lat": "30.2672", "lng": "-97.7431", "Zip Code": "78701"})

    lookup = build_lookup_with_responses(block_payload={"County": {"name": "Travis County"}})

    output_csv = add_counties_to_csv(input_csv, lookup=lookup)

    with output_csv.open() as handle:
        rows = list(csv.DictReader(handle))

    assert rows == [
        {
            "Id": "1",
            "lat": "30.2672",
            "lng": "-97.7431",
            "Zip Code": "78701",
            "County": "Travis County",
        }
    ]
