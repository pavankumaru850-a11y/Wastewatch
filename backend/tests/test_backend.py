import io

from app.services import scoring_service as sc
from app.services.report_service import compare_counts
from app.services.similarity_service import dhash, hamming
from app.services import training_service
from tests.conftest import FAKE, det, login, make_image, submit


# ---------------- auth / rbac ----------------
def test_health(client):
    assert client.get("/api/health").json() == {"status": "healthy"}
    assert client.get("/docs").status_code == 200 and client.get("/openapi.json").status_code == 200


def test_register_cannot_escalate_to_admin(client):
    r = client.post("/api/auth/register", json={"name": "Evil", "email": "e@t.com", "password": "password123", "role": "ADMIN"})
    assert r.status_code == 200 and r.json()["role"] == "CITIZEN"


def test_short_password_rejected(client):
    r = client.post("/api/auth/register", json={"name": "A", "email": "z@t.com", "password": "short"})
    assert r.status_code == 422


def test_login_wrong_password_and_no_token(client):
    assert client.post("/api/auth/login", json={"email": "admin@t.com", "password": "nope"}).status_code == 401
    assert client.get("/api/reports").status_code == 401


def test_admin_only_endpoints_blocked_for_staff_and_citizen(client):
    for who in ("staff", "citizen"):
        h = login(client, who)
        assert client.get("/api/admin/users", headers=h).status_code == 403
        assert client.get("/api/admin/settings", headers=h).status_code == 403
        assert client.post("/api/admin/users", headers=h, json={"name": "x", "email": "q@t.com", "password": "password123", "role": "ADMIN"}).status_code == 403


def test_admin_creates_staff(client):
    h = login(client, "admin")
    r = client.post("/api/admin/users", headers=h, json={"name": "S", "email": "s3@t.com", "password": "password123", "role": "STAFF"})
    assert r.status_code == 201 and r.json()["role"] == "STAFF"


