"""Generate KMZ files from processed locations."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile, ZIP_DEFLATED

from ..core import CsvLocation, KmzMetadata
from ..utils import format_number


@dataclass(slots=True)
class KmzExporter:
    """Create KMZ archives for the provided locations."""

    schema_id: str = "kmz_optimizer_schema"

    def export(self, locations: Iterable[CsvLocation], metadata: KmzMetadata, output_path: Path | str) -> Path:
        output_path = Path(output_path)
        kml_content = self._build_kml(list(locations), metadata)
        with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("doc.kml", kml_content)
        return output_path

    def _build_kml(self, locations: list[CsvLocation], metadata: KmzMetadata) -> bytes:
        kml = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
        document = ET.SubElement(kml, "Document")
        schema = ET.SubElement(document, "Schema", id=self.schema_id, name="KMZ Optimizer")

        fields = [
            ("Name", "string"),
            ("Address", "string"),
            ("City", "string"),
            ("State", "string"),
            ("Zip", "string"),
            ("County", "string"),
            ("Placer Rank ({})".format(metadata.date_range), "string"),
            ("Ranked Stores", "string"),
            ("Total Visits ({})".format(metadata.date_range), "string"),
            ("Total {} Stores".format(metadata.state_store_counts.keys().__iter__().__next__() if metadata.state_store_counts else "State"), "string"),
            ("LAT", "string"),
            ("LONG", "string"),
        ]

        for name, field_type in fields:
            ET.SubElement(schema, "SimpleField", type=field_type, name=name)

        for location in locations:
            placemark = ET.SubElement(document, "Placemark")
            ET.SubElement(placemark, "name").text = location.property_name
            extended_data = ET.SubElement(placemark, "ExtendedData")
            schema_data = ET.SubElement(extended_data, "SchemaData", schemaUrl=f"#{self.schema_id}")

            def add_field(key: str, value: str | None) -> None:
                element = ET.SubElement(schema_data, "SimpleData", name=key)
                element.text = value or ""

            total_state_stores = metadata.state_store_counts.get(location.state_code, 0)

            add_field("Name", location.property_name)
            add_field("Address", location.address)
            add_field("City", location.city)
            add_field("State", location.state_code)
            add_field("Zip", location.zip_code)
            add_field("County", (location.metadata.get("County") or "").upper())
            add_field(f"Placer Rank ({metadata.date_range})", str(location.rank or ""))
            add_field("Ranked Stores", str(metadata.total_ranked_stores))
            add_field(f"Total Visits ({metadata.date_range})", format_number(location.visits))
            add_field(f"Total {location.state_code} Stores", str(total_state_stores))
            add_field("LAT", f"{location.latitude:.6f}")
            add_field("LONG", f"{location.longitude:.6f}")

            point = ET.SubElement(placemark, "Point")
            ET.SubElement(point, "coordinates").text = f"{location.longitude},{location.latitude},0"

        return ET.tostring(kml, encoding="utf-8", xml_declaration=True)
