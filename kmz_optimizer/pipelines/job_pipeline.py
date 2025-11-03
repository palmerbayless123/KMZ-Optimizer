"""Processing pipeline orchestrator."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from ..config import STORAGE_PATHS
from ..core import ProcessingSummary
from ..services import (
    CSVIngestor,
    CountyEnricher,
    DataMerger,
    KmzExporter,
    KmzLoader,
    LocationMatcher,
)
from ..utils.io import ensure_directory, safe_filename

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class JobPipeline:
    """Orchestrates the entire processing workflow."""

    csv_ingestor: CSVIngestor
    kmz_loader: KmzLoader
    matcher: LocationMatcher
    county_enricher: CountyEnricher
    merger: DataMerger
    exporter: KmzExporter

    def run(
        self,
        *,
        csv_paths: Iterable[Path | str],
        kmz_path: Path | str | None = None,
        job_id: str,
    ) -> ProcessingSummary:
        logger.info("Starting pipeline for job %s", job_id)
        created_at = datetime.utcnow()

        csv_locations = self.csv_ingestor.load(csv_paths)
        csv_locations = self.county_enricher.enrich(csv_locations)
        merge_outcome = self.merger.merge(csv_locations)

        if kmz_path:
            kmz_document = self.kmz_loader.load(kmz_path)
            self.matcher.match(csv_locations, kmz_document.placemarks)

        output_dir = ensure_directory(STORAGE_PATHS.outputs / job_id)
        output_file = output_dir / f"{safe_filename(job_id)}.kmz"
        self.exporter.export(csv_locations, merge_outcome.metadata, output_file)

        completed_at = datetime.utcnow()
        logger.info("Job %s finished; generated %s", job_id, output_file.name)

        return ProcessingSummary(
            job_id=job_id,
            created_at=created_at,
            completed_at=completed_at,
            generated_files=[output_file.name],
            metadata=merge_outcome.metadata,
        )

    @classmethod
    def default(cls) -> "JobPipeline":
        return cls(
            csv_ingestor=CSVIngestor(),
            kmz_loader=KmzLoader(),
            matcher=LocationMatcher(),
            county_enricher=CountyEnricher(),
            merger=DataMerger(),
            exporter=KmzExporter(),
        )