def test_training_dataset_summary_is_admin_only(client, tmp_path, monkeypatch):
    dataset_dir = tmp_path / "training"
    (dataset_dir / "dataset_binary_combined" / "waste").mkdir(parents=True)
    (dataset_dir / "dataset_binary_combined" / "waste" / "source.JPG").write_bytes(b"image")
    (dataset_dir / "dataset_binary_combined" / "waste" / "notes.txt").write_text("not an image")
    (dataset_dir / "dataset_cls" / "train" / "waste").mkdir(parents=True)
    (dataset_dir / "dataset_cls" / "train" / "waste" / "train.jpg").write_bytes(b"image")
    monkeypatch.setattr(training_service, "TRAINING_DATA_DIR", dataset_dir)

    assert client.get("/api/training/dataset").status_code == 401
    staff_headers = login(client, "staff")
    assert client.get("/api/training/dataset", headers=staff_headers).status_code == 403

    admin_headers = login(client, "admin")
    response = client.get("/api/training/dataset", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == {
        "available": True,
        "source": {"classes": {"waste": 1}, "total": 1},
        "splits": {
            "train": {"classes": {"waste": 1}, "total": 1},
            "val": {"classes": {}, "total": 0},
            "test": {"classes": {}, "total": 0},
        },
    }


# ---------------- scoring ----------------
def test_confidence_levels():
    assert sc.confidence_level(0.91) == "HIGH" and sc.confidence_level(0.75) == "HIGH"
    assert sc.confidence_level(0.6) == "MEDIUM" and sc.confidence_level(0.49) == "LOW"
    assert sc.confidence_level(None) is None


def test_severity_scales_with_count():
    box = {"x1": 0, "y1": 0, "x2": 10, "y2": 10}
    mk = lambda n, c="plastic": [{"class_name": c, "confidence": 0.8, "box": box} for _ in range(n)]
    low, med, high = (sc.compute_severity(mk(n)) for n in (3, 7, 15))
    assert low["level"] == "LOW" and med["level"] == "MEDIUM" and high["level"] == "HIGH"
    assert low["score"] < med["score"] < high["score"]
    assert sc.compute_severity([])["level"] == "LOW"


def test_large_repeated_drainage_is_critical():
    box = {"x1": 0, "y1": 0, "x2": 900, "y2": 900}
    d = [{"class_name": "drainage_waste", "confidence": 0.95, "box": box} for _ in range(16)]
    s = sc.compute_severity(d, repeat_count=3, in_hotspot=True, img_size=(1000, 1000))
    assert s["level"] == "CRITICAL", s
    p = sc.compute_priority(d, s["score"], repeat_count=3, hotspot_reports=6)
    assert p["level"] in ("HIGH", "CRITICAL") and 0 <= p["score"] <= 100


def test_priority_bounds():
    d = [{"class_name": "plastic", "confidence": 0.5}]
    p = sc.compute_priority(d, 10)
    assert p["level"] == "LOW" and 0 <= p["score"] <= 100


def test_cleanup_improvement_math():
    assert compare_counts(12, 2) == 83.3
    assert compare_counts(0, 3) is None
    assert compare_counts(4, 8) == -100.0


# ---------------- image similarity ----------------
def test_dhash_similarity(tmp_path):
    a, a2, b = tmp_path / "a.jpg", tmp_path / "a2.jpg", tmp_path / "b.jpg"
    from PIL import Image
    a.write_bytes(make_image(1)); b.write_bytes(make_image(99))
    with Image.open(a) as im:
        im.resize((200, 150)).save(a2, "JPEG", quality=60)  # same picture, smaller + recompressed
    assert hamming(dhash(str(a)), dhash(str(a2))) <= 10
    assert hamming(dhash(str(a)), dhash(str(b))) > 10
    assert hamming(None, "ff") is None


# ---------------- detection API / quality ----------------
def test_detection_api_shape(client):
    h = login(client, "citizen")
    FAKE["dets"] = [det("plastic", 0.91), det("paper", 0.6)]
    r = client.post("/api/detection/predict", headers=h, files={"image": ("a.jpg", make_image(2), "image/jpeg")})
    j = r.json()
    assert r.status_code == 200 and j["detected"] and j["object_count"] == 2 and j["model_version"]
    assert j["detections"][0]["bbox"] == [10.0, 10.0, 100.0, 100.0] and j["confidence_level"] == "HIGH"
    assert j["severity"] and j["priority_score"] is not None


def test_any_waste_class_is_simply_waste(client):
    h = login(client, "citizen")
    FAKE["dets"] = [det("paper", 0.8)]
    j = client.post("/api/detection/predict", headers=h, files={"image": ("a.jpg", make_image(3), "image/jpeg")}).json()
    assert j["message"] == "Waste detected" and j["is_waste"] is True and "Unsupported data" not in j["message"]


def test_no_waste_and_low_confidence_messages(client):
    h = login(client, "citizen")
    FAKE["dets"] = []
    j = client.post("/api/detection/predict", headers=h, files={"image": ("a.jpg", make_image(4), "image/jpeg")}).json()
    assert j["message"] == "No waste detected." and j["detected"] is False and j["detections"] == [] and j["is_waste"] is False
    FAKE["dets"] = [det("plastic", 0.42)]
    j = client.post("/api/detection/predict", headers=h, files={"image": ("a.jpg", make_image(4), "image/jpeg")}).json()
    assert j["code"] == "LOW_CONFIDENCE" and "Low-confidence" in j["message"]


def test_quality_gate_blurry_dark_tiny(client):
    h = login(client, "citizen")
    for img in (make_image(1, blur=True), make_image(1, dark=True), make_image(1, size=(100, 80))):
        j = client.post("/api/detection/predict", headers=h, files={"image": ("a.jpg", img, "image/jpeg")}).json()
        assert j["success"] is False and j["code"] == "IMAGE_QUALITY_LOW" and "quality is too low" in j["message"]


def test_upload_validation(client):
    h = login(client, "citizen")
    assert client.post("/api/detection/predict", headers=h, files={"image": ("a.jpg", b"not an image", "image/jpeg")}).status_code == 400
    assert client.post("/api/detection/predict", headers=h, files={"image": ("a.jpg", make_image(1, fmt="GIF"), "image/jpeg")}).status_code == 400
    assert client.post("/api/detection/predict", headers=h, files={"image": ("a.webp", make_image(5, fmt="WEBP"), "image/webp")}).status_code == 200


# ---------------- report creation ----------------
def test_report_creation_full_pipeline(client):
    h = login(client, "citizen")
    FAKE["dets"] = [det("plastic", 0.9), det("plastic", 0.8), det("paper", 0.7)]
    r = submit(client, h, seed=10, gps_accuracy="8.5")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "AI_DETECTED" and j["object_count"] == 3 and j["waste_type"] == "plastic"
    assert j["severity"] and j["priority_score"] is not None and j["gps_accuracy"] == 8.5 and j["model_version"]
    assert len(j["detections"]) == 3
    n = client.get("/api/notifications", headers=h).json()
    assert any(x["title"] == "Report submitted" for x in n)


def test_report_needs_location(client):
    h = login(client, "citizen")
    r = client.post("/api/reports", headers=h, files={"image": ("a.jpg", make_image(1), "image/jpeg")})
    assert r.status_code == 400


def test_report_saved_even_when_no_detection(client):
    h = login(client, "citizen")
    FAKE["dets"] = []
    j = submit(client, h, seed=11).json()
    assert j["status"] == "NOT_WASTE" and j["is_waste"] is False and j["object_count"] == 0 and j["waste_type"] is None  # kept, but as not-waste


def test_offline_sync_idempotent(client):
    h = login(client, "citizen")
    a = submit(client, h, seed=12, client_uuid="abc-123").json()
    b = submit(client, h, seed=12, client_uuid="abc-123").json()
    assert a["id"] == b["id"]
    assert len(client.get("/api/reports", headers=h).json()) == 1


def test_citizen_cannot_see_other_citizens_reports(client):
    a, b = login(client, "citizen"), login(client, "citizen2")
    rid = submit(client, a, seed=13).json()["id"]
    assert client.get(f"/api/reports/{rid}", headers=b).status_code == 403
    assert client.get("/api/reports", headers=b).json() == []


# ---------------- duplicates ----------------
def test_duplicate_flagged_not_deleted_and_decidable(client):
    c, s = login(client, "citizen"), login(client, "staff")
    first = submit(client, c, seed=20, lat=15.00000, lng=75.00000).json()
    second = submit(client, c, seed=20, lat=15.00010, lng=75.00010).json()  # ~15 m away, same image
    assert second["is_possible_duplicate"] is True and first["is_possible_duplicate"] is False
    assert len(client.get("/api/reports", headers=login(client, "admin")).json()) == 2  # nothing deleted
    checks = client.get("/api/duplicates", headers=s).json()
    assert len(checks) == 1 and checks[0]["distance_m"] < 30 and checks[0]["hash_distance"] == 0
    r = client.post(f"/api/duplicates/{checks[0]['id']}/decision", headers=s, json={"decision": "NOT_DUPLICATE"})
    assert r.status_code == 200 and r.json()["decision"] == "NOT_DUPLICATE"
    assert client.get(f"/api/reports/{second['id']}", headers=login(client, "admin")).json()["is_possible_duplicate"] is False
    logs = client.get("/api/admin/audit-log", headers=login(client, "admin")).json()
    assert any(l["action"] == "DUPLICATE_NOT_DUPLICATE" for l in logs)


def test_far_reports_not_duplicates_and_citizen_cannot_decide(client):
    c = login(client, "citizen")
    submit(client, c, seed=21, lat=15.0, lng=75.0)
    j = submit(client, c, seed=21, lat=15.01, lng=75.0).json()  # ~1.1 km
    assert j["is_possible_duplicate"] is False
    assert client.post("/api/duplicates/1/decision", headers=c, json={"decision": "MERGED"}).status_code == 403


def test_merge_rejects_newer_report_keeps_records(client):
    c, s = login(client, "citizen"), login(client, "staff")
    first = submit(client, c, seed=22).json()
    second = submit(client, c, seed=22, lat=15.00005).json()
    cid = client.get("/api/duplicates", headers=s).json()[0]["id"]
    assert client.post(f"/api/duplicates/{cid}/decision", headers=s, json={"decision": "MERGED"}).status_code == 200
    r = client.get(f"/api/reports/{second['id']}", headers=login(client, "admin")).json()
    assert r["status"] == "REJECTED" and r["duplicate_of_id"] == first["id"]


# ---------------- hotspots ----------------
def test_hotspot_created_after_threshold(client):
    c, s = login(client, "citizen"), login(client, "staff")
    for i in range(3):
        j = submit(client, c, seed=30 + i * 7, lat=15.0 + i * 0.0002, lng=75.0).json()  # ~22 m apart, different photos
    assert j["hotspot_id"] is not None
    hs = client.get("/api/hotspots", headers=s).json()
    assert len(hs) == 1 and hs[0]["total_reports"] == 3 and hs[0]["dominant_waste_type"] == "plastic"
    assert hs[0]["color"] in ("green", "yellow", "orange", "red")
    hist = client.get(f"/api/hotspots/{hs[0]['id']}/history", headers=s).json()
    assert len(hist["timeline"]) >= 3
    assert client.get("/api/hotspots", headers=c).status_code == 403


# ---------------- workflow ----------------
def _assigned_report(client, seed):
    c, a = login(client, "citizen"), login(client, "admin")
    rid = submit(client, c, seed=seed).json()["id"]
    sid = next(u["id"] for u in client.get("/api/admin/users?role=STAFF", headers=a).json() if u["email"] == "staff@t.com")
    r = client.post(f"/api/reports/{rid}/assign", headers=a, json={"staff_id": sid})
    assert r.status_code == 200, r.text
    return rid, c, a, login(client, "staff")


def test_invalid_transition_rejected(client):
    c, a = login(client, "citizen"), login(client, "admin")
    rid = submit(client, c, seed=40).json()["id"]
    r = client.put(f"/api/reports/{rid}/status", headers=a, json={"status": "CLOSED"})
    assert r.status_code == 400 and "Cannot move" in r.json()["detail"]


def test_reject_requires_reason(client):
    c, s = login(client, "citizen"), login(client, "staff")
    rid = submit(client, c, seed=41).json()["id"]
    assert client.put(f"/api/reports/{rid}/status", headers=s, json={"status": "REJECTED"}).status_code == 400
    assert client.put(f"/api/reports/{rid}/status", headers=s, json={"status": "REJECTED", "remarks": "not waste"}).status_code == 200


def test_full_lifecycle_with_cleanup_verification(client, monkeypatch):
    rid, c, a, s = _assigned_report(client, 50)
    assert client.get(f"/api/reports/{rid}", headers=s).json()["status"] == "ASSIGNED"
    # other staff cannot touch it
    s2 = login(client, "staff2")
    assert client.put(f"/api/reports/{rid}/status", headers=s2, json={"status": "IN_PROGRESS"}).status_code == 403
    assert client.put(f"/api/reports/{rid}/status", headers=s, json={"status": "IN_PROGRESS"}).status_code == 200
    # path-aware stub: the BEFORE image has 12 objects, the AFTER image has 2
    from app import detector
    monkeypatch.setattr(detector, "predict", lambda p, t=None: [det() for _ in range(12 if "/before/" in p else 2)])
    client.post(f"/api/reports/{rid}/before-image", headers=s, files={"image": ("b.jpg", make_image(51), "image/jpeg")})
    r = client.post(f"/api/reports/{rid}/complete", headers=s, files={"completion_image": ("a.jpg", make_image(52), "image/jpeg")}, data={"remarks": "done"})
    assert r.status_code == 200, r.text
    assert client.get(f"/api/reports/{rid}", headers=s).json()["status"] == "CLEANUP_VERIFICATION"
    cv = client.get(f"/api/reports/{rid}/cleanup-verification", headers=s).json()
    assert cv["analysis_available"] is True
    assert (cv["before_detection_count"], cv["after_detection_count"], cv["improvement_percentage"]) == (12, 2, 83.3)
    ok = client.post(f"/api/reports/{rid}/cleanup-verification", headers=a, json={"approve": True, "remarks": "verified"})
    assert ok.status_code == 200 and ok.json()["verified_by"]
    hist = client.get(f"/api/reports/{rid}/history", headers=a).json()
    assert hist["current"] == "CLOSED" and hist["allowed_next"] == []
    assert [h["new"] for h in hist["history"]][-3:] == ["CLEANED", "CLEANUP_VERIFICATION", "CLOSED"]
    titles = [n["title"] for n in client.get("/api/notifications", headers=c).json()]
    assert "Your report has been closed" in titles and "Cleanup completed" in titles


def test_cannot_complete_before_in_progress(client):
    rid, c, a, s = _assigned_report(client, 60)
    r = client.post(f"/api/reports/{rid}/complete", headers=s, files={"completion_image": ("a.jpg", make_image(61), "image/jpeg")})
    assert r.status_code == 400


def test_cleanup_without_model_never_invents_numbers(client, monkeypatch):
    from app import detector
    rid, c, a, s = _assigned_report(client, 70)
    client.put(f"/api/reports/{rid}/status", headers=s, json={"status": "IN_PROGRESS"})
    def boom(*_a, **_k): raise detector.ModelUnavailableError("no model")
    monkeypatch.setattr(detector, "predict", boom)
    assert client.post(f"/api/reports/{rid}/complete", headers=s, files={"completion_image": ("a.jpg", make_image(71), "image/jpeg")}).status_code == 200
    cv = client.get(f"/api/reports/{rid}/cleanup-verification", headers=s).json()
    assert cv["analysis_available"] is False and cv["improvement_percentage"] is None


# ---------------- notifications / settings / audit ----------------
def test_notifications_are_private(client):
    a, b = login(client, "citizen"), login(client, "citizen2")
    submit(client, a, seed=80)
    assert client.get("/api/notifications", headers=b).json() == []
    nid = client.get("/api/notifications", headers=a).json()[0]["id"]
    assert client.post(f"/api/notifications/{nid}/read", headers=b).status_code == 404
    assert client.post(f"/api/notifications/{nid}/read", headers=a).json()["is_read"] is True


def test_staff_notified_of_new_report(client):
    FAKE["dets"] = [det()]
    submit(client, login(client, "citizen"), seed=81)
    titles = [n["title"] for n in client.get("/api/notifications", headers=login(client, "staff")).json()]
    assert any(t.startswith("Waste detected") for t in titles)


def test_settings_change_takes_effect_and_is_audited(client):
    a, c = login(client, "admin"), login(client, "citizen")
    assert client.put("/api/admin/settings", headers=a, json={"bogus": 1}).status_code == 400
    assert client.put("/api/admin/settings", headers=a, json={"duplicate_distance_m": "far"}).status_code == 400
    assert client.put("/api/admin/settings", headers=a, json={"duplicate_distance_m": 5}).status_code == 200
    submit(client, c, seed=90, lat=15.0)
    j = submit(client, c, seed=90, lat=15.00010).json()  # ~11 m > 5 m now
    assert j["is_possible_duplicate"] is False
    assert any(l["action"] == "SETTING_CHANGED" for l in client.get("/api/admin/audit-log", headers=a).json())


def test_login_audited_and_no_secrets_in_log(client):
    login(client, "admin")
    logs = client.get("/api/admin/audit-log", headers=login(client, "admin")).json()
    assert any(l["action"] == "USER_LOGIN" for l in logs)
    assert "password" not in str(logs).lower()


def test_filters_and_search(client):
    c, a = login(client, "citizen"), login(client, "admin")
    FAKE["dets"] = [det("paper", 0.9)]
    submit(client, c, seed=100, lat=15.0, description="near the market")
    FAKE["dets"] = [det("plastic", 0.9)]
    submit(client, c, seed=101, lat=16.0, description="by the river")
    assert len(client.get("/api/reports?waste_type=paper", headers=a).json()) == 1
    assert len(client.get("/api/reports?search=river", headers=a).json()) == 1
    assert len(client.get("/api/reports?min_confidence=0.95", headers=a).json()) == 0
    assert len(client.get("/api/reports?duplicate=true", headers=a).json()) == 0


def test_migration_adds_missing_columns(tmp_path):
    import sqlite3, subprocess, sys, os
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE waste_reports (id INTEGER PRIMARY KEY, user_id INTEGER, image_path TEXT, latitude FLOAT, longitude FLOAT, status VARCHAR(20), priority VARCHAR(10), created_at DATETIME, updated_at DATETIME)")
    con.commit(); con.close()
    code = "from app.migrate import run_migrations; a=run_migrations(); print('ADDED', len(a), 'waste_reports.image_hash' in a)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env={**os.environ, "DATABASE_URL": f"sqlite:///{db}", "PYTHONPATH": os.getcwd()})
    assert "True" in out.stdout, out.stderr[-500:]


# ---------------- v2.1: verify via workflow, exports, cards ----------------
def test_staff_can_verify_classification_via_workflow(client):
    c, s = login(client, "citizen"), login(client, "staff")
    rid = submit(client, c, seed=110).json()["id"]
    r = client.post(f"/api/admin/reports/{rid}/verify", headers=s, json={"verification_status": "INCORRECT", "verified_class": "paper"})
    assert r.status_code == 200 and r.json()["status"] == "VERIFIED" and r.json()["waste_type"] == "paper"
    assert client.post(f"/api/admin/reports/{rid}/verify", headers=s, json={"verification_status": "CORRECT"}).status_code == 400
    assert client.post(f"/api/admin/reports/{rid}/verify", headers=c, json={"verification_status": "CORRECT"}).status_code == 403
    a = client.get("/api/admin/audit-log?action=CLASS_CORRECTED", headers=login(client, "admin")).json()
    assert a and a[0]["old_value"] == "plastic" and a[0]["new_value"] == "paper"


def test_export_csv_xlsx_admin_only_and_formula_safe(client):
    c, a, s = login(client, "citizen"), login(client, "admin"), login(client, "staff")
    submit(client, c, seed=111, description="=HYPERLINK(evil)", village="=cmd|calc")
    assert client.get("/api/reports/export/csv", headers=s).status_code == 403
    assert client.get("/api/reports/export/xlsx", headers=c).status_code == 403
    r = client.get("/api/reports/export/csv", headers=a)
    assert r.status_code == 200 and "Report ID" in r.text and "'=cmd|calc" in r.text
    x = client.get("/api/reports/export/xlsx", headers=a)
    assert x.status_code == 200 and x.content[:2] == b"PK"
    from openpyxl import load_workbook
    import io
    ws = load_workbook(io.BytesIO(x.content)).active
    assert ws.max_row == 2 and ws["A1"].value == "Report ID"


def test_dashboard_cards(client):
    c, a, s = login(client, "citizen"), login(client, "admin"), login(client, "staff")
    submit(client, c, seed=112)
    j = client.get("/api/dashboard/cards", headers=a).json()
    assert j["total_reports"] == 1 and j["todays_reports"] == 1 and j["pending_verification"] == 1 and j["avg_resolution_hours"] is None
    assert client.get("/api/dashboard/cards", headers=s).status_code == 200
    assert client.get("/api/dashboard/cards", headers=c).status_code == 403


def test_seeded_demo_accounts_can_actually_log_in(client, monkeypatch):
    """Regression: seed emails used a reserved TLD that the login validator rejected."""
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "AdminPass123")
    monkeypatch.setenv("SEED_STAFF_PASSWORD", "StaffPass123")
    monkeypatch.setenv("SEED_CITIZEN_PASSWORD", "CitizenPass123")
    from app import seed
    seed.main()
    for email, pw in (("admin", "AdminPass123"), ("staff", "StaffPass123"), ("citizen", "CitizenPass123")):
        r = client.post("/api/auth/login", json={"email": f"{email}@wastewatch.dev", "password": pw})
        assert r.status_code == 200, r.text


