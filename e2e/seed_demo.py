from _common import REPO, DEMO, DB_URL, API, DASH  # noqa: E402
import io, random, sys, sqlite3
import requests
from PIL import Image
sys.path.insert(0, str(REPO / "backend"))
B = API

def img(seed, size=(400, 300)):
    r = random.Random(seed); im = Image.new("RGB", size)
    im.putdata([(r.randint(30, 220),) * 3 for _ in range(size[0] * size[1])])
    b = io.BytesIO(); im.save(b, "JPEG"); return b.getvalue()

# admin + staff are created straight in the DB (this is what `python -m app.seed` does)
import os
os.environ.update(DATABASE_URL=DB_URL, UPLOAD_DIR=str(DEMO / "uploads"))
os.environ.update(SEED_ADMIN_PASSWORD="AdminPass123", SEED_STAFF_PASSWORD="StaffPass123", SEED_CITIZEN_PASSWORD="CitizenPass123")
from app import seed; seed.main()

def login(email, pw):
    r = requests.post(f"{B}/api/auth/login", json={"email": email, "password": pw}); r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
cit = login("citizen@wastewatch.dev", "CitizenPass123")
adm = login("admin@wastewatch.dev", "AdminPass123")

def submit(seed, lat, lng, **kw):
    r = requests.post(f"{B}/api/reports", headers=cit, files={"image": ("a.jpg", img(seed), "image/jpeg")},
                      data={"latitude": lat, "longitude": lng, "gps_accuracy": 6, **kw})
    r.raise_for_status(); return r.json()

ids = []
# three reports ~20 m apart -> hotspot; a 4th same photo+place -> duplicate flag
for i in range(3):
    ids.append(submit(100 + i * 9, 17.38500 + i * 0.0002, 78.48600, village="Old Town", description=f"pile {i}")["id"])
dup = submit(100, 17.38502, 78.48601, village="Old Town", description="same pile again")
ids += [submit(200, 17.44000, 78.35000, village="Tech Park")["id"], submit(300, 17.30000, 78.55000, village="Lakeside")["id"]]
print("reports", ids, "dup flagged:", dup["is_possible_duplicate"])
staff_id = next(u["id"] for u in requests.get(f"{B}/api/admin/users?role=STAFF", headers=adm).json() if u["email"] == "staff@wastewatch.dev")
# verify + assign one for the staff cleanup flow
requests.post(f"{B}/api/admin/reports/{ids[3]}/verify", headers=adm, json={"verification_status": "CORRECT"}).raise_for_status()
requests.post(f"{B}/api/reports/{ids[3]}/assign", headers=adm, json={"staff_id": staff_id}).raise_for_status()
print("assigned", ids[3], "to staff", staff_id)
open(str(DEMO / "ids.txt"), "w").write(",".join(map(str, ids)))
