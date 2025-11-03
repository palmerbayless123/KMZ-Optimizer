# Deployment Checklist

Use this checklist to track progress when shipping the KMZ Optimizer backend to
Railway and connecting the Lovable frontend.

## Pre-Deployment

- [ ] Git repository contains the latest backend code.
- [ ] `.env` values copied into Railway variables (see below).
- [ ] Redis database provisioned (Railway add-on or external).
- [ ] Sample CSV file available for smoke testing.

## Railway Project Setup

- [ ] Project created from the GitHub repository.
- [ ] `web` service online (runs `python app.py`).
- [ ] `worker` service online (runs `rq worker kmz-optimizer`).
- [ ] `REDIS_URL` variable set on both services.
- [ ] `FLASK_ENV=production` added.
- [ ] `KMZ_OPTIMIZER_UPLOADS=/app/uploads` added.
- [ ] `KMZ_OPTIMIZER_OUTPUTS=/app/outputs` added.
- [ ] Volume attached at `/app/uploads` (and optionally `/app/outputs`).

## Verification

- [ ] `/health` returns HTTP 200 and `{ "status": "healthy" }`.
- [ ] Upload endpoint accepts CSV via `POST /api/jobs`.
- [ ] Job status transitions from `queued` → `started` → `finished`.
- [ ] Generated KMZ file saved under `/app/outputs/<job_id>/`.
- [ ] Worker logs confirm successful completion.

## Lovable Frontend Integration

- [ ] API base URL updated to the Railway domain.
- [ ] Upload form points to `POST /api/jobs`.
- [ ] Polling logic reads `GET /api/jobs/<job_id>` until `finished`.
- [ ] Download button links to `/outputs/<job_id>/<job_id>.kmz`.
- [ ] CORS errors resolved (if any) by updating backend or frontend settings.

## Post-Deployment

- [ ] Documented Railway domain in shared notes.
- [ ] Monitoring plan in place (e.g., periodic log review, usage checks).
- [ ] Incident response: know how to restart services from the Railway UI.
- [ ] Confirm GitHub pushes trigger automatic redeploys.

Keep this checklist updated and store it alongside project documentation so
future operators can follow the same process.