# ---------------- v2.3: model registry round-trip, geocoding, limits, sync, analytics ----------------
import json as _json
import pytest


@pytest.fixture()
def registry(tmp_path, monkeypatch):
    """A repo layout exactly like training/export.py produces: paths RELATIVE TO THE REPO ROOT."""
    from app import detector
    from app.services import training_service as ts
    root = tmp_path / "repo"
    (root / "backend" / "models" / "wastewatch_v1").mkdir(parents=True)
    (root / "backend" / "models" / "wastewatch_v1" / "best.pt").write_bytes(b"w")
    (root / "backend" / "models" / "wastewatch_v2").mkdir(parents=True)  # registered but weights missing
    reg = root / "backend" / "models" / "model_versions.json"
    entries = [
        {"model_name": "wastewatch-yolo", "version": "v1", "path": "backend/models/wastewatch_v1/best.pt", "map50": 0.6, "precision": .7, "recall": .5, "map5095": .3, "dataset_version": "abc"},
        {"model_name": "wastewatch-yolo", "version": "v2", "path": "backend/models/wastewatch_v2/best.pt", "map50": 0.7},
        {"model_name": "wastewatch-yolo", "version": "v3", "path": "backend/models/wastewatch_v1/best.pt", "map50": None},
    ]
    reg.write_text(_json.dumps(entries))
    monkeypatch.setattr(ts, "REPO_ROOT", root)
    monkeypatch.setattr(ts, "MODEL_VERSIONS_FILE", reg)
    saved = (detector.MODEL_PATH, detector._active_version, detector._model, detector._load_error)
    yield root
    detector.MODEL_PATH, detector._active_version, detector._model, detector._load_error = saved


