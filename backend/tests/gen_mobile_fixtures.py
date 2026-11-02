import json, sys
sys.path.insert(0, ".")
from tests.conftest import *  # sets env, patches detector fixtures
from tests import conftest as c
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal
from app.models import User, RoleEnum
from app.utils.security import hash_password
from app import detector
detector.predict = c.fake_predict
Base.metadata.drop_all(bind=engine)
out = {}
with TestClient(app) as cl:
    db = SessionLocal(); db.add(User(name="citizen", email="citizen@t.com", password_hash=hash_password("password123"), role=RoleEnum.CITIZEN)); db.commit(); db.close()
    h = c.login(cl, "citizen")
    def predict(img, dets):
        c.FAKE["dets"] = dets
        return cl.post("/api/detection/predict", headers=h, files={"image": ("a.jpg", img, "image/jpeg")}).json()
    out["waste"] = predict(c.make_image(2), [c.det("plastic", .91), c.det("plastic", .8)])
    out["paper"] = predict(c.make_image(3), [c.det("paper", .8)])
    out["none"] = predict(c.make_image(4), [])
    out["not_waste"] = predict(c.make_image(9), [c.det("not_waste", .96)])
    out["low"] = predict(c.make_image(5), [c.det("plastic", .42)])
    out["quality"] = predict(c.make_image(6, blur=True), [c.det()])
    from app import detector as d
    def boom(*a, **k): raise d.ModelUnavailableError("x")
    d.predict = boom
    out["unavailable"] = predict(c.make_image(7), [])
    d.predict = c.fake_predict
    c.FAKE["dets"] = [c.det("plastic", .9), c.det("paper", .7)]
    out["report"] = c.submit(cl, h, seed=8, gps_accuracy="7").json()
    out["history"] = cl.get(f"/api/reports/{out['report']['id']}/history", headers=h).json()
    out["notifications"] = cl.get("/api/notifications", headers=h).json()
json.dump(out, open("../mobile/tests/fixtures.json", "w"), indent=1, default=str)
print("ok", {k: (v.get("code") if isinstance(v, dict) else len(v)) for k, v in out.items()})
