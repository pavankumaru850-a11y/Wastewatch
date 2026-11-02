# WasteWatch architecture

```
 Citizen phone (Expo / React Native)          Staff + Admin (React dashboard, one app, role-based)
   camera / gallery / GPS / offline queue            reports, map, hotspots, duplicates, analytics, settings
              \                                         /
               +----------- HTTPS + JWT (REST) --------+
                                   |
                           FastAPI backend  (backend/app)
        routers -> services -> models        RBAC enforced here, not in the UI
        |            |             |
   quality gate   scoring      workflow state machine, audit log, notifications
   AI detector    duplicates   hotspots, cleanup verification, exports, analytics
        |            |
   YOLO model    SQLite (dev) / PostgreSQL (docker)      uploads/{reports,before,after}
```

## Backend layout (`backend/app`)
| Folder / file | Responsibility |
|---|---|
| `routers/` | HTTP only: auth, reports, detection, hotspots, duplicates, analytics, admin, staff, notifications, sync, training |
| `services/` | All rules: `report_service` (the pipeline), `quality_service`, `detection_service`, `scoring_service` (severity/priority/confidence), `similarity_service` (dHash), `duplicate_service`, `hotspot_service`, `workflow_service`, `notification_service`, `audit_service`, `geocode_service`, `export_service` |
| `detector.py` | Lazy YOLO loader; version tracking; hot-swap on admin activation |
| `config.py` + `config/*.json` | Tunable settings (DB overrides JSON defaults) and the scoring rules |
| `migrate.py` | Additive migration: adds new columns/indexes to an existing database, never drops data |
| `models.py`, `schemas.py` | SQLAlchemy tables / Pydantic request-response schemas |

## What happens when a citizen submits a report (`report_service.create_report`)
1. Validate coordinates; return the original report if the same `client_uuid` was already stored (offline retry safety).
2. Citizen rate limit (default 60 reports/hour, admin-configurable).
3. Validate + save the image (decoded with Pillow, JPEG/PNG/WEBP only, size limit).
4. **Quality gate** (format, resolution, blur, too dark, too bright) -> if poor, the AI is skipped with "Image quality is too low".
5. **YOLO detection** (only if a model is active). If no model / nothing found the report is still stored, with no waste type.
6. Perceptual hash of the image; optional reverse geocoding (off by default).
7. **Duplicate check** and **hotspot assignment** (both flag, never delete).
8. **Severity** and **priority** are computed and stored; a cleanup deadline is derived from the priority.
9. Status becomes `AI_DETECTED` (or stays `NEW`), history + audit rows written, notifications created.

## Status workflow (`workflow_service`)
`NEW -> AI_DETECTED -> STAFF_REVIEW -> VERIFIED -> ASSIGNED -> IN_PROGRESS -> CLEANED -> CLEANUP_VERIFICATION -> CLOSED`
plus `REJECTED` (reason required) from any step before cleanup, and `CLEANUP_VERIFICATION -> IN_PROGRESS` when the cleanup is judged insufficient.
Every change goes through one function that validates the transition, checks the role, writes `status_history` and the audit log, and notifies the citizen.
**Separation of duties:** the staff member who did the cleanup cannot approve it; another staff member or an admin must.

## Scoring (all numbers live in `backend/config/severity_config.json`; editable by admins)
**Confidence level:** HIGH >= 0.75, MEDIUM >= 0.50, otherwise LOW (a LOW detection is shown as a warning, never as success).

**Severity score (0-100)** = points for object count (1 obj: 8, 3: 15, 7: 30, 15+: 55)
+ highest class weight (drainage_waste 20, general_waste 8, plastic 5, paper 3)
+ up to 20 for the share of the photo covered by detection boxes
+ up to 8 for average confidence
+ 5 per repeated report nearby (max 15) + 10 if inside a hotspot.
Levels: LOW < 30, MEDIUM >= 30, HIGH >= 55, CRITICAL >= 80.

**Priority score (0-100)** = 100 x weighted sum of normalised factors: quantity 25 %, severity 30 %, drainage involvement 15 %, repeat reports 10 %, hotspot size 10 %, confidence 10 %.
Levels: LOW 0-30, MEDIUM 31-60, HIGH 61-80, CRITICAL 81-100. Cleanup deadline: CRITICAL 6 h, HIGH 24 h, MEDIUM 72 h, LOW 168 h.

These weights are **design choices of this project, not validated values**. Say so in the viva, show the breakdown, and tune them with the municipality's input.

## Duplicate detection
Candidate = another open report within `duplicate_distance_m` (50 m) and `duplicate_time_window_hours` (7 days).
It is flagged only if there is real evidence of "same thing": the photos are perceptually similar (dHash Hamming distance <= 10 of 64) **or** it is the same category from practically the same spot (<= `duplicate_close_distance_m`, 10 m).
Category alone is deliberately not enough (only four categories exist). Staff then confirm, dismiss or merge; merging closes the newer report as a duplicate of the older one and keeps all evidence.

## Hotspots
When at least `hotspot_min_reports` (3) non-rejected reports fall within `hotspot_radius_m` (100 m) of a hotspot centre, a hotspot is created/updated with total reports, dominant waste type, worst severity, max priority, cleanup count and a timeline of reports and status changes. Colours: green LOW, yellow MEDIUM, orange HIGH, red CRITICAL.

## Data model (tables)
`users`, `waste_reports` (+ `detections` per box), `hotspots`, `duplicate_checks`, `status_history`, `staff_assignments`, `completion_reports`, `cleanup_verifications` (before/after counts + improvement %), `notifications`, `audit_logs` (old/new value + IP), `system_settings`, `model_versions`, `verifications`, `training_images`, `waste_types`.
Indexed: latitude+longitude, created_at, status, severity, priority score, waste type.
There is no server-side `sync_queue` table: the mobile queue lives on the phone and is made safe by the `client_uuid` idempotency key (`POST /api/sync/status` lets the app check what the server already has).

## Security summary
Password hashing (bcrypt), JWT with expiry, role checks on every endpoint, login rate limit (10 failures / 5 min / IP), citizen upload limit, upload validation by decoding the bytes, CORS from config, secrets only in `.env`, production refuses a weak `SECRET_KEY`, public registration can only create citizens, API docs disabled in production, errors never expose Python exceptions, audit log for security-relevant actions, CSV/Excel export escapes formula injection.
