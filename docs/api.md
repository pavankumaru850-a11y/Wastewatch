# WasteWatch API reference

_Generated from the live OpenAPI schema by `backend/scripts/gen_api_docs.py`. In development the same data is browsable at `/docs` (Swagger) and `/openapi.json`; both are disabled when `APP_ENV=production`._

All endpoints except `/api/health`, `/`, `/api/auth/register` and `/api/auth/login` need `Authorization: Bearer <token>`.
Errors are always `{"success": false, "detail": "..."}`; raw exceptions are never returned.

## Who may call what (enforced on the server, not just hidden in the UI)

| Area | Citizen | Staff | Admin |
|---|---|---|---|
| Create report, list/read **own** reports, own notifications, `/api/sync/status` | yes | yes | yes |
| Read reports | own only | assigned + review queue + verification queue + ones they worked on | all |
| Verify / reject / start cleanup / before+after photos / complete | no | yes (own assignment) | yes |
| Approve or reopen a finished cleanup | no | yes, **but not for a cleanup they did themselves** | yes |
| Assign staff, edit report fields, export CSV/Excel | no | no | yes |
| Hotspots, duplicate review, analytics, dashboard cards | no | yes | yes |
| Users, staff creation, settings, scoring rules, AI models, audit log | no | no | yes |

_Reports are never deleted through the API: duplicates are merged/rejected and all evidence is kept for the audit trail._

## admin

| Method | Path | Summary | Query params | Body |
|---|---|---|---|---|
| GET | `/api/admin/audit-log` | Audit Log | report_id, action, user_id, limit | - |
| GET | `/api/admin/models` | List Models | - | - |
| POST | `/api/admin/models/{version}/activate` | Activate Model | - | - |
| POST | `/api/admin/reports/{report_id}/add-to-training` | Add To Training Dataset | - | - |
| POST | `/api/admin/reports/{report_id}/verify` | Verify Report | - | JSON |
| PUT | `/api/admin/scoring-config` | Put Scoring | - | JSON |
| GET | `/api/admin/settings` | Get System Settings | - | - |
| PUT | `/api/admin/settings` | Put System Settings | - | JSON |
| GET | `/api/admin/users` | List Users | role | - |
| POST | `/api/admin/users` | Create User | - | JSON |
| PUT | `/api/admin/users/{user_id}` | Update User | - | JSON |

## analytics

| Method | Path | Summary | Query params | Body |
|---|---|---|---|---|
| GET | `/api/analytics/summary` | Summary | days | - |

## auth

| Method | Path | Summary | Query params | Body |
|---|---|---|---|---|
| POST | `/api/auth/login` | Login | - | JSON |
| GET | `/api/auth/me` | Me | - | - |
| POST | `/api/auth/register` | Register | - | JSON |

## dashboard

| Method | Path | Summary | Query params | Body |
|---|---|---|---|---|
| GET | `/api/dashboard/analytics` | Analytics | - | - |
| GET | `/api/dashboard/cards` | Cards | - | - |
| GET | `/api/dashboard/cleanliness-score` | Cleanliness Score | by | - |
| GET | `/api/dashboard/hotspots` | Hotspots | min_reports | - |
| GET | `/api/dashboard/recent` | Recent | since | - |
| GET | `/api/dashboard/stats` | Stats | - | - |

## detection

| Method | Path | Summary | Query params | Body |
|---|---|---|---|---|
| POST | `/api/detection/predict` | Predict | - | multipart/form-data |

## duplicates

| Method | Path | Summary | Query params | Body |
|---|---|---|---|---|
| GET | `/api/duplicates` | List Checks | decision, report_id | - |
| POST | `/api/duplicates/{check_id}/decision` | Decide | - | JSON |

## hotspots

| Method | Path | Summary | Query params | Body |
|---|---|---|---|---|
| GET | `/api/hotspots` | List Hotspots | status | - |
| GET | `/api/hotspots/{hotspot_id}/history` | History | - | - |

## notifications

| Method | Path | Summary | Query params | Body |
|---|---|---|---|---|
| GET | `/api/notifications` | Mine | unread_only | - |
| POST | `/api/notifications/read-all` | Read All | - | - |
| POST | `/api/notifications/{nid}/read` | Mark Read | - | - |

## reports

| Method | Path | Summary | Query params | Body |
|---|---|---|---|---|
| POST | `/api/reports` | Create Report | - | multipart/form-data |
| GET | `/api/reports` | List Reports | status, waste_type, village, district, priority, severity, hotspot_id, duplicate, min_confidence, date_from, date_to, search, assigned_to, limit, offset | - |
| GET | `/api/reports/export/csv` | Export Csv | status, waste_type, severity, priority, date_from, date_to | - |
| GET | `/api/reports/export/pdf` | Export Pdf | status, waste_type, village, district, priority | - |
| GET | `/api/reports/export/xlsx` | Export Xlsx | status, waste_type, severity, priority, date_from, date_to | - |
| GET | `/api/reports/{report_id}` | Get Report | - | - |
| PUT | `/api/reports/{report_id}` | Update Report | - | JSON |
| POST | `/api/reports/{report_id}/assign` | Assign Report | - | JSON |
| POST | `/api/reports/{report_id}/before-image` | Before Image | - | multipart/form-data |
| GET | `/api/reports/{report_id}/cleanup-verification` | Get Cleanup | - | - |
| POST | `/api/reports/{report_id}/cleanup-verification` | Decide Cleanup | - | JSON |
| POST | `/api/reports/{report_id}/complete` | Complete Report | - | multipart/form-data |
| GET | `/api/reports/{report_id}/history` | Status History | - | - |
| PUT | `/api/reports/{report_id}/status` | Update Status | - | JSON |

## staff

| Method | Path | Summary | Query params | Body |
|---|---|---|---|---|
| GET | `/api/staff/summary` | My Summary | - | - |

## sync

| Method | Path | Summary | Query params | Body |
|---|---|---|---|---|
| POST | `/api/sync/status` | Sync Status | - | JSON |

## system

| Method | Path | Summary | Query params | Body |
|---|---|---|---|---|
| GET | `/` | Health | - | - |
| GET | `/api/health` | Api Health | - | - |

## training

| Method | Path | Summary | Query params | Body |
|---|---|---|---|---|
| GET | `/api/training/images` | Verified Training Images | - | - |
| GET | `/api/training/model` | Current Model | - | - |
| GET | `/api/training/model/history` | Model History | - | - |

## users

| Method | Path | Summary | Query params | Body |
|---|---|---|---|---|
| GET | `/api/users/me` | My Profile | - | - |
| PUT | `/api/users/me` | Update Profile | - | JSON |
| POST | `/api/users/me/change-password` | Change Password | - | JSON |

## waste-types

| Method | Path | Summary | Query params | Body |
|---|---|---|---|---|
| GET | `/api/waste-types` | List Waste Types | active_only | - |
| POST | `/api/waste-types` | Create Waste Type | - | JSON |
| PUT | `/api/waste-types/{waste_type_id}/activate` | Activate Waste Type | - | - |
| PUT | `/api/waste-types/{waste_type_id}/deactivate` | Deactivate Waste Type | - | - |