def test_model_activation_roundtrip_with_export_layout(client, registry, monkeypatch):
    from app import detector
    a, c = login(client, "admin"), login(client, "citizen")
    models = client.get("/api/admin/models", headers=a).json()
    assert [m["version"] for m in models] == ["v1", "v2", "v3"] and not any(m["active"] for m in models)
    monkeypatch.setattr(detector, "_load_model", lambda: None)
    monkeypatch.setattr(detector, "is_available", lambda: True)
    assert client.post("/api/admin/models/v1/activate", headers=a).json() == {"active": "v1"}
    assert detector.active_version() == "v1" and str(detector.MODEL_PATH).endswith("wastewatch_v1/best.pt")
    assert next(m for m in client.get("/api/admin/models", headers=a).json() if m["version"] == "v1")["active"] is True
    j = client.post("/api/detection/predict", headers=c, files={"image": ("a.jpg", make_image(200), "image/jpeg")}).json()
    assert j["model_version"] == "v1"  # real active version, not a config label
    assert any(l["action"] == "MODEL_ACTIVATED" for l in client.get("/api/admin/audit-log", headers=a).json())
    assert any(n["title"] == "AI model changed" for n in client.get("/api/notifications", headers=a).json())


def test_model_activation_refusals(client, registry, monkeypatch):
    from app import detector
    a = login(client, "admin")
    assert client.post("/api/admin/models/nope/activate", headers=a).status_code == 404
    assert client.post("/api/admin/models/v2/activate", headers=a).status_code == 400  # file missing
    assert client.post("/api/admin/models/v3/activate", headers=a).status_code == 400  # no metrics
    assert client.post("/api/admin/models/v1/activate", headers=login(client, "staff")).status_code == 403
    before = detector.active_version()
    monkeypatch.setattr(detector, "_load_model", lambda: None)
    monkeypatch.setattr(detector, "is_available", lambda: False)  # weights that will not load
    r = client.post("/api/admin/models/v1/activate", headers=a)
    assert r.status_code == 400 and "not activated" in r.json()["detail"]
    assert detector.active_version() == before  # rolled back


