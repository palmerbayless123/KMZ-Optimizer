from __future__ import annotations

import csv
import zipfile
from pathlib import Path

import pytest

from kmz_optimizer.workflow import (
    build_kmz_from_enriched_csv,
    enrich_ranked_locations_csv,
    run_csv_to_kmz_workflow,
)


class FakeLookup:
    def __init__(self, county: str):
        self.county = county

    def lookup(self, *, latitude, longitude, zip_code):
        return self.county


@pytest.fixture()
def ranked_locations_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "ranked_locations.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "Ranking",
                "Property Name",
                "Address",
                "City",
                "State Code",
                "Zip Code",
                "lat",
                "lng",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "Ranking": "1",
                "Property Name": "Academy Sports",
                "Address": "123 Example Rd",
                "City": "Austin",
                "State Code": "TX",
                "Zip Code": "78758",
                "lat": "30.391",
                "lng": "-97.724",
            }
        )
    return csv_path


def read_csv_rows(csv_path: Path):
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_enrich_ranked_locations_csv_writes_county_column(ranked_locations_csv: Path):
    output = enrich_ranked_locations_csv(
        ranked_locations_csv,
        lookup=FakeLookup("Travis County"),
    )

    rows = read_csv_rows(output)
    assert rows[0]["County"] == "Travis County"


def test_build_kmz_from_enriched_csv_uses_all_fields(ranked_locations_csv: Path):
    enriched = enrich_ranked_locations_csv(
        ranked_locations_csv,
        lookup=FakeLookup("Travis County"),
    )

    kmz_path = build_kmz_from_enriched_csv(enriched)
    with zipfile.ZipFile(kmz_path) as archive:
        with archive.open("doc.kml") as kml_file:
            content = kml_file.read().decode("utf-8")

    assert "Travis County" in content
    assert "Academy Sports" in content


def test_run_csv_to_kmz_workflow_returns_paths(ranked_locations_csv: Path):
    enriched_path, kmz_path = run_csv_to_kmz_workflow(
        ranked_locations_csv,
        lookup=FakeLookup("Travis County"),
    )

    assert enriched_path.exists()
    assert kmz_path.exists()
