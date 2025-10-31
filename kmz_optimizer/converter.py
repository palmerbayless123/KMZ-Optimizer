"""Conversion utilities for building KMZ files from CSV tabular data."""

from __future__ import annotations

import argparse
import csv
import html
import io
import os
import logging
from typing import Iterable, List, Mapping, MutableMapping, Sequence
from xml.etree import ElementTree as ET

__all__ = ["convert_csv_to_kmz", "build_kml_document", "rows_from_csv"]


LOGGER = logging.getLogger(__name__)


def rows_from_csv(csv_path: str) -> Iterable[MutableMapping[str, str]]:
    """Yield rows from ``csv_path`` as dictionaries.

    Parameters
    ----------
    csv_path:
        Path to a CSV file containing a header row.

    Yields
    ------
    dict
        Row dictionaries keyed by the header names.
    """

    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError("CSV file must contain a header row")
        for row in reader:
            yield row


def build_kml_document(
    rows: Sequence[Mapping[str, str]],
    *,
    name_field: str,
    latitude_field: str,
    longitude_field: str,
    schema_id: str = "location_schema",
    description_fields: Sequence[str] | None = None,
) -> ET.Element:
    """Build a KML ``Document`` element from row dictionaries.

    The resulting :class:`~xml.etree.ElementTree.Element` is ready to be written
    into a KML file. Each row is converted into a Placemark that exposes all
    available fields as ``ExtendedData`` so that consumers of the generated KMZ
    can read the full attribute set for each pin.
    """

    if not rows:
        raise ValueError("At least one row is required to build a KML document")

    # Determine which fields we should expose in the schema/description.
    all_fields: List[str] = list(rows[0].keys())
    if description_fields is None:
        description_fields = [
            field
            for field in all_fields
            if field not in {latitude_field, longitude_field}
        ]

    kml = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
    document = ET.SubElement(kml, "Document")

    schema = ET.SubElement(document, "Schema", id=schema_id)
    for field in description_fields:
        ET.SubElement(schema, "SimpleField", name=field, type="string")

    for row in rows:
        placemark = ET.SubElement(document, "Placemark")
        name_value = row.get(name_field) or "Unnamed"
        name = ET.SubElement(placemark, "name")
        name.text = name_value

        description = ET.SubElement(placemark, "description")
        description.text = _build_description(row, description_fields)

        extended = ET.SubElement(placemark, "ExtendedData")
        schema_data = ET.SubElement(extended, "SchemaData", schemaUrl=f"#{schema_id}")
        for field in description_fields:
            value = row.get(field, "")
            simple_data = ET.SubElement(schema_data, "SimpleData", name=field)
            if value is not None:
                simple_data.text = value
            else:
                simple_data.text = ""

        latitude = _as_float(row.get(latitude_field), latitude_field)
        longitude = _as_float(row.get(longitude_field), longitude_field)
        point = ET.SubElement(placemark, "Point")
        coordinates = ET.SubElement(point, "coordinates")
        coordinates.text = f"{longitude:.12f},{latitude:.12f},0"

    return kml


def _build_description(row: Mapping[str, str], fields: Sequence[str]) -> str:
    if not fields:
        return ""
    buffer = io.StringIO()
    buffer.write("<![CDATA[<table border=\"1\" cellpadding=\"2\" cellspacing=\"0\">")
    for field in fields:
        buffer.write("<tr><th>")
        buffer.write(html.escape(field))
        buffer.write("</th><td>")
        value = row.get(field, "")
        buffer.write(html.escape(value if value is not None else ""))
        buffer.write("</td></tr>")
    buffer.write("</table>]]>")
    return buffer.getvalue()


def _as_float(value: str | None, field_name: str) -> float:
    if value in (None, ""):
        raise ValueError(f"Missing value for required field '{field_name}'")
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Field '{field_name}' must contain a numeric value") from exc


def convert_csv_to_kmz(
    csv_path: str,
    *,
    kmz_path: str | None = None,
    name_field: str = "Property Name",
    latitude_field: str = "lat",
    longitude_field: str = "lng",
    description_fields: Sequence[str] | None = None,
    kml_path: str | None = None,
    strict: bool = False,
) -> str:
    """Convert ``csv_path`` to a KMZ archive and return the output path."""

    rows = list(rows_from_csv(csv_path))
    if not rows:
        raise ValueError("CSV file did not contain any rows")

    valid_rows: list[MutableMapping[str, str]] = []
    skipped_rows = 0

    for index, row in enumerate(rows, start=1):
        try:
            _as_float(row.get(latitude_field), latitude_field)
            _as_float(row.get(longitude_field), longitude_field)
        except ValueError as exc:
            if strict:
                raise
            skipped_rows += 1
            LOGGER.warning("Skipping row %s: %s", index, exc)
            continue
        valid_rows.append(row)

    if not valid_rows:
        raise ValueError(
            "No valid rows found with latitude/longitude values. "
            "Provide valid coordinates or run with --strict to inspect errors."
        )

    kml_document = build_kml_document(
        valid_rows,
        name_field=name_field,
        latitude_field=latitude_field,
        longitude_field=longitude_field,
        description_fields=description_fields,
    )

    if kmz_path is None:
        base, _ = os.path.splitext(csv_path)
        kmz_path = f"{base}.kmz"

    kml_bytes = ET.tostring(kml_document, encoding="utf-8", xml_declaration=True)

    if kml_path is not None:
        with open(kml_path, "wb") as fh:
            fh.write(kml_bytes)

    _write_kmz_bytes(kml_bytes, kmz_path)
    if skipped_rows:
        LOGGER.info("Skipped %s row(s) without valid coordinates", skipped_rows)

    return kmz_path


def _write_kmz_bytes(kml_bytes: bytes, kmz_path: str) -> None:
    import zipfile

    with zipfile.ZipFile(kmz_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", kml_bytes)


def _parse_field_list(value: str | None) -> Sequence[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a KMZ file from a CSV dataset.")
    parser.add_argument("csv", help="Input CSV file")
    parser.add_argument("kmz", nargs="?", help="Output KMZ path (defaults to CSV name)")
    parser.add_argument("--kmz", dest="kmz", help="Output KMZ path (defaults to CSV name)")
    parser.add_argument("--kml", help="Optional path to save the intermediate KML file")
    parser.add_argument("--name-field", default="Property Name", help="Column to use for placemark names")
    parser.add_argument("--latitude-field", default="lat", help="Column containing latitude values")
    parser.add_argument("--longitude-field", default="lng", help="Column containing longitude values")
    parser.add_argument(
        "--description-fields",
        help="Comma separated list of columns to include in placemark descriptions",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail instead of skipping rows that are missing or contain invalid coordinates.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_argument_parser()
    args = parser.parse_args(argv)
    description_fields = _parse_field_list(args.description_fields)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    convert_csv_to_kmz(
        args.csv,
        kmz_path=args.kmz,
        kml_path=args.kml,
        name_field=args.name_field,
        latitude_field=args.latitude_field,
        longitude_field=args.longitude_field,
        description_fields=description_fields,
        strict=args.strict,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