def test_active_model_restored_after_restart(client, registry):
    from app import detector
    from app.database import SessionLocal
    from app.main import on_startup
    from app.models import ModelVersion
    p = registry / "backend" / "models" / "wastewatch_v1" / "best.pt"
    db = SessionLocal(); db.add(ModelVersion(model_name="w", version="v9", path=str(p), deployed=True)); db.commit(); db.close()
    on_startup()
    assert detector.active_version() == "v9" and detector.MODEL_PATH == p


def test_no_active_model_reports_no_version_on_unavailable(client, monkeypatch):
    from app import detector
    def boom(*a, **k): raise detector.ModelUnavailableError("none")
    monkeypatch.setattr(detector, "predict", boom)
    j = client.post("/api/detection/predict", headers=login(client, "citizen"), files={"image": ("a.jpg", make_image(201), "image/jpeg")}).json()
    assert j["success"] is False and j["model_version"] is None and j["message"] == "AI model is not currently available."


def test_reverse_geocoding_optional_and_never_fabricates(client, monkeypatch):
    from app.services import geocode_service as g
    c = login(client, "citizen")
    calls = []
    payload = {"display_name": "Main Rd, Hubballi, Karnataka, India",
               "address": {"village": "Keshwapur", "city": "Hubballi", "county": "Dharwad", "state": "Karnataka", "country": "India"}}
    monkeypatch.setattr(g, "fetch_json", lambda lat, lng, t: calls.append(1) or payload)
    g._cached.cache_clear()
    monkeypatch.delenv("REVERSE_GEOCODING", raising=False)
    off = submit(client, c, seed=210, lat=15.3).json()
    assert calls == [] and off["address"] is None and off["state"] is None          # off by default
    monkeypatch.setenv("REVERSE_GEOCODING", "true")
    on = submit(client, c, seed=211, lat=15.4, lng=75.1).json()
    assert (on["village"], on["town"], on["district"], on["state"], on["country"]) == ("Keshwapur", "Hubballi", "Dharwad", "Karnataka", "India")
    assert on["address"].startswith("Main Rd")
    manual = submit(client, c, seed=212, lat=15.5, lng=75.2, address="my own text").json()
    assert manual["address"] == "my own text"                                        # user-supplied wins
    def down(*a, **k): raise TimeoutError("boom")
    monkeypatch.setattr(g, "fetch_json", down); g._cached.cache_clear()
    fail = submit(client, c, seed=213, lat=15.6, lng=75.3)
    assert fail.status_code == 200 and fail.json()["address"] is None and fail.json()["state"] is None
    assert g.parse({}) is None and g.parse({"address": {}}) is None


