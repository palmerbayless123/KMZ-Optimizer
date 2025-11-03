# KMZ Optimizer

The KMZ Optimizer processes Placer.ai CSV exports into a production-ready KMZ
package. The service exposes a lightweight Flask API backed by Redis Queue so
long-running work executes outside of the request cycle. This repository now
ships with a Railway deployment configuration and a Lovable-oriented frontend
integration plan.

## Features

- CSV validation and ingestion with automatic character encoding detection.
- KMZ parsing, reconciliation, and export using a composable pipeline.
- Redis Queue powered background processing to keep the API responsive.
- Ready-to-deploy configuration for [Railway](https://railway.app/).
- Frontend integration guidance for building a Lovable interface.

## Project Layout

```
KMZ-Optimizer/
├── app.py                  # Flask entry point
├── kmz_optimizer/          # Application package
│   ├── api/                # Flask blueprint & app factory
│   ├── core/               # Domain models and exceptions
│   ├── pipelines/          # Orchestrated processing pipeline
│   ├── services/           # CSV/KMZ business logic
│   └── utils/              # Shared helpers
├── requirements.txt        # Python dependencies
├── Procfile                # Railway process definitions
├── runtime.txt             # Python runtime pin for Railway
├── ARCHITECTURE.md         # Backend architecture documentation
├── FRONTEND_LOVABLE_PLAN.md# Frontend build plan
└── docs/                   # Deployment playbooks (see below)
```

## Getting Started Locally

1. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
3. **Run Redis** – either locally (`redis-server`) or via Docker:
   ```bash
   docker run -p 6379:6379 redis:7
   ```
4. **Start the web server**
   ```bash
   python app.py
   ```
5. **Start the worker** (in another terminal)
   ```bash
   rq worker kmz-optimizer
   ```
6. Upload CSV/KMZ files using the `/api/jobs` endpoint. A simple smoke test:
   ```bash
   curl -F "csv_files=@tests/fixtures/sample.csv" http://localhost:5000/api/jobs
   ```

Generated files appear in `outputs/<job_id>/<job_id>.kmz`.

## Deploying on Railway

Railway automatically provisions infrastructure when the repository is connected.
This project includes the required manifest files (`requirements.txt`, `Procfile`,
`runtime.txt`). Review `docs/RAILWAY_DEPLOYMENT_GUIDE.md` for the step-by-step
workflow covering:

- Connecting the GitHub repository.
- Configuring environment variables (e.g., `FLASK_ENV=production`, `REDIS_URL`).
- Running both the `web` and `worker` services.
- Validating the `/health` endpoint and job lifecycle.

### Environment Variables

| Variable | Purpose | Suggested Value |
|----------|---------|-----------------|
| `FLASK_ENV` | Enables production mode | `production` |
| `PORT` | Provided by Railway; no manual change required | *(auto)* |
| `REDIS_URL` | Redis connection string | *(from Railway Redis add-on)* |
| `KMZ_OPTIMIZER_UPLOADS` | Override uploads directory | `/app/uploads` |
| `KMZ_OPTIMIZER_OUTPUTS` | Override outputs directory | `/app/outputs` |

Mount a Railway volume at `/app/uploads` and `/app/outputs` to persist data
between deploys.

## Frontend Integration (Lovable)

The backend is tailored for a Lovable-built UI. `FRONTEND_LOVABLE_PLAN.md`
provides detailed screen flows, API usage, and UX tips. Configure the frontend’s
API base URL with the Railway domain, then wire the endpoints:

- `POST /api/jobs` – Upload CSV files (and optional KMZ) to create a job.
- `GET /api/jobs/<job_id>` – Poll for progress and fetch results.
- `/outputs/<job_id>/<job_id>.kmz` – Download the generated KMZ asset.

## Additional Documentation

All deployment playbooks and checklists live under `docs/`:

- `docs/RAILWAY_DEPLOYMENT_GUIDE.md` – End-to-end Railway deployment manual.
- `docs/DEPLOYMENT_CHECKLIST.md` – Interactive checklist for go-live.
- `docs/QUICK_REFERENCE.md` – Command cheatsheet for operations.
- `docs/RAILWAY_LOVABLE_NEXT_STEPS.md` – Conversation-ready activation guide.

These documents are designed for non-expert operators and can be surfaced to an
LLM assistant for guided walkthroughs.

## Contributing

1. Fork the repository and create a feature branch.
2. Run `python -m compileall .` to ensure there are no syntax errors.
3. Submit a pull request describing the change and tests performed.

## License

This project is provided under the MIT License. See `LICENSE` if present or add
one that suits your deployment requirements.
