"""
export.py -- registers a trained + EVALUATED run as a versioned model:

    backend/models/wastewatch_<version>/
        best.pt  results.csv  results.png  confusion_matrix.png  PR_curve.png ...  metrics.json
    backend/models/model_versions.json   (registry the admin dashboard reads)

Refuses if the run has no evaluation.json (run evaluate.py first) so a model can
never be registered with invented or missing numbers. It does NOT switch the
live model; activate it from the dashboard, or pass --deploy to also copy it to
backend/models/best.pt (refused when mAP50 is 0).

Usage:
    python export.py --run runs/wastewatch --version v1 [--notes "..."] [--deploy]
"""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = Path(os.environ.get("WW_REPO_ROOT") or HERE.parent)  # env override is for tests
ARTIFACTS = ["results.csv", "results.png", "args.yaml", "run_info.json", "evaluation.json"]
EVAL_ARTIFACTS = ["confusion_matrix.png", "confusion_matrix_normalized.png", "PR_curve.png", "P_curve.png", "R_curve.png", "F1_curve.png"]


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True, help="Path to the ultralytics run dir, e.g. runs/wastewatch")
    p.add_argument("--version", required=True, help="Version label, e.g. v1")
    p.add_argument("--notes", default="")
    p.add_argument("--deploy", action="store_true", help="Also copy weights to backend/models/best.pt")
    args = p.parse_args(argv)

    run_dir = Path(args.run)
    ckpt = run_dir / "weights" / "best.pt"
    evaluation = run_dir / "evaluation.json"
    if not ckpt.exists():
        print(f"ERROR: no checkpoint at {ckpt}")
        return 1
    if not evaluation.exists():
        print(f"ERROR: {evaluation} not found. Run  python evaluate.py --weights {ckpt}  first. "
              "Refusing to register a model without measured test-set metrics.")
        return 1
    ev = json.loads(evaluation.read_text())

    models_dir = REPO_ROOT / "backend" / "models"
    registry_path = models_dir / "model_versions.json"
    registry = json.loads(registry_path.read_text()) if registry_path.exists() else []
    if any(r.get("version") == args.version for r in registry):
        print(f"ERROR: version {args.version} is already registered. Use a new version label.")
        return 1
    if args.deploy and not ev.get("map50"):
        print("ERROR: mAP50 is 0 -- this model detects nothing on the test split. Not deploying.")
        return 1

    folder = models_dir / f"wastewatch_{args.version}"
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ckpt, folder / "best.pt")
    for name in ARTIFACTS:
        if (run_dir / name).exists():
            shutil.copy2(run_dir / name, folder / name)
    eval_dir = run_dir / f"eval_{ev.get('split', 'test')}"
    for name in EVAL_ARTIFACTS:
        for src in (eval_dir / name, run_dir / name):
            if src.exists():
                shutil.copy2(src, folder / name)
                break

    run_info = json.loads((run_dir / "run_info.json").read_text()) if (run_dir / "run_info.json").exists() else {}
    record = {
        "model_name": "wastewatch-yolo",
        "version": args.version,
        "path": str((folder / "best.pt").relative_to(REPO_ROOT)).replace("\\", "/"),
        "precision": ev["precision"], "recall": ev["recall"], "map50": ev["map50"], "map5095": ev["map5095"],
        "metrics_split": ev.get("split"), "metrics_images": ev.get("images"),
        "dataset_version": ev.get("dataset_version") or run_info.get("dataset_version"),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "deployed": bool(args.deploy),
        "notes": args.notes,
    }
    (folder / "metrics.json").write_text(json.dumps({**record, "per_class": ev.get("per_class", {})}, indent=2))

    if args.deploy:
        for r in registry:
            r["deployed"] = False
        shutil.copy2(ckpt, models_dir / "best.pt")
        print(f"Deployed: {models_dir / 'best.pt'}")
    registry.append(record)
    registry_path.write_text(json.dumps(registry, indent=2))
    print("Recorded model version:")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