def test_upload_rate_limit_only_for_citizens_and_replays_allowed(client):
    a, c, s = login(client, "admin"), login(client, "citizen"), login(client, "staff")
    assert client.put("/api/admin/settings", headers=a, json={"max_reports_per_hour": 2}).status_code == 200
    assert submit(client, c, seed=220, lat=10.0, client_uuid="u1").status_code == 200
    assert submit(client, c, seed=221, lat=11.0).status_code == 200
    r = submit(client, c, seed=222, lat=12.0)
    assert r.status_code == 429 and "try again later" in r.json()["detail"]
    assert submit(client, c, seed=220, lat=10.0, client_uuid="u1").status_code == 200   # offline-sync retry is not blocked
    assert submit(client, s, seed=223, lat=13.0).status_code == 200                      # staff exempt


def test_sync_status_is_private(client):
    a, b = login(client, "citizen"), login(client, "citizen2")
    rid = submit(client, a, seed=230, client_uuid="ww-1").json()["id"]
    j = client.post("/api/sync/status", headers=a, json={"client_uuids": ["ww-1", "ww-2"]}).json()
    assert j == {"synced": {"ww-1": rid}, "unknown": ["ww-2"]}
    assert client.post("/api/sync/status", headers=b, json={"client_uuids": ["ww-1"]}).json()["synced"] == {}
    assert client.post("/api/sync/status", json={"client_uuids": []}).status_code == 401


def test_analytics_summary(client):
    a, c, s = login(client, "admin"), login(client, "citizen"), login(client, "staff")
    assert client.get("/api/analytics/summary", headers=c).status_code == 403
    empty = client.get("/api/analytics/summary", headers=a).json()
    assert empty["total_reports"] == 0 and empty["avg_resolution_hours"] is None and empty["cleanup_completion"]["rate_percent"] is None
    FAKE["dets"] = [det("paper", 0.9)]
    submit(client, c, seed=240, lat=20.0, village="Alpha")
    FAKE["dets"] = [det("plastic", 0.6), det("plastic", 0.7)]
    submit(client, c, seed=241, lat=21.0, village="Alpha")
    submit(client, c, seed=242, lat=22.0, village="Beta")
    j = client.get("/api/analytics/summary?days=30", headers=a).json()
    assert j["total_reports"] == 3 and len(j["reports_per_day"]) == 30 and len(j["reports_per_week"]) == 12 and len(j["reports_per_month"]) == 12
    assert j["reports_per_day"][-1]["count"] == 3 and j["reports_per_month"][-1]["count"] == 3
    assert {x["label"]: x["count"] for x in j["waste_categories"]} == {"paper": 1, "plastic": 2}
    assert {x["label"]: x["count"] for x in j["area_wise"]} == {"Alpha": 2, "Beta": 1}
    assert sum(x["count"] for x in j["confidence_distribution"]) == 3 and j["avg_confidence"] is not None
    assert sum(x["count"] for x in j["severity_distribution"]) == 3
    assert client.get("/api/analytics/summary", headers=s).json()["total_reports"] == 3   # unassigned review queue is visible to staff
    old = client.get("/api/dashboard/analytics", headers=a)
    assert old.status_code == 200 and sum(old.json()["by_month"].values()) == 3


def test_analytics_after_closed_cleanup(client, monkeypatch):
    from app import detector
    rid, c, a, s = _assigned_report(client, 250)
    client.put(f"/api/reports/{rid}/status", headers=s, json={"status": "IN_PROGRESS"})
    monkeypatch.setattr(detector, "predict", lambda p, t=None: [det() for _ in range(10 if "/before/" in p or "/reports/" in p else 1)])
    client.post(f"/api/reports/{rid}/complete", headers=s, files={"completion_image": ("a.jpg", make_image(251), "image/jpeg")})
    client.post(f"/api/reports/{rid}/cleanup-verification", headers=a, json={"approve": True})
    j = client.get("/api/analytics/summary", headers=a).json()
    assert j["cleanup_completion"] == {"eligible": 1, "closed": 1, "rate_percent": 100.0, "awaiting_verification": 0, "in_progress": 0}
    assert j["avg_resolution_hours"] is not None and j["avg_resolution_hours"] >= 0
    assert j["avg_cleanup_improvement_percent"] == 90.0
    cards = client.get("/api/dashboard/cards", headers=a).json()
    assert cards["completed_cleanups"] == 1 and cards["avg_resolution_hours"] is not None


def test_image_paths_are_url_style_and_fetchable_with_absolute_upload_dir(client, monkeypatch):
    """Regression: with an absolute UPLOAD_DIR (Docker/production) the DB used to store filesystem paths,
    so every image URL 404'd in the dashboard and mobile app."""
    from app import detector
    from app.utils import file_utils
    import os
    assert os.path.isabs(str(file_utils.UPLOAD_DIR))  # this test run really uses an absolute dir
    rid, c, a, s = _assigned_report(client, 260)
    r = client.get(f"/api/reports/{rid}", headers=s).json()
    assert r["image_path"].startswith("uploads/reports/") and not r["image_path"].startswith("/")
    img = client.get("/" + r["image_path"])
    assert img.status_code == 200 and img.headers["content-type"].startswith("image/") and len(img.content) > 100
    client.put(f"/api/reports/{rid}/status", headers=s, json={"status": "IN_PROGRESS"})
    monkeypatch.setattr(detector, "predict", lambda p, t=None: [det()] if os.path.exists(p) else (_ for _ in ()).throw(AssertionError(f"AI was given a non-file path: {p}")))
    client.post(f"/api/reports/{rid}/before-image", headers=s, files={"image": ("b.jpg", make_image(261), "image/jpeg")})
    assert client.post(f"/api/reports/{rid}/complete", headers=s, files={"completion_image": ("a.jpg", make_image(262), "image/jpeg")}).status_code == 200
    cv = client.get(f"/api/reports/{rid}/cleanup-verification", headers=s).json()
    assert cv["analysis_available"] is True
    for key, folder in (("before_image", "before"), ("after_image", "after")):
        assert cv[key].startswith(f"uploads/{folder}/")
        assert client.get("/" + cv[key]).status_code == 200


