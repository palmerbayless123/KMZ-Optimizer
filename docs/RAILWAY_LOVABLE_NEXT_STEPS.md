# Railway + Lovable Next Steps (LLM Script)

This document is optimized for conversational assistants. Paste the numbered
steps into a new chat to guide an amateur operator through activating the KMZ
Optimizer backend on Railway and wiring it to a Lovable frontend.

## Conversation Goals

1. Confirm the backend is live on Railway.
2. Validate that CSV uploads succeed and the worker processes jobs.
3. Point the Lovable frontend to the production API.
4. Share follow-up habits (monitoring, redeploying, troubleshooting).

## Script Outline

1. **Warm Welcome & Context**
   - "Hi! I'm here to help you launch your KMZ Optimizer. We'll deploy the
     backend on Railway and hook up your Lovable frontend. Ready to begin?"

2. **Check Prerequisites**
   - Ask if they already have a Railway account and GitHub repo fork.
   - If not, provide the signup links:
     - Railway: <https://railway.app>
     - Repo: `https://github.com/palmerbayless123/kmz-optimizer`
   - Confirm they can access a Redis database (Railway add-on recommended).

3. **Create the Railway Project**
   - Guide them to click **New Project → Deploy from GitHub repo**.
   - Ensure they select their fork and wait for the initial deploy.
   - Prompt them to note the generated domain (e.g.
     `https://something.up.railway.app`).

4. **Attach Redis & Configure Variables**
   - "Let's add Redis now. Click `New → Database → Redis`."
   - After provisioning, copy the `REDIS_URL` from the integration card.
   - Set the following variables on both `web` and `worker` services:
     - `FLASK_ENV=production`
     - `REDIS_URL=<copied value>`
     - `KMZ_OPTIMIZER_UPLOADS=/app/uploads`
     - `KMZ_OPTIMIZER_OUTPUTS=/app/outputs`
   - Optional: mount a volume at `/app/uploads` so files persist.

5. **Verify Health Endpoint**
   - Ask them to run: `curl https://<domain>/health`
   - Success message should be `{ "status": "healthy" }`.
   - If not healthy, prompt them to open the Railway logs.

6. **Test File Upload**
   - Instruct them to pick a sample CSV.
   - Run: `curl -F "csv_files=@/path/to/sample.csv" https://<domain>/api/jobs`
   - Copy the returned `job_id`.
   - Poll status: `curl https://<domain>/api/jobs/<job_id>` until `status`
     becomes `finished`.
   - Celebrate success and mention the generated KMZ lives under
     `/app/outputs/<job_id>/<job_id>.kmz`.

7. **Wire Up Lovable**
   - In the Lovable project settings locate the environment variables screen.
   - Set `VITE_API_BASE_URL` (or equivalent) to the Railway domain.
   - Instruct them to rebuild/publish the Lovable site and test uploads from the
     UI.

8. **Daily Operations Tips**
   - Check Railway logs after each big batch upload.
   - Trigger redeploys by pushing to GitHub.
   - Use the `docs/DEPLOYMENT_CHECKLIST.md` for future launches.

9. **Troubleshooting Prompts**
   - If a job stays `queued`, ensure the worker service is running.
   - If uploads fail immediately, verify the CSV file extension and size.
   - If the frontend reports CORS errors, confirm `flask-cors` is enabled (it is
     by default) and that they are calling the `/api/...` routes.

10. **Closing the Conversation**
    - Summarize: "Your backend is live, jobs finish successfully, and the
      frontend is pointing to the production API."
    - Offer follow-up assistance: "Need help adding monitoring or analytics?"

## Supporting Links

- Full deployment manual: `docs/RAILWAY_DEPLOYMENT_GUIDE.md`
- Checklist: `docs/DEPLOYMENT_CHECKLIST.md`
- Quick commands: `docs/QUICK_REFERENCE.md`
- Lovable build plan: `FRONTEND_LOVABLE_PLAN.md`

Reuse this script whenever you need to onboard a new teammate or re-explain the
activation process to yourself.
