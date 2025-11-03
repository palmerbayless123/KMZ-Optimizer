# KMZ Optimizer Architecture

This document describes the high-level architecture of the refactored KMZ Optimizer
backend. The goal of this iteration is to provide a clean separation between the
domain, service, pipeline, and API layers while keeping the codebase lightweight
and easy to extend.

## Layered Overview

```
app.py (Flask entry point)
└── kmz_optimizer/
    ├── api/         → HTTP transport concerns (Flask blueprint & app factory)
    ├── pipelines/   → Long-running orchestration logic
    ├── services/    → Stateless domain services (CSV ingestion, KMZ export, …)
    ├── core/        → Domain models & custom exceptions
    └── utils/       → Shared helper functions
```

Each layer depends only on the layer(s) below it. For example, services consume
`core` models and `utils`, but never touch Flask directly. The pipeline composes
services into an end-to-end flow, and the API simply invokes the pipeline.

## Domain Models (`kmz_optimizer/core`)

* `CsvLocation` – canonical representation of a row from Placer.ai exports.
* `KmzPlacemark` – lightweight description of placemarks parsed from KMZ files.
* `LocationBundle` – container for grouped CSV/KMZ objects for future expansion.
* `KmzMetadata` – stores state- and date-related metrics required by KMZ export.
* `ProcessingSummary` – result object returned to API consumers after a job.
* `ProcessingError` – base exception for recoverable domain failures.

## Services (`kmz_optimizer/services`)

Each service exposes a minimal, cohesive responsibility:

| Service | Responsibility |
|---------|----------------|
| `CSVIngestor` | Validates headers and converts CSV rows into `CsvLocation` objects. |
| `KmzLoader` | Parses KMZ archives and extracts placemarks. |
| `LocationMatcher` | Performs geospatial matching to reconcile CSV & KMZ entries. |
| `CountyEnricher` | Normalizes county metadata attached to locations. |
| `DataMerger` | Aggregates locations and computes KMZ metadata (counts, ranges). |
| `KmzExporter` | Builds doc.kml files and wraps them as KMZ archives. |

Services are stateless, making them trivial to unit test and compose.

## Pipeline (`kmz_optimizer/pipelines`)

`JobPipeline` orchestrates the full workflow:

1. Load CSV files (`CSVIngestor`).
2. Enrich county data (`CountyEnricher`).
3. Compute metadata (`DataMerger`).
4. Optionally parse the user-provided KMZ for future reconciliation (`KmzLoader` + `LocationMatcher`).
5. Export the consolidated KMZ (`KmzExporter`).

The pipeline exposes a `default()` constructor to quickly instantiate the standard
service stack while keeping dependency injection flexible for testing.

## API (`kmz_optimizer/api`)

* `app_factory.create_app()` – standard Flask application factory that registers CORS,
  configures payload size limits, and exposes the health endpoint.
* `routes.api_bp` – blueprint implementing `/api/jobs` (create processing job) and
  `/api/jobs/<id>` (retrieve job status/summary).

Uploads are persisted in job-specific directories under `uploads/<job_id>` and
output KMZ files are written to `outputs/<job_id>/<job_id>.kmz`.

## Storage & Configuration (`kmz_optimizer/config.py`)

Configuration is centralized in dataclasses (`AppConfig` and `StoragePaths`). Paths
are resolved from environment variables (`KMZ_OPTIMIZER_UPLOADS`, `KMZ_OPTIMIZER_OUTPUTS`)
or fallback to local directories.

## Extensibility

* **Front-end integration** – the API blueprint is intentionally minimal, ready to be
  wrapped by any UI (including Lovable) that can upload CSV/KMZ files and poll job
  status.
* **Alternate persistence** – replace `JobPipeline.default()` with dependency-injected
  implementations (e.g., S3 storage, async queues) without touching the API.
* **Additional analytics** – extend `DataMerger` to compute richer metadata; the
  `ProcessingSummary` model guarantees a predictable shape for responses.

## Removal of Legacy Code

Previous single-file modules (`csv_parser.py`, `kmz_parser.py`, `location_matcher.py`,
`data_merger.py`, `county_lookup.py`, `kmz_generator.py`) have been replaced with
modular services described above. This eliminates duplicate logic, centralizes error
handling, and reduces coupling between the Flask app and processing logic.

## Testing Considerations

* Unit tests can target each service independently with synthetic data.
* Integration tests can instantiate `JobPipeline.default()` and assert against the
  generated KMZ files written to a temporary directory.

## Frontend Next Steps (Lovable)

1. Generate a Lovable project using the API endpoints described in this document.
2. Implement multi-file upload (CSV + optional KMZ) and display job summaries.
3. Provide download links to generated KMZ files located under `/outputs/<job_id>/`.
