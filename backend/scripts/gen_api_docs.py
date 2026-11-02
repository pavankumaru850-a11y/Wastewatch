"""Regenerates docs/api.md from the running app's OpenAPI schema so the reference never drifts.
    cd backend && python scripts/gen_api_docs.py
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("UPLOAD_DIR", str(Path(__file__).resolve().parent / "_tmp_uploads"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402

spec = app.openapi()
by_tag: dict[str, list] = {}
for path, item in sorted(spec["paths"].items()):
    for method, op in item.items():
        tag = (op.get("tags") or ["other"])[0]
        params = [p["name"] for p in op.get("parameters", []) if p.get("in") == "query"]
        body = op.get("requestBody", {}).get("content", {})
        kind = "multipart/form-data" if "multipart/form-data" in body else "JSON" if "application/json" in body else ""
        by_tag.setdefault(tag, []).append((method.upper(), path, op.get("summary", ""), params, kind))

out = ["# WasteWatch API reference", "",
       "_Generated from the live OpenAPI schema by `backend/scripts/gen_api_docs.py`. In development the same data is browsable at `/docs` (Swagger) and `/openapi.json`; both are disabled when `APP_ENV=production`._", "",
       "All endpoints except `/api/health`, `/`, `/api/auth/register` and `/api/auth/login` need `Authorization: Bearer <token>`.",
       "Errors are always `{\"success\": false, \"detail\": \"...\"}`; raw exceptions are never returned.", "",
       "## Who may call what (enforced on the server, not just hidden in the UI)", "",
       "| Area | Citizen | Staff | Admin |", "|---|---|---|---|",
       "| Create report, list/read **own** reports, own notifications, `/api/sync/status` | yes | yes | yes |",
       "| Read reports | own only | assigned + review queue + verification queue + ones they worked on | all |",
       "| Verify / reject / start cleanup / before+after photos / complete | no | yes (own assignment) | yes |",
       "| Approve or reopen a finished cleanup | no | yes, **but not for a cleanup they did themselves** | yes |",
       "| Assign staff, edit report fields, export CSV/Excel | no | no | yes |",
       "| Hotspots, duplicate review, analytics, dashboard cards | no | yes | yes |",
       "| Users, staff creation, settings, scoring rules, AI models, audit log | no | no | yes |", "",
       "_Reports are never deleted through the API: duplicates are merged/rejected and all evidence is kept for the audit trail._", ""]
for tag in sorted(by_tag):
    out += [f"## {tag}", "", "| Method | Path | Summary | Query params | Body |", "|---|---|---|---|---|"]
    for m, p, s, q, k in by_tag[tag]:
        out.append(f"| {m} | `{p}` | {s} | {', '.join(q) or '-'} | {k or '-'} |")
    out.append("")
dest = Path(__file__).resolve().parent.parent.parent / "docs" / "api.md"
dest.write_text("\n".join(out), encoding="utf-8")
print(f"wrote {dest} ({sum(len(v) for v in by_tag.values())} operations)")