def test_physical_path_handles_legacy_rows():
    from app.utils import file_utils
    assert file_utils.physical_path("/old/absolute/x.jpg") == "/old/absolute/x.jpg"       # legacy row: untouched
    assert file_utils.physical_path("uploads/reports/x.jpg").endswith("reports/x.jpg")


def test_duplicate_rule_needs_image_or_very_close_same_category(client):
    c = login(client, "citizen")
    FAKE["dets"] = [det("plastic", 0.9)]
    submit(client, c, seed=270, lat=30.00000, lng=75.0)
    far_diff_photo = submit(client, c, seed=271, lat=30.00020, lng=75.0).json()      # ~22 m, different photo, same category
    assert far_diff_photo["is_possible_duplicate"] is False                            # category alone is not evidence
    near_diff_photo = submit(client, c, seed=272, lat=30.00005, lng=75.0).json()     # ~5.5 m, different photo, same category
    assert near_diff_photo["is_possible_duplicate"] is True
    FAKE["dets"] = [det("paper", 0.9)]
    other_cat = submit(client, c, seed=273, lat=30.00003, lng=75.0).json()           # ~3 m, different photo, DIFFERENT category
    assert other_cat["is_possible_duplicate"] is False
    same_photo_other_cat = submit(client, c, seed=270, lat=30.00015, lng=75.0).json()  # ~16 m but identical photo
    assert same_photo_other_cat["is_possible_duplicate"] is True


def login_as(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_staff_cannot_verify_own_cleanup_but_other_staff_can(client, monkeypatch):
    """Separation of duties: the person who did the cleanup cannot sign it off."""
    from app import detector
    rid, c, a, s = _assigned_report(client, 280)
    s2 = login(client, "staff2")
    client.put(f"/api/reports/{rid}/status", headers=s, json={"status": "IN_PROGRESS"})
    monkeypatch.setattr(detector, "predict", lambda p, t=None: [det()] * (6 if "/reports/" in p or "/before/" in p else 1))
    assert client.post(f"/api/reports/{rid}/complete", headers=s, files={"completion_image": ("a.jpg", make_image(281), "image/jpeg")}).status_code == 200
    body = {"approve": True, "remarks": "self-check"}
    r = client.post(f"/api/reports/{rid}/cleanup-verification", headers=s, json=body)
    assert r.status_code == 403 and "different staff member" in r.json()["detail"]
    assert client.put(f"/api/reports/{rid}/status", headers=s, json={"status": "CLOSED"}).status_code == 403   # same rule on the generic endpoint
    assert client.get(f"/api/reports/{rid}", headers=s2).status_code == 200                                     # verification queue visible to other staff
    assert rid in [x["id"] for x in client.get("/api/reports", headers=s2).json()]
    assert client.post(f"/api/reports/{rid}/cleanup-verification", headers=s2, json={"approve": True, "remarks": "checked on site"}).status_code == 200
    assert client.get(f"/api/reports/{rid}", headers=a).json()["status"] == "CLOSED"
    # staff who verified/closed it keep read access afterwards; an uninvolved staff member does not
    assert client.get(f"/api/reports/{rid}", headers=s2).status_code == 200
    assert rid in [x["id"] for x in client.get("/api/reports", headers=s2).json()]
    assert client.get(f"/api/reports/{rid}/history", headers=s2).status_code == 200
    outsider = client.post("/api/admin/users", headers=a, json={"name": "O", "email": "o@t.com", "password": "password123", "role": "STAFF"})
    assert outsider.status_code == 201
    o = login_as(client, "o@t.com")
    assert client.get(f"/api/reports/{rid}", headers=o).status_code == 403


def test_verification_queue_not_open_to_citizens_or_before_completion(client):
    rid, c, a, s = _assigned_report(client, 290)
    s2 = login(client, "staff2")
    assert client.get(f"/api/reports/{rid}", headers=s2).status_code == 403          # ASSIGNED: only its own staff
    assert client.get(f"/api/reports/{rid}", headers=login(client, "citizen2")).status_code == 403
    assert client.post(f"/api/reports/{rid}/cleanup-verification", headers=s2, json={"approve": True}).status_code in (400, 403)


def test_database_url_normalization():
    from app.database import _normalize
    assert _normalize("postgresql://u:p@h:5432/d") == "postgresql+psycopg2://u:p@h:5432/d"
    assert _normalize("postgres://u:p@h/d") == "postgresql+psycopg2://u:p@h/d"
    assert _normalize("postgresql+psycopg2://u@h/d") == "postgresql+psycopg2://u@h/d"      # explicit driver untouched
    assert _normalize("sqlite:///./x.db") == "sqlite:///./x.db"


def test_production_refuses_weak_or_default_secret():
    import pytest as _pt
    from app.utils.security import DEV_DEFAULT_KEY, validate_secret
    with _pt.raises(RuntimeError, match="Refusing to start"):
        validate_secret("production", DEV_DEFAULT_KEY)
    with _pt.raises(RuntimeError):
        validate_secret("production", "short")
    assert validate_secret("production", "x" * 48) is None
    warn = validate_secret("development", DEV_DEFAULT_KEY)
    assert warn and "insecure" in warn                      # dev: loud warning, not a crash
    assert validate_secret("development", "y" * 40) is None


def test_model_path_resolves_in_container_layout(tmp_path, monkeypatch):
    from app.services import training_service as ts
    backend = tmp_path / "app"
    (backend / "models" / "wastewatch_v1").mkdir(parents=True)
    (backend / "models" / "wastewatch_v1" / "best.pt").write_bytes(b"x")
    monkeypatch.setattr(ts, "BACKEND_DIR", backend)
    monkeypatch.setattr(ts, "REPO_ROOT", tmp_path)          # '/' in the image: repo-root-relative path does not exist
    found = ts.resolve_model_path({"path": "backend/models/wastewatch_v1/best.pt"})
    assert found == backend / "models" / "wastewatch_v1" / "best.pt"
    assert ts.resolve_model_path({"path": "backend/models/nope/best.pt"}) is None


def test_create_admin_command(client, monkeypatch):
    from app import create_admin
    monkeypatch.setenv("ADMIN_PASSWORD", "BrandNewPass1")
    assert create_admin.main(["--email", "New.Admin@Example.org", "--name", "Ada"]) == 0
    r = client.post("/api/auth/login", json={"email": "new.admin@example.org", "password": "BrandNewPass1"})
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).json()
    assert me["role"] == "ADMIN" and me["name"] == "Ada"
    # promoting an existing citizen resets the password and role
    monkeypatch.setenv("ADMIN_PASSWORD", "AnotherPass22")
    assert create_admin.main(["--email", "citizen@t.com"]) == 0
    assert client.post("/api/auth/login", json={"email": "citizen@t.com", "password": "password123"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "citizen@t.com", "password": "AnotherPass22"}).status_code == 200
    monkeypatch.setenv("ADMIN_PASSWORD", "short")
    assert create_admin.main(["--email", "x@y.org"]) == 1      # weak password refused


