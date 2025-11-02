"""REST API blueprint."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from ..config import APP_CONFIG, STORAGE_PATHS
from ..core.exceptions import ProcessingError
from ..pipelines import JobPipeline
from ..utils.io import ensure_directory, safe_filename

api_bp = Blueprint("api", __name__)

jobs: dict[str, dict] = {}


@api_bp.post("/jobs")
def create_job():
    """Create a processing job from uploaded files."""

    if "csv_files" not in request.files:
        return jsonify({"error": "csv_files field is required"}), 400

    csv_files = request.files.getlist("csv_files")
    kmz_file = request.files.get("kmz_file")

    job_id = str(uuid.uuid4())
    job_dir = ensure_directory(STORAGE_PATHS.uploads / job_id)
    csv_paths: list[Path] = []

    for uploaded in csv_files:
        if not uploaded.filename:
            continue
        if not _allowed(uploaded.filename, APP_CONFIG.allowed_csv_extensions):
            return jsonify({"error": f"Invalid CSV file: {uploaded.filename}"}), 400
        filename = safe_filename(uploaded.filename)
        target = job_dir / filename
        uploaded.save(target)
        csv_paths.append(target)

    kmz_path: Path | None = None
    if kmz_file and kmz_file.filename:
        if not _allowed(kmz_file.filename, APP_CONFIG.allowed_kmz_extensions):
            return jsonify({"error": "Invalid KMZ file"}), 400
        filename = safe_filename(kmz_file.filename)
        kmz_path = job_dir / filename
        kmz_file.save(kmz_path)

    pipeline = JobPipeline.default()

    try:
        summary = pipeline.run(csv_paths=csv_paths, kmz_path=kmz_path, job_id=job_id)
    except ProcessingError as exc:
        return jsonify({"error": exc.as_dict()}), 400

    jobs[job_id] = {
        "summary": summary.as_dict(),
        "created_at": datetime.utcnow().isoformat(),
    }

    return jsonify(jobs[job_id]), 201


@api_bp.get("/jobs/<job_id>")
def job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


def _allowed(filename: str, extensions: tuple[str, ...]) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in extensions
