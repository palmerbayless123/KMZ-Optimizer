"""RQ task definitions for asynchronous job processing."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from rq import get_current_job

from .core.exceptions import ProcessingError
from .pipelines import JobPipeline


def process_job(*, job_id: str, csv_paths: Iterable[str], kmz_path: str | None) -> dict:
    """Execute the KMZ optimization pipeline for the given job."""

    job = get_current_job()
    if job:
        job.meta["progress"] = 0
        job.save_meta()

    pipeline = JobPipeline.default()

    try:
        summary = pipeline.run(
            csv_paths=[Path(path) for path in csv_paths],
            kmz_path=Path(kmz_path) if kmz_path else None,
            job_id=job_id,
        )
    except ProcessingError as exc:
        if job:
            job.meta["error"] = exc.as_dict()
            job.save_meta()
        raise

    if job:
        job.meta["progress"] = 100
        job.save_meta()

    return summary.as_dict()
