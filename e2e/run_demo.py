"""TEST HARNESS ONLY: real backend, but the YOLO call is replaced by a deterministic stub
(no trained model exists yet). Everything else -- DB, auth, workflow, scoring -- is the real code."""
from _common import REPO, DEMO, DB_URL, API, DASH  # noqa: E402
import os, sys, random
os.environ.update(DATABASE_URL=DB_URL, UPLOAD_DIR=str(DEMO / "uploads"), SECRET_KEY="demo-secret", APP_ENV="development")
sys.path.insert(0, str(REPO / "backend"))
from app import detector

def stub(path, conf=None):
    rnd = random.Random(os.path.getsize(path))
    n = 12 if "/reports/" in path or "/before/" in path else 2   # before-cleanup photo has more waste than the after photo
    cls = ["plastic", "general_waste", "paper", "drainage_waste"]
    out = []
    for i in range(n):
        x, y = rnd.randint(10, 250), rnd.randint(10, 150)
        out.append({"class_name": cls[i % 4] if n > 2 else "plastic", "confidence": round(rnd.uniform(0.55, 0.95), 2),
                    "box": {"x1": float(x), "y1": float(y), "x2": float(x + 90), "y2": float(y + 70)}})
    return out
detector.predict = stub
import uvicorn
from app.main import app
uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
