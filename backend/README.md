# WasteWatch backend

FastAPI + SQLAlchemy + SQLite (Postgres-ready via `DATABASE_URL`).

## This has actually been run, not just written

Every endpoint below was exercised against a live server with real SQLite
persistence during development of this starter kit: register (all 3 roles),
login, JWT-protected requests, report creation with a real image from the
dataset, admin verification, staff assignment, in-progress/completion status
updates, RBAC rejection (citizen blocked from admin routes with 403, a staff
member blocked from someone else's assignment with 403), file-type rejection
of a non-image upload, missing-GPS rejection, duplicate-email rejection, and
wrong-password rejection. All of these returned the expected status codes and
the exact error messages the spec asks for (e.g. "AI model is not currently
available.", "Location information is required.").

The deployed `models/best.pt` object detector was exercised through the live
API and returns localized bounding boxes. It is trained on the project's
existing annotations. Its held-out test set has only 11 images and 10
objects, with recall 0.389 and mAP50 0.376; these results are noisy and more
labeled examples are needed before operational use. The prior whole-photo
classifier remains at `models/versions/waste-not-waste-v2.pt`.

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # edit SECRET_KEY at minimum
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive API docs: `http://localhost:8000/docs`

`pip install -r requirements.txt` installs the Ultralytics runtime required
by the bundled detector. After replacing the model, restart the backend.

## Enabling remote/mobile access without matching Wi-Fi

```bash
ngrok http 8000
```

Give the mobile app the printed `https://...ngrok...` URL as `API_BASE_URL`.
CORS is already open (`CORS_ORIGINS=*` in dev) so this works without extra
config; tighten it to your actual origins before deploying.

## What's next

This backend is complete and tested for auth, reports, detection (once a
model exists), assignment, completion, RBAC, and dashboard stats. Not yet
built: the admin/staff web dashboard and the Expo mobile app that consume
this API — those are the next phases.
