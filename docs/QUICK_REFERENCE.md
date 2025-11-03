# Quick Reference

A condensed list of commands and URLs for operating the KMZ Optimizer backend on
Railway and coordinating with the Lovable frontend.

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
redis-server  # or: docker run -p 6379:6379 redis:7
python app.py
rq worker kmz-optimizer
```

Smoke test:
```bash
curl -F "csv_files=@path/to/sample.csv" http://localhost:5000/api/jobs
```

## Railway Management

| Action | Command / Location |
|--------|--------------------|
| View logs | Railway dashboard → Service → Logs |
| Trigger deploy | Service → Deployments → Trigger Deploy |
| Restart service | Service → Settings → Restart |
| Update variables | Service → Variables |
| Attach volume | Service → Settings → Volumes |

## Environment Variables

| Variable | Notes |
|----------|-------|
| `FLASK_ENV=production` | Disables debug mode. |
| `REDIS_URL=<redis connection>` | Shared between web and worker services. |
| `KMZ_OPTIMIZER_UPLOADS=/app/uploads` | Location of incoming files. |
| `KMZ_OPTIMIZER_OUTPUTS=/app/outputs` | Location of generated KMZ packages. |

## Worker Operations

Start an ad-hoc worker using the Railway shell:
```bash
rq worker kmz-optimizer
```

Check job states using the RQ dashboard (optional add-on) or by polling the API:
```bash
curl https://<domain>/api/jobs/<job_id>
```

## Lovable Frontend Integration

- Base URL: `https://<domain>` (replace with Railway domain).
- Upload endpoint: `POST /api/jobs` with `multipart/form-data`.
- Status polling: `GET /api/jobs/<job_id>`.
- Download link: `/outputs/<job_id>/<job_id>.kmz`.

## Troubleshooting Cheatsheet

| Symptom | Quick Fix |
|---------|-----------|
| `Job not found` | Confirm worker is running and Redis URL matches on both services. |
| `502 Bad Gateway` | Wait for warm-up or redeploy; check logs for stack trace. |
| Files missing | Ensure volumes are mounted and directory permissions allow writes. |
| CORS errors | Verify `flask-cors` is enabled and Lovable origin is allowed if restricted. |

## Useful Links

- Railway docs: <https://docs.railway.app/>
- RQ docs: <https://python-rq.org/>
- Lovable docs: <https://docs.lovable.dev/> *(adjust based on official URL)*

Keep this reference handy for day-to-day operations and handoffs.
