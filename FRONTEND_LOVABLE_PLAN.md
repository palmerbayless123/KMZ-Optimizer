# Frontend Implementation Plan (Lovable)

This plan outlines the recommended steps for building the Lovable frontend that
connects to the refactored KMZ Optimizer backend.

## 1. Project Setup

1. Create a new Lovable project targeting a dashboard layout.
2. Configure an environment variable for the backend base URL (e.g., `VITE_API_BASE_URL`).
3. Add dependencies for file uploads and HTTP requests if the chosen Lovable stack
   does not provide them out of the box (for example, Axios or Fetch wrappers).

## 2. Core Screens

| Screen | Purpose | Key Elements |
|--------|---------|--------------|
| Upload Wizard | Collect CSV & optional KMZ files | Drag-and-drop zone, file list, validation messages |
| Job History | Display processed jobs | Table of summaries, download buttons |
| Job Detail | Show metadata for a single job | Date range, ranked store counts, generated file links |

## 3. API Integration

* **Create Job** – POST `/api/jobs` with multipart form data (`csv_files[]`, optional `kmz_file`).
  Handle validation errors by reading the `error` payload.
* **Job Status** – GET `/api/jobs/{job_id}` to poll for completion. The backend currently
  processes jobs synchronously but retaining polling support keeps the UI future-proof.
* **Download** – Render a direct link to `/outputs/{job_id}/{job_id}.kmz`. Expose the link only
  after a job completes.

## 4. UX Enhancements

* Preview CSV filenames before upload and allow removal from the list.
* Provide progress feedback during uploads.
* Show formatted metadata returned in the job summary (date range, store counts) in a highlighted card.
* Implement optimistic UI updates for the job list while awaiting server confirmation.

## 5. Testing Checklist

* Upload with multiple CSVs and verify that the UI displays the aggregate metadata.
* Upload with and without KMZ files to ensure optional handling works.
* Validate that invalid file extensions are rejected before hitting the API.
* Confirm download buttons link to the generated KMZ archives and handle 404s gracefully.

## 6. Deployment

1. Configure Lovable environments (development, staging, production) with the backend base URL.
2. Enable HTTPS for backend endpoints or route through a proxy to satisfy Lovable hosting requirements.
3. Add monitoring for failed upload requests to capture backend validation issues quickly.

Following this plan keeps the front-end implementation aligned with the new backend architecture
and ready for future enhancements such as background job processing or authentication layers.
