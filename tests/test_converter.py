import zipfile
from pathlib import Path

import pytest

from kmz_optimizer.converter import build_kml_document, convert_csv_to_kmz


def test_build_kml_document_populates_extended_data():
    rows = [
        {
            "Name": "Test Location",
            "lat": "1.5",
            "lng": "-2.5",
            "City": "Exampleville",
            "State": "TX",
        }
    ]

    document = build_kml_document(
        rows,
        name_field="Name",
        latitude_field="lat",
        longitude_field="lng",
    )

    xml = _element_to_string(document)
    assert "<SimpleData name=\"City\">Exampleville</SimpleData>" in xml
    assert "<SimpleData name=\"State\">TX</SimpleData>" in xml
    assert "-2.500000000000,1.500000000000,0" in xml


def test_convert_csv_to_kmz_writes_archive(tmp_path: Path):
    csv_content = "Name,lat,lng,City\nSample,1.0,2.0,Somewhere\n"
    csv_path = tmp_path / "points.csv"
    csv_path.write_text(csv_content)

    kmz_path = tmp_path / "points.kmz"
    convert_csv_to_kmz(
        str(csv_path),
        kmz_path=str(kmz_path),
        name_field="Name",
        latitude_field="lat",
        longitude_field="lng",
    )

    assert kmz_path.exists()

    with zipfile.ZipFile(kmz_path) as zf:
        data = zf.read("doc.kml").decode("utf-8")

    assert "Sample" in data
    assert "Somewhere" in data
    assert "2.000000000000,1.000000000000,0" in data


def _element_to_string(element):
    from xml.etree import ElementTree as ET

    return ET.tostring(element, encoding="unicode")
