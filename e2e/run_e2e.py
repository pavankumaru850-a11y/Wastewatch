"""One-command browser test: builds the dashboard, starts the demo backend (YOLO replaced by a stub, because no
model is trained yet) and the dashboard, seeds data through the real API, drives Chromium through the admin and
staff workflows, then shuts everything down.

    pip install -r ../backend/requirements.txt playwright pillow requests
    playwright install chromium
    python run_e2e.py

Exit code 0 = every check passed. Screenshots land in the temp folder printed at the end.
"""
import os
import shutil
import subprocess
import sys
import time
import urllib.request

from _common import API, DASH, DEMO, REPO

HERE = os.path.dirname(os.path.abspath(__file__))
NPM = "npm.cmd" if os.name == "nt" else "npm"
NPX = "npx.cmd" if os.name == "nt" else "npx"


def wait(url, seconds=40):
    for _ in range(seconds * 2):
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    return False


def main() -> int:
    for item in ("demo.db", "uploads"):                       # always start from an empty database
        p = DEMO / item
        shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)

    env = {**os.environ, "VITE_API_URL": API}
    dash_dir = REPO / "dashboard"
    if not (dash_dir / "node_modules").exists():
        subprocess.run([NPM, "install"], cwd=dash_dir, check=True)
    subprocess.run([NPM, "run", "build"], cwd=dash_dir, env=env, check=True, stdout=subprocess.DEVNULL)

    procs = []
    try:
        procs.append(subprocess.Popen([sys.executable, os.path.join(HERE, "run_demo.py")], cwd=HERE))
        procs.append(subprocess.Popen([NPX, "vite", "preview", "--port", "4173", "--host", "127.0.0.1"], cwd=dash_dir,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        if not (wait(f"{API}/api/health") and wait(DASH)):
            print("ERROR: servers did not start")
            return 2
        subprocess.run([sys.executable, os.path.join(HERE, "seed_demo.py")], cwd=HERE, check=True)
        code = subprocess.run([sys.executable, os.path.join(HERE, "ui_test.py")], cwd=HERE).returncode
        print(f"\nScreenshots: {DEMO}")
        return code
    finally:
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    sys.exit(main())
