# MCA demonstration walkthrough (about 12 minutes)

## Before you start
```
cd backend && python -m app.seed          # note the three printed logins (development only)
uvicorn app.main:app --host 0.0.0.0 --port 8000
cd dashboard && npm run dev               # http://localhost:5173
cd mobile && npx expo start               # phone must reach EXPO_PUBLIC_API_URL
```
The active detector returns waste-item bounding boxes. Install the backend requirements before starting the API. Its held-out test set is only 11 images (10 labeled objects), with recall 0.389 and mAP50 0.376; describe these results and their uncertainty honestly. More labeled data is needed before operational use. Detection should only be described as unavailable if model/runtime loading actually fails; do not fake results.

## Rehearse the workflow without a model
`cd e2e && python run_e2e.py` replays the whole admin/staff workflow in a browser against a stand-in detector and leaves screenshots you can use in slides (see `e2e/README.md`). It does **not** replace a real model for the live demo.

## Script
1. **Problem + architecture (1 min).** Show the diagram in `architecture.md`: phone -> API -> AI/database; three roles.
2. **Citizen report (3 min, phone).** Log in as the citizen -> Detect Roadside Waste -> photograph waste -> location appears with accuracy -> Detect Waste -> boxes, confidence, object count, model version, severity, priority -> Confirm & Submit. Show a blurry photo being refused ("Image quality is too low").
3. **Offline (1 min).** Airplane mode -> capture -> "Saved offline / Pending Sync" -> Pending Uploads screen -> airplane mode off -> it syncs by itself and shows Synced. Explain the idempotency key (no duplicate reports on retry).
4. **Staff review (2 min, dashboard).** Log in as staff -> dedicated Staff dashboard (tasks, review queue, critical, nearby by GPS) -> open the report -> confirm/correct the AI class -> Verify. Show the duplicate panel (Confirm / Not duplicate / Merge) and the Hotspots page (severity colours, timeline).
5. **Assignment and cleanup (2 min).** Admin assigns staff -> staff Start cleanup -> optional before photo -> after photo + remarks -> "AI count: N before -> M after, improvement X %".
6. **Separation of duties (30 s).** The same staff member sees "you cannot sign off your own work"; log in as a second staff member (or admin) -> Approve & close.
7. **Admin (2 min).** Dashboard cards, Map (clusters + layers), Analytics charts, Audit log (old/new values), System & AI Models (thresholds, scoring rules, model activation, metrics), Export CSV/Excel/PDF.
8. **Honesty slide (1 min).** What is measured (test-set metrics from `evaluation.json`), what is a design choice (severity/priority weights), what is not done (see limitations).

## Questions to prepare for
* *"What is the accuracy?"* -> quote `evaluation.json` test-split numbers with the image count and dataset version; nothing else.
* *"How are severity and priority computed?"* -> `architecture.md` scoring section; all weights are in `severity_config.json` and editable; they are design choices, not learned.
* *"How do you avoid duplicate reports?"* -> distance + time gates, then image hash or same category within 10 m; flagged not deleted; staff decide.
* *"What if the model is wrong?"* -> confidence levels, low-confidence warnings, staff verification before any action, corrected labels can be added to the training set.
* *"Can a citizen make themselves admin?"* -> No (was possible in the original code; fixed) - staff/admin accounts are created by an admin.
* *"What about privacy?"* -> photos may contain people/plates, retention policy needed, reverse geocoding is opt-in.
