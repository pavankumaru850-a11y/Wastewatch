from pathlib import Path
import tempfile

REPO = Path(__file__).resolve().parent.parent
DEMO = Path(tempfile.gettempdir()) / "wastewatch_demo"   # scratch DB, uploads, screenshots
DEMO.mkdir(exist_ok=True)
DB_URL = "sqlite:///" + (DEMO / "demo.db").as_posix()
API = "http://127.0.0.1:8765"
DASH = "http://127.0.0.1:4173"
