# Railway Deployment Guide

This guide walks through deploying the KMZ Optimizer backend to
[Railway](https://railway.app/). It assumes you already forked the repository
and have a Redis instance available (Railway can provision one in a single
click).

---

## 1. Prerequisites

- Railway account with the GitHub integration enabled.
- Fork of `palmerbayless123/kmz-optimizer` in your own GitHub namespace.
- Redis database (Railway add-on or external).
- Credit card on file with Railway to unlock the free tier allowance.

Optional but recommended:
- Railway volume to persist uploaded CSVs and generated KMZ files.

---

## 2. Repository Checklist

Ensure the following files are present at the repository root:

| File | Purpose |
|------|---------|
| `requirements.txt` | Declares Flask, Redis, and RQ dependencies. |
| `Procfile` | Defines the `web` and `worker` processes. |
| `runtime.txt` | Pins Python to version 3.11.5. |
| `.gitignore` | Excludes transient directories (uploads, outputs, env files). |
| `app.py` | Flask entry point configured to read Railway's `PORT`. |
| `README.md` | Highlights deployment and Lovable integration steps. |

The repository should already contain these files after applying the current
change set.

---

## 3. Create the Railway Project

1. Log in to Railway and click **New Project** → **Deploy from GitHub repo**.
2. Authorize GitHub (if prompted) and select your fork of the repository.
3. Railway will clone the repo, detect the Python project, and install
   dependencies from `requirements.txt`.
4. During the first deploy Railway creates a default `web` service.

### Add the Worker Service

1. Navigate to the project dashboard.
2. Click **New Service** → **Deploy from Repo** and choose the same repository.
3. When prompted for the `Deploy` command, keep the default but set the service
   type to **Background Worker**.
4. Railway reads the `Procfile` and creates both the `web` and `worker`
   processes automatically. Confirm that two tabs appear in the project view.

---

## 4. Configure Environment Variables

From the project dashboard select **Variables** and add the following keys:

| Variable | Description | Example |
|----------|-------------|---------|
| `FLASK_ENV` | Enables production mode in `app.py`. | `production` |
| `REDIS_URL` | Connection string for the Redis database. | `redis://default:password@host:port/0` |
| `KMZ_OPTIMIZER_UPLOADS` | Directory for uploaded CSV/KMZ files. | `/app/uploads` |
| `KMZ_OPTIMIZER_OUTPUTS` | Directory for generated KMZ packages. | `/app/outputs` |

If you provision a Redis add-on inside Railway the dashboard exposes the URL as
`REDIS_URL` by default. The application automatically falls back to
`RAILWAY_REDIS_URL` or the local development default when unset.

### Volumes (Optional but Recommended)

1. In the service view select **Settings → Volumes**.
2. Add a volume mounted at `/app/uploads` with size ≥1 GB.
3. (Optional) Add another volume for `/app/outputs` or reuse the same one.
4. Redeploy after attaching volumes so the directories become writable.

---

## 5. Trigger a Deployment

Railway redeploys automatically whenever you push to the tracked Git branch.
To force a redeploy, click **Deployments → Trigger Deploy**.

Deployment steps performed by Railway:

1. Install dependencies from `requirements.txt`.
2. Run the start command from the `Procfile` (`web: python app.py`).
3. Expose the app on the generated domain (e.g.,
   `https://kmz-optimizer-production.up.railway.app`).
4. Spin up the worker process to execute queued jobs (`rq worker kmz-optimizer`).

---

## 6. Verify the Deployment

Use the automatically generated domain in the following checks:

```bash
# Health check
curl https://<your-domain>/health

# Upload sample CSV (replace sample.csv with a real file)
curl -F "csv_files=@sample.csv" https://<your-domain>/api/jobs

# Poll job status
curl https://<your-domain>/api/jobs/<job_id>
```

Successful responses:

- `/health` → `{ "status": "healthy" }`
- `/api/jobs` → HTTP 202 with `job_id`
- `/api/jobs/<job_id>` → HTTP 200 with `status` of `queued`, `started`,
  `finished`, or `failed`

When a job finishes the resulting KMZ file is stored under
`/app/outputs/<job_id>/<job_id>.kmz`. Expose this directory via a CDN or direct
file serving if needed.

---

## 7. Frontend Updates

Update the Lovable frontend to call the Railway-hosted API:

```javascript
const API_URL = 'https://<your-domain>';
```

All API endpoints are namespaced under `/api`. Remember to enable CORS in the
Lovable environment if it supports custom headers.

---

## 8. Monitoring & Maintenance

- **Logs**: Railway dashboard → your service → **Logs**.
- **Usage**: Keep an eye on the free credit in **Usage**. Typical monthly cost
  is under the included $5.
- **Scaling**: Use **Settings → Scaling** to add replicas if concurrency grows.
- **Backups**: Download processed KMZ files periodically if you do not mount a
  persistent volume.

---

## 9. Troubleshooting

| Issue | Fix |
|-------|-----|
| `Job not found` when polling | Ensure both `web` and `worker` services share the same Redis (`REDIS_URL`). |
| `502 Bad Gateway` | Wait for warm-up, review logs, confirm `PORT` env var is not overridden. |
| Worker crashes with `ConnectionError` | Redis add-on may be sleeping; restart the worker or upgrade your plan. |
| Files lost after redeploy | Attach a Railway volume for `/app/uploads` and `/app/outputs`. |

---

## 10. Redeploying Updates

1. Commit your code changes locally.
2. Push to the tracked branch on GitHub.
3. Railway detects the push and redeploys automatically.
4. Verify `/health` and execute a smoke test upload.

Congratulations! Your KMZ Optimizer backend now runs on Railway with persistent
job processing handled by Redis Queue.
