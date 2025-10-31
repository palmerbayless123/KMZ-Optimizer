"""High-level workflow helpers for enriching CSV data and building KMZ files."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

from .converter import convert_csv_to_kmz
from .county_enricher import CountyLookup, add_counties_to_csv

__all__ = [
    "enrich_ranked_locations_csv",
    "build_kmz_from_enriched_csv",
    "run_csv_to_kmz_workflow",
]


def enrich_ranked_locations_csv(
    input_csv: Path,
    *,
    output_csv: Optional[Path] = None,
    county_field: str = "County",
    lookup: Optional[CountyLookup] = None,
    fail_on_missing: bool = False,
) -> Path:
    """Step 3: Enrich a ranked locations CSV with county information.

    Parameters
    ----------
    input_csv:
        Path to the CSV file that should be enriched.
    output_csv:
        Optional explicit path for the enriched CSV. When omitted the output
        is written alongside ``input_csv`` with ``_with_counties`` appended to
        the filename.
    county_field:
        Name of the column that should contain county values (defaults to
        ``"County"``).
    lookup:
        Optional :class:`~kmz_optimizer.county_enricher.CountyLookup` instance
        to use for resolving counties. When omitted a default instance is
        created which will query the FCC API.
    fail_on_missing:
        When ``True`` the enrichment will raise an exception if a county cannot
        be resolved for a record instead of leaving the county cell blank.

    Returns
    -------
    Path
        The filesystem path to the enriched CSV file.
    """

    return add_counties_to_csv(
        input_csv,
        output_path=output_csv,
        county_field=county_field,
        fail_on_missing=fail_on_missing,
        lookup=lookup,
    )


def _infer_description_fields(
    csv_path: Path,
    *,
    latitude_field: str,
    longitude_field: str,
) -> Sequence[str]:
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return []
        return [
            field
            for field in reader.fieldnames
            if field not in {latitude_field, longitude_field}
        ]


def build_kmz_from_enriched_csv(
    enriched_csv: Path,
    *,
    kmz_output: Optional[Path] = None,
    kml_output: Optional[Path] = None,
    name_field: str = "Property Name",
    latitude_field: str = "lat",
    longitude_field: str = "lng",
    description_fields: Optional[Sequence[str]] = None,
    strict: bool = False,
) -> Path:
    """Step 4: Convert an enriched CSV dataset into a KMZ archive."""

    if description_fields is None:
        description_fields = _infer_description_fields(
            enriched_csv,
            latitude_field=latitude_field,
            longitude_field=longitude_field,
        )

    kmz_path = convert_csv_to_kmz(
        str(enriched_csv),
        kmz_path=str(kmz_output) if kmz_output else None,
        kml_path=str(kml_output) if kml_output else None,
        name_field=name_field,
        latitude_field=latitude_field,
        longitude_field=longitude_field,
        description_fields=description_fields,
        strict=strict,
    )
    return Path(kmz_path)


def run_csv_to_kmz_workflow(
    input_csv: Path,
    *,
    output_csv: Optional[Path] = None,
    kmz_output: Optional[Path] = None,
    county_field: str = "County",
    lookup: Optional[CountyLookup] = None,
    fail_on_missing: bool = False,
    name_field: str = "Property Name",
    latitude_field: str = "lat",
    longitude_field: str = "lng",
    description_fields: Optional[Sequence[str]] = None,
    kml_output: Optional[Path] = None,
    strict: bool = False,
) -> Tuple[Path, Path]:
    """Run the two-step workflow: enrich the CSV and produce a KMZ file."""

    enriched_csv = enrich_ranked_locations_csv(
        input_csv,
        output_csv=output_csv,
        county_field=county_field,
        lookup=lookup,
        fail_on_missing=fail_on_missing,
    )
    kmz_path = build_kmz_from_enriched_csv(
        enriched_csv,
        kmz_output=kmz_output,
        kml_output=kml_output,
        name_field=name_field,
        latitude_field=latitude_field,
        longitude_field=longitude_field,
        description_fields=description_fields,
        strict=strict,
    )
    return enriched_csv, kmz_path


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the ranked locations CSV -> counties -> KMZ workflow.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    step3 = subparsers.add_parser(
        "step3",
        help="Enrich a ranked locations CSV with county information.",
    )
    step3.add_argument("input", type=Path, help="Path to the ranked locations CSV")
    step3.add_argument(
        "--output",
        type=Path,
        help="Optional output path for the enriched CSV (defaults to '<name>_with_counties.csv')",
    )
    step3.add_argument(
        "--county-field",
        default="County",
        help="Column name used for county values (default: County)",
    )
    step3.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Raise an error when a county lookup cannot be resolved.",
    )
    step3.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Timeout for FCC API requests (default: 10 seconds)",
    )

    step4 = subparsers.add_parser(
        "step4",
        help="Reingest the enriched CSV and write the final KMZ file.",
    )
    step4.add_argument("input", type=Path, help="Enriched CSV produced by step 3")
    step4.add_argument("--kmz", type=Path, help="Output KMZ path (defaults to CSV name)")
    step4.add_argument(
        "--kml",
        type=Path,
        help="Optional path to also write the intermediate KML document",
    )
    step4.add_argument(
        "--name-field",
        default="Property Name",
        help="Column used for placemark names",
    )
    step4.add_argument(
        "--latitude-field",
        default="lat",
        help="Column containing latitude values",
    )
    step4.add_argument(
        "--longitude-field",
        default="lng",
        help="Column containing longitude values",
    )
    step4.add_argument(
        "--description-fields",
        help="Comma separated list of columns to include in placemark descriptions",
    )
    step4.add_argument(
        "--strict",
        action="store_true",
        help="Fail instead of skipping rows with missing coordinates when generating the KMZ.",
    )

    run = subparsers.add_parser(
        "run",
        help="Execute steps 3 and 4 in a single command.",
    )
    run.add_argument("input", type=Path, help="Path to the ranked locations CSV")
    run.add_argument(
        "--output",
        type=Path,
        help="Optional output path for the enriched CSV",
    )
    run.add_argument(
        "--kmz",
        type=Path,
        help="Optional output path for the KMZ file",
    )
    run.add_argument(
        "--kml",
        type=Path,
        help="Optional path to also write the intermediate KML document",
    )
    run.add_argument(
        "--county-field",
        default="County",
        help="Column name used for county values (default: County)",
    )
    run.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Raise an error when a county lookup cannot be resolved.",
    )
    run.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Timeout for FCC API requests (default: 10 seconds)",
    )
    run.add_argument(
        "--name-field",
        default="Property Name",
        help="Column used for placemark names",
    )
    run.add_argument(
        "--latitude-field",
        default="lat",
        help="Column containing latitude values",
    )
    run.add_argument(
        "--longitude-field",
        default="lng",
        help="Column containing longitude values",
    )
    run.add_argument(
        "--description-fields",
        help="Comma separated list of columns to include in placemark descriptions",
    )
    run.add_argument(
        "--strict",
        action="store_true",
        help="Fail instead of skipping rows with missing coordinates when generating the KMZ.",
    )

    return parser


def _parse_description_fields(value: Optional[str]) -> Optional[Sequence[str]]:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = _build_argument_parser()
    args = parser.parse_args(argv)

    if args.command == "step3":
        lookup = CountyLookup(timeout=args.timeout)
        enrich_ranked_locations_csv(
            args.input,
            output_csv=args.output,
            county_field=args.county_field,
            lookup=lookup,
            fail_on_missing=args.fail_on_missing,
        )
        return 0

    if args.command == "step4":
        description_fields = _parse_description_fields(args.description_fields)
        build_kmz_from_enriched_csv(
            args.input,
            kmz_output=args.kmz,
            kml_output=args.kml,
            name_field=args.name_field,
            latitude_field=args.latitude_field,
            longitude_field=args.longitude_field,
            description_fields=description_fields,
            strict=args.strict,
        )
        return 0

    if args.command == "run":
        lookup = CountyLookup(timeout=args.timeout)
        description_fields = _parse_description_fields(args.description_fields)
        run_csv_to_kmz_workflow(
            args.input,
            output_csv=args.output,
            kmz_output=args.kmz,
            kml_output=args.kml,
            county_field=args.county_field,
            lookup=lookup,
            fail_on_missing=args.fail_on_missing,
            name_field=args.name_field,
            latitude_field=args.latitude_field,
            longitude_field=args.longitude_field,
            description_fields=description_fields,
            strict=args.strict,
        )
        return 0

    parser.error("Unknown command")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
