"""REST API blueprint."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from rq.exceptions import NoSuchJobError
from rq.job import Job

from ..config import APP_CONFIG, STORAGE_PATHS
from ..utils.io import ensure_directory, safe_filename

api_bp = Blueprint("api", __name__)

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

    created_at = datetime.utcnow().isoformat()
    queue = _queue()

    job = queue.enqueue(
        "kmz_optimizer.tasks.process_job",
        kwargs={
            "job_id": job_id,
            "csv_paths": [str(path) for path in csv_paths],
            "kmz_path": str(kmz_path) if kmz_path else None,
        },
        job_id=job_id,
        meta={"created_at": created_at},
    )

    response = {
        "job_id": job.id,
        "status": job.get_status(refresh=False),
        "created_at": created_at,
    }

    return jsonify(response), 202


@api_bp.get("/jobs/<job_id>")
def job_status(job_id: str):
    try:
        job = Job.fetch(job_id, connection=_connection())
    except NoSuchJobError:
        return jsonify({"error": "Job not found"}), 404

    payload: dict[str, object] = {
        "job_id": job.id,
        "status": job.get_status(refresh=True),
        "created_at": job.meta.get("created_at"),
    }

    if job.is_finished:
        payload["result"] = job.result or {}
        return jsonify(payload), 200
    if job.is_failed:
        payload["error"] = job.meta.get("error", job.exc_info)
        return jsonify(payload), 500

    payload["progress"] = job.meta.get("progress", 0)
    return jsonify(payload), 200


def _allowed(filename: str, extensions: tuple[str, ...]) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in extensions


def _queue():
    return current_app.extensions["rq"]["queue"]


def _connection():
    return current_app.extensions["rq"]["connection"]
