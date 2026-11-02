> v10: a trained waste/not-waste model is included in backend/models/best.pt - see TRAIN_V10.md for results and limits.

# WasteWatch — AI-Based Roadside Waste Detection & Rural Municipal Reporting

Built incrementally, module by module, each one actually run and verified
before moving to the next — per the project brief's own instruction not to
skip straight to a finished-looking demo.

## Status

| Module | Status |
|---|---|
| Dataset analysis | Done — 95 images scanned, 2 duplicates found, zero labels found |
| Annotation tool | Done — working browser tool, exports YOLO-format ZIP |
| Training pipeline | Done — `train.py`/`validate.py`/`export.py`/`dataset_manager.py`; trained waste/not-waste and item-localization models are available |
| Backend (FastAPI) | Done — auth, reports, real object-detection inference, assignment, completion, RBAC, dashboard stats, analytics, waste-type management, profile/password. Live API inference verified against SQLite (see `backend/README.md`) |
| Admin/Staff dashboard | Done — React/Vite app, builds cleanly, every page's data verified against real backend JSON. Not click-tested in a real browser (see `dashboard/README.md`) |
| Mobile app (Expo) | Done — TypeScript compiles clean, and the full Metro bundle (1448 modules) exports successfully for Android. Not tested on a real device/simulator (see `mobile/README.md`) |

## Folders

```
dataset/raw/        the 95 original images, untouched
training/            annotation → split → train → validate → export pipeline
backend/             FastAPI API (see backend/README.md)
dashboard/           React admin/staff web dashboard (see dashboard/README.md)
mobile/               Expo citizen app (see mobile/README.md)
```

## Quickest path to a working end-to-end demo right now

1. Run the backend (`backend/README.md`).
2. Run the dashboard (`dashboard/README.md`), log in as an Admin or Staff
   account you registered via the API.
3. Run the mobile app (`mobile/README.md`) with `EXPO_PUBLIC_API_URL`
   pointed at the backend (LAN IP or an `ngrok http 8000` URL — never
   localhost), log in as a Citizen, capture a report.
4. Watch it land in the dashboard's Reports page and Dashboard stat cards
   within 5 seconds (polling).
5. Assign it to staff, mark it in-progress and completed from the
   dashboard (or build the equivalent staff flows on mobile later) — the
   citizen's report status updates in the mobile app's My Reports screen.

The active model now returns item bounding boxes using the existing annotations. Its held-out test set is very small (11 images / 10 objects), so recall and localization quality need improvement with more labeled examples before operational use. The previous whole-photo waste/not-waste classifier remains available at `backend/models/versions/waste-not-waste-v2.pt`. To improve the detector with more annotated data:

1. Use the annotation tool (published artifact link, earlier in this
   conversation) to label some of the 95 images.
2. `training/dataset_manager.py split` → `training/train.py` → copy
   `best.pt` into `backend/models/` (or `training/export.py --deploy`
   does this for you).
3. Restart the backend to load the newly deployed model.

## What was verified vs. not, honestly

Every module's own README says exactly what was tested and how (curl
sessions for the backend, `npm run build` for the dashboard, `tsc` +
a full Metro bundle export for mobile) and what wasn't (no browser or
physical device was available in this environment, so UI interaction bugs
are more likely than the logic bugs that static checks and API tests catch).

---
## WasteWatch v2 — quick start
Full details: `docs/deployment.md`. What changed and what is verified: `docs/UPGRADE_V2.md`. Demo script: `docs/DEMO_WALKTHROUGH.md`.

**Backend (Windows)**
```
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env            (set SECRET_KEY to a random 32+ character string)
python -m app.seed                (DEVELOPMENT ONLY: prints admin/staff/citizen logins once)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
**Dashboard** `cd dashboard && npm install && npm run dev` (set `VITE_API_URL` in `dashboard/.env`).
**Mobile** `cd mobile && npm install && npx expo start` (set `EXPO_PUBLIC_API_URL` in `mobile/.env`; use an HTTPS URL to work from any network).
**Docker (PostgreSQL)** `copy .env.example .env`, fill it in, `docker compose up --build`.
**Tests** `cd backend && python -m pytest tests` · `cd training && python -m pytest tests` · `cd mobile && npm test`.
**AI training** `docs/ai-training.md` (a trained item detector and binary classifier are included; add labeled data and retrain for better coverage).

| Folder | Contents |
|---|---|
| `backend/` | FastAPI API, services, config, tests |
| `dashboard/` | React admin + staff dashboard |
| `mobile/` | Expo citizen app |
| `training/` | dataset tools, train, evaluate, export |
| `e2e/` | one-command browser test of the full workflow |
| `docs/` | architecture, API, AI training, deployment, demo script |
