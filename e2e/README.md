# End-to-end browser test

`python run_e2e.py` runs 40 checks in a real Chromium against a real backend and the built dashboard:
admin dashboard cards, report list + filters (staff, date range), CSV/Excel export, bounding boxes, duplicate review,
hotspot timeline, clustered map, analytics charts, creating a staff account, system settings, the verify -> assign ->
start cleanup -> before/after AI comparison -> second-staff approval -> closed workflow, audit log, and the phone-width layout.

**It uses a stand-in for YOLO** (`run_demo.py`) because no model is trained yet; everything else is the real code.
It therefore proves the application workflow, not detection quality. Map tiles / web fonts need internet access.
Setup: `pip install -r ../backend/requirements.txt playwright pillow requests && playwright install chromium`.
