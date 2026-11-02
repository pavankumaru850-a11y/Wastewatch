# WasteWatch dashboard

React (Vite) + react-router-dom + axios + Leaflet (map) + Recharts (analytics).
One dashboard app serves both Admin and Staff -- the backend already scopes
`/api/reports` to "own assignments only" for a STAFF token, so the same
Reports/ReportDetails pages are correct for both roles; the sidebar and the
action buttons on the details page are the only things that change per role.

## What's verified

- `npm run build` completes cleanly (checked while building this).
- Every page's data shape was checked against the actual JSON the backend
  returns (see `backend/README.md` for the curl session that produced it) --
  field names like `waste_type`, `village`, `assignment.staff_id`,
  `completion.completion_image` are not guessed.

## Not yet verified

No browser was available while building this to click through the UI, so
runtime interaction bugs (a wrong prop, a missed null-check) are more likely
here than in the backend, which was exercised directly. Test it for real
after `npm install`.

## Setup

```bash
cd dashboard
npm install
cp .env.example .env       # set VITE_API_URL if not localhost:8000
npm run dev
```

Log in with any ADMIN or STAFF account you registered against the backend
(`POST /api/auth/register` with `"role":"ADMIN"` or `"role":"STAFF"` --
there's no public staff signup form, on purpose).

## Pages

Admin: Dashboard, Reports, Report Details (verify / assign / reject / change
priority / add-to-training), Map, Users & Staff, Dataset & Training (reads
`model_versions.json` via the backend), Analytics (6 real charts off
`/api/dashboard/analytics`).

Staff: Dashboard, Assigned Reports, Report Details (Start Cleaning / Mark
Completed with photo + GPS), Map -- all automatically scoped to their own
assignments by the backend, not by hiding UI.

## Known gaps against the original spec

- No separate "Waste Types" CRUD page -- classes are configured in
  `training/data.yaml`, not through the dashboard yet.
- No Settings page yet (profile editing, notification prefs).
- Polling for new reports runs every 5 seconds on the Dashboard page only, per
  the spec's explicit allowance ("polling every 5 seconds is acceptable")  --
  not a WebSocket, and not yet on every page.