def test_filter_by_assigned_staff_date_range_and_hotspot(client):
    a, c = login(client, "admin"), login(client, "citizen")
    rid, c, a, s = _assigned_report(client, 300)                      # assigned to staff@t.com
    other = submit(client, c, seed=301, lat=40.0).json()["id"]        # unassigned
    staff_id = next(u["id"] for u in client.get("/api/admin/users?role=STAFF", headers=a).json() if u["email"] == "staff@t.com")
    ids = [r["id"] for r in client.get(f"/api/reports?assigned_to={staff_id}", headers=a).json()]
    assert ids == [rid]
    assert client.get("/api/reports?assigned_to=99999", headers=a).json() == []
    assert len(client.get("/api/reports?date_from=2000-01-01T00:00:00&date_to=2100-01-01T00:00:00", headers=a).json()) == 2
    assert client.get("/api/reports?date_from=2100-01-01T00:00:00", headers=a).json() == []
    assert client.get("/api/reports?date_to=2000-01-01T00:00:00", headers=a).json() == []
    # assigned_to is admin-only: it never widens what a citizen or another citizen can see
    assert {r["id"] for r in client.get(f"/api/reports?assigned_to={staff_id}", headers=c).json()} == {rid, other}   # own reports only
    assert client.get(f"/api/reports?assigned_to={staff_id}", headers=login(client, "citizen2")).json() == []


# ---------------- waste / not-waste decision ----------------
def _titles(client, who):
    return [n["title"] for n in client.get("/api/notifications", headers=login(client, who)).json()]


def test_waste_photo_is_stored_notified_and_counted(client):
    c, a = login(client, "citizen"), login(client, "admin")
    FAKE["dets"] = [det("waste", 0.93)]
    before = client.get("/api/dashboard/cards", headers=a).json()
    j = submit(client, c, seed=201, lat=15.2).json()
    assert j["is_waste"] is True and j["status"] == "AI_DETECTED" and j["confidence"] == 0.93
    assert any(t.startswith("Waste detected") and f"#{j['id']}" in t for t in _titles(client, "admin"))
    after = client.get("/api/dashboard/cards", headers=a).json()
    assert after["total_reports"] == before["total_reports"] + 1


def test_not_waste_photo_is_stored_separately_and_never_counted(client):
    c, a, st = login(client, "citizen"), login(client, "admin"), login(client, "staff")
    FAKE["dets"] = [det("not_waste", 0.97)]            # classifier says: not waste
    cards0 = client.get("/api/dashboard/cards", headers=a).json()
    staff_notes0 = len(client.get("/api/notifications", headers=st).json())
    j = submit(client, c, seed=202, lat=15.3).json()
    assert j["is_waste"] is False and j["status"] == "NOT_WASTE" and j["waste_type"] is None
    assert j["hotspot_id"] is None and j["severity"] is None and j["confidence"] == 0.97
    # saved with its photo + GPS, but kept out of the waste lists, counts and the staff/admin notifications
    assert j["id"] not in [r["id"] for r in client.get("/api/reports", headers=a).json()]
    assert j["id"] in [r["id"] for r in client.get("/api/reports?is_waste=false", headers=a).json()]
    assert j["id"] in [r["id"] for r in client.get("/api/reports", headers=c).json()]   # the citizen still sees their own
    cards1 = client.get("/api/dashboard/cards", headers=a).json()
    assert cards1["total_reports"] == cards0["total_reports"] and cards1["not_waste_reports"] == cards0["not_waste_reports"] + 1
    assert len(client.get("/api/notifications", headers=st).json()) == staff_notes0
    assert "Photo is not waste" in _titles(client, "citizen")


def test_not_waste_does_not_form_hotspots_or_duplicates(client):
    c = login(client, "citizen")
    FAKE["dets"] = [det("not_waste", 0.9)]
    for i in range(4):
        j = submit(client, c, seed=210 + i, lat=15.4).json()
        assert j["hotspot_id"] is None and j["is_possible_duplicate"] is False


def test_unavailable_model_keeps_report_for_human_review(client, monkeypatch):
    from app import detector
    def boom(*_a, **_k): raise detector.ModelUnavailableError("no model")
    monkeypatch.setattr(detector, "predict", boom)
    j = submit(client, login(client, "citizen"), seed=220, lat=15.5).json()
    assert j["is_waste"] is None and j["status"] == "NEW"


def test_admin_can_correct_the_ai_both_ways(client):
    c, a = login(client, "citizen"), login(client, "admin")
    FAKE["dets"] = [det("not_waste", 0.8)]
    j = submit(client, c, seed=230, lat=15.6).json()
    assert client.post(f"/api/reports/{j['id']}/reclassify", headers=c, json={"is_waste": True}).status_code == 403
    r = client.post(f"/api/reports/{j['id']}/reclassify", headers=a, json={"is_waste": True}).json()
    assert r["is_waste"] is True and r["status"] == "NEW"
    assert j["id"] in [x["id"] for x in client.get("/api/reports", headers=a).json()]
    assert any(t.startswith("New report") and f"#{j['id']}" in t for t in _titles(client, "admin"))
    r = client.post(f"/api/reports/{j['id']}/reclassify", headers=a, json={"is_waste": False}).json()
    assert r["is_waste"] is False and r["status"] == "NOT_WASTE"
    assert client.post(f"/api/reports/{j['id']}/reclassify", headers=a, json={"is_waste": False}).status_code == 400
