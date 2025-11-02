"""KMZ parsing helpers."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile

from ..core import KmzPlacemark
from ..core.exceptions import ProcessingError


@dataclass(slots=True)
class KmzDocument:
    placemarks: list[KmzPlacemark]


class KmzLoader:
    """Load placemarks from KMZ files."""

    def load(self, path: Path | str) -> KmzDocument:
        path = Path(path)
        if not path.exists():
            raise ProcessingError(f"KMZ file not found: {path}")

        with ZipFile(path) as archive:
            try:
                with archive.open("doc.kml") as handle:
                    tree = ET.parse(handle)
            except KeyError as exc:  # pragma: no cover - rare scenario
                raise ProcessingError("KMZ archive is missing doc.kml") from exc

        root = tree.getroot()
        placemarks = [self._parse_placemark(node) for node in root.iterfind(".//{*}Placemark")]
        return KmzDocument(placemarks=[pm for pm in placemarks if pm is not None])

    def _parse_placemark(self, node: ET.Element) -> KmzPlacemark | None:
        name = self._text(node, "./{*}name")
        if not name:
            return None

        coordinates = self._text(node, "./{*}Point/{*}coordinates")
        if not coordinates:
            return None
        lon_str, lat_str, *_ = coordinates.split(",")
        latitude = float(lat_str)
        longitude = float(lon_str)

        extended_data = self._extract_extended_data(node)
        return KmzPlacemark(
            name=name,
            latitude=latitude,
            longitude=longitude,
            address=extended_data.get("Address"),
            city=extended_data.get("City"),
            state=extended_data.get("State"),
            zip_code=extended_data.get("Zip"),
            county=extended_data.get("County"),
            attributes=extended_data,
        )

    def _extract_extended_data(self, node: ET.Element) -> dict[str, str]:
        data = {}
        for element in node.findall(".//{*}SimpleData"):
            name = element.attrib.get("name")
            if name:
                data[name] = (element.text or "").strip()
        return data

    @staticmethod
    def _text(node: ET.Element, selector: str) -> str | None:
        found = node.find(selector)
        return (found.text or None) if found is not None else None
