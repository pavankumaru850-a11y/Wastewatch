"""
evaluate.py -- measures a trained checkpoint on the HELD-OUT test split and
writes evaluation.json (overall + per-class precision/recall/AP) next to the
run. export.py refuses to register a model that has no evaluation.json, so
every registered model has real, reproducible numbers.

Usage:
    python evaluate.py --weights runs/wastewatch/weights/best.pt
    python evaluate.py --weights ... --split val      (not recommended for reporting)
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build_report(names: dict, box, split: str, n_images: int, dataset_version: str) -> dict:
    """box: ultralytics Metric-like object (mp, mr, map50, map, ap_class_index, and per-class accessors).
    Kept separate from the YOLO call so it can be unit-tested with a stand-in object."""
    per_class = {}
    for i, cid in enumerate(box.ap_class_index):
        p, r, ap50, ap = box.class_result(i)
        per_class[names[int(cid)]] = {"precision": float(p), "recall": float(r), "ap50": float(ap50), "ap50_95": float(ap)}
    return {
        "split": split,
        "images": n_images,
        "dataset_version": dataset_version,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "precision": float(box.mp),
        "recall": float(box.mr),
        "map50": float(box.map50),
        "map5095": float(box.map),
        "per_class": per_class,
        "note": "Classes absent from this split are not listed; do not quote a class number without its image count.",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--weights", default=str(HERE / "runs" / "wastewatch" / "weights" / "best.pt"))
    p.add_argument("--data", default=str(HERE / "data.yaml"))
    p.add_argument("--split", default="test", choices=["val", "test"])
    args = p.parse_args()

    weights = Path(args.weights)
    if not weights.exists():
        print(f"ERROR: checkpoint not found at {weights}. Run train.py first.")
        sys.exit(1)
    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics is not installed. Run: pip install ultralytics")
        sys.exit(1)

    import dataset_manager as dm
    from resolve_data import resolved_data_yaml
    n_images = len(list((HERE / "dataset" / "images" / args.split).glob("*.*")))
    if n_images == 0:
        print(f"ERROR: dataset/images/{args.split} is empty; nothing to evaluate on.")
        sys.exit(1)

    run_dir = weights.parent.parent
    model = YOLO(str(weights))
    m = model.val(data=resolved_data_yaml(args.data), split=args.split, plots=True, project=str(run_dir), name=f"eval_{args.split}", exist_ok=True)
    report = build_report(m.names, m.box, args.split, n_images, dm.dataset_version())
    out = run_dir / "evaluation.json"
    out.write_text(json.dumps(report, indent=2))

    print(f"\n=== {args.split} results ({n_images} images) ===")
    print(f"Precision {report['precision']:.4f}  Recall {report['recall']:.4f}  mAP50 {report['map50']:.4f}  mAP50-95 {report['map5095']:.4f}")
    for name, v in report["per_class"].items():
        print(f"  {name:<16} P={v['precision']:.3f} R={v['recall']:.3f} AP50={v['ap50']:.3f}")
    print(f"\nSaved {out}\nConfusion matrix / PR curves: {run_dir / ('eval_' + args.split)}")
    if n_images < 30:
        print("\nNOTE: fewer than 30 test images -- these numbers are very noisy. Do not quote them as accuracy.")


if __name__ == "__main__":
    main()
