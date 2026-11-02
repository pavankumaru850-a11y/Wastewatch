import io
import os
import random
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="ww_test_")
# Default: throwaway SQLite. Set TEST_DATABASE_URL=postgresql://... to run the same suite on PostgreSQL.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_TMP}/test.db"
os.environ["UPLOAD_DIR"] = f"{_TMP}/uploads"
os.environ["SECRET_KEY"] = "test-secret"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import detector
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import RoleEnum, User
from app.utils.security import hash_password

FAKE = {"dets": []}


def fake_predict(image_path, conf_threshold=None):
    return list(FAKE["dets"])


def det(cls="plastic", conf=0.9, box=(10, 10, 100, 100)):
    return {"class_name": cls, "confidence": conf, "box": dict(zip(("x1", "y1", "x2", "y2"), map(float, box)))}


def make_image(seed=1, size=(400, 300), blur=False, dark=False, fmt="JPEG"):
    """Random-noise textured image (sharp). seed controls content -> perceptual hash."""
    rnd = random.Random(seed)
    im = Image.new("RGB", size)
    px = im.load()
    for x in range(0, size[0], 4):
        for y in range(0, size[1], 4):
            c = (rnd.randint(40, 220),) * 3 if not dark else (3, 3, 3)
            for dx in range(4):
                for dy in range(4):
                    if x + dx < size[0] and y + dy < size[1]:
                        px[x + dx, y + dy] = c
    if blur:
        im = Image.new("RGB", size, (128, 128, 128))  # perfectly flat = zero detail
    buf = io.BytesIO()
    im.save(buf, fmt)
    return buf.getvalue()


@pytest.fixture(scope="session", autouse=True)
def _patch():
    detector.predict = fake_predict
    yield


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:
        FAKE["dets"] = [det()]
        db = SessionLocal()
        for name, role in (("admin", RoleEnum.ADMIN), ("staff", RoleEnum.STAFF), ("staff2", RoleEnum.STAFF), ("citizen", RoleEnum.CITIZEN), ("citizen2", RoleEnum.CITIZEN)):
            db.add(User(name=name, email=f"{name}@t.com", password_hash=hash_password("password123"), role=role))
        db.commit()
        db.close()
        yield c


def login(client, name):
    r = client.post("/api/auth/login", json={"email": f"{name}@t.com", "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def submit(client, headers, seed=1, lat=15.0, lng=75.0, **extra):
    files = {"image": ("x.jpg", make_image(seed), "image/jpeg")}
    data = {"latitude": str(lat), "longitude": str(lng), **extra}
    return client.post("/api/reports", files=files, data=data, headers=headers)
