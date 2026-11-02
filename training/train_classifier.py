"""
train_classifier.py -- trains a YOLOv8 *classification* model on the
TrashNet-style dataset (one folder per class, no bounding boxes).

Steps (all in one script):
  1. Reads class folders from --source (default ../dataset-resized)
  2. Drops exact duplicate images (by content hash)
  3. Makes a stratified train/val/test split -> training/dataset_cls/
  4. Fine-tunes yolov8n-cls.pt
  5. Evaluates on the held-out TEST split and prints real top-1 / top-5 accuracy
  6. Copies best.pt to backend/models/best.pt and records it in
     backend/models/model_versions.json (only with --deploy)

WasteWatch's goal is a yes/no decision: WASTE or NOT WASTE. Use --binary to build that
two-class dataset from any folders you have (every photo under --waste folders becomes
"waste", every photo under --not-waste becomes "not_waste"):

    python train_classifier.py --binary \
        --waste ../dataset/raw C:\\data\\dataset-resized \
        --not-waste C:\\data\\not_waste --deploy

Usage (class-per-folder, e.g. TrashNet's own 6 classes):
    pip install -r requirements.txt
    python train_classifier.py --source /path/to/dataset-resized --deploy

Env / flags: --epochs (30), --imgsz (224), --batch (32), --model (yolov8n-cls.pt)
Runs on CPU but a GPU (e.g. free Colab T4) is ~10-20x faster.
"""
import argparse
import csv
import hashlib
import json
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
IMG_EXTS = {".jpg", ".jpeg", ".png"}


def prepare(source: Path, out: Path, ratios=(0.7, 0.15, 0.15), seed=42):
    classes = sorted(d.name for d in source.iterdir() if d.is_dir() and not d.name.startswith((".", "_")))
    if not classes:
        sys.exit(f"No class folders found in {source}")
    if out.exists():
        shutil.rmtree(out)
    rng = random.Random(seed)
    seen, dupes, counts = set(), 0, {}
    for cls in classes:
        files = sorted(p for p in (source / cls).iterdir() if p.suffix.lower() in IMG_EXTS)
        unique = []
        for p in files:
            h = hashlib.md5(p.read_bytes()).hexdigest()
            if h in seen:
                dupes += 1
                continue
            seen.add(h)
            unique.append(p)
        rng.shuffle(unique)
        n = len(unique)
        n_train, n_val = int(n * ratios[0]), int(n * ratios[1])
        parts = {"train": unique[:n_train], "val": unique[n_train:n_train + n_val], "test": unique[n_train + n_val:]}
        for split, items in parts.items():
            (out / split / cls).mkdir(parents=True, exist_ok=True)
            for p in items:
                shutil.copy2(p, out / split / cls / p.name)
        counts[cls] = {k: len(v) for k, v in parts.items()}
    print(f"Split written to {out}  (dropped {dupes} duplicate image(s))")
    for cls, c in counts.items():
        print(f"  {cls:<10} train={c['train']:<4} val={c['val']:<4} test={c['test']}")
    return classes


def build_binary(waste_dirs, not_waste_dirs, out: Path, max_ratio: float = 2.0, seed: int = 42) -> Path:
    """Merge many folders into out/waste and out/not_waste (copies; originals untouched).
    Exact duplicates are dropped. The bigger class is down-sampled to max_ratio x the smaller one,
    otherwise the model would just learn to say "waste" for everything."""
    rng = random.Random(seed)
    groups = {"waste": [], "not_waste": []}
    seen = set()
    for label, dirs in (("waste", waste_dirs), ("not_waste", not_waste_dirs)):
        for d in dirs:
            d = Path(d)
            if not d.exists():
                sys.exit(f"Folder not found: {d}")
            for p in sorted(x for x in d.rglob("*") if x.suffix.lower() in IMG_EXTS):
                h = hashlib.md5(p.read_bytes()).hexdigest()
                if h in seen:
                    continue
                seen.add(h)
                groups[label].append(p)
    n_w, n_n = len(groups["waste"]), len(groups["not_waste"])
    if n_w == 0 or n_n == 0:
        sys.exit(f"Need photos for BOTH classes (found waste={n_w}, not_waste={n_n}).")
    print(f"Found {n_w} waste and {n_n} not-waste photos (after removing duplicates).")
    if min(n_w, n_n) < 100:
        print("WARNING: fewer than 100 photos in one class. Results will be unreliable; add more photos of the smaller class.")
    small = min(n_w, n_n)
    cap = int(small * max_ratio)
    for label in groups:
        if len(groups[label]) > cap:
            rng.shuffle(groups[label])
            print(f"Balancing: using {cap} of {len(groups[label])} '{label}' photos (max ratio {max_ratio}:1).")
            groups[label] = groups[label][:cap]
    if out.exists():
        shutil.rmtree(out)
    for label, files in groups.items():
        (out / label).mkdir(parents=True)
        for i, p in enumerate(files):
            shutil.copy2(p, out / label / f"{i:05d}_{p.name}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(REPO_ROOT.parent / "dataset-resized"))
    ap.add_argument("--binary", action="store_true", help="train WASTE vs NOT WASTE (use with --waste and --not-waste)")
    ap.add_argument("--waste", nargs="+", default=[], help="folders of photos that contain waste (searched recursively)")
    ap.add_argument("--not-waste", nargs="+", default=[], dest="not_waste", help="folders of photos with NO waste")
    ap.add_argument("--scenes", action="store_true",
                    help="RECOMMENDED: build WASTE/NOT WASTE from dataset_annotated (waste = photo, not_waste = clean crops "
                         "outside the boxes), split per photo; see build_scene_binary.py")
    ap.add_argument("--max-ratio", type=float, default=2.0, help="cap the bigger class at this multiple of the smaller")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--imgsz", type=int, default=224)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--model", default="yolov8n-cls.pt")
    ap.add_argument("--version", default="cls-v1")
    ap.add_argument("--deploy", action="store_true", help="copy weights to backend/models/best.pt")
    args = ap.parse_args()

    data_dir = HERE / "dataset_cls"
    if args.scenes:
        import build_scene_binary
        build_scene_binary.build(HERE / "dataset_annotated" / "images", HERE / "dataset_annotated" / "labels", data_dir)
        args.binary = True
        classes = sorted(d.name for d in (data_dir / "train").iterdir() if d.is_dir())
        source = data_dir
    elif args.binary:
        source = build_binary(args.waste, args.not_waste, HERE / "dataset_binary_src", args.max_ratio)
    else:
        source = Path(args.source)
    if not source.exists():
        sys.exit(f"Dataset folder not found: {source} (use --source)")
    if not args.scenes:
        classes = prepare(source, data_dir)

    try:
        from ultralytics import YOLO
    except ImportError:
        sys.exit("ultralytics is not installed. Run: pip install ultralytics")

    model = YOLO(args.model)
    results = model.train(data=str(data_dir), epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
                          project=str(HERE / "runs"), name="wastewatch_cls", exist_ok=True)
    run_dir = Path(results.save_dir)
    (HERE / "runs").mkdir(exist_ok=True)
    best = run_dir / "weights" / "best.pt"
    if not best.exists():
        sys.exit(f"Training finished but {best} was not produced. Check the log above.")

    # Honest evaluation on data the model never saw during training/selection
    test_metrics = YOLO(str(best)).val(data=str(data_dir), split="test", imgsz=args.imgsz)
    top1, top5 = float(test_metrics.top1), float(test_metrics.top5)
    print("\n=== TEST-set results (held-out) ===")
    print(f"Classes: {classes}")
    print(f"Top-1 accuracy: {top1:.4f}   Top-5 accuracy: {top5:.4f}")

    versions_dir = REPO_ROOT / "backend" / "models"
    (versions_dir / "versions").mkdir(parents=True, exist_ok=True)
    versioned = versions_dir / "versions" / f"{args.version}.pt"
    shutil.copy2(best, versioned)
    record = {
        "model_name": "wastewatch-waste-vs-not" if args.binary else "wastewatch-yolo-cls", "version": args.version,
        "path": str(versioned.relative_to(REPO_ROOT)),
        "precision": None, "recall": None, "map50": None, "map5095": None,
        "top1_accuracy": top1, "top5_accuracy": top5, "classes": classes,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "deployed": bool(args.deploy), "notes": f"classifier, {args.epochs} epochs, imgsz {args.imgsz}",
    }
    reg = versions_dir / "model_versions.json"
    registry = json.loads(reg.read_text()) if reg.exists() else []
    registry.append(record)
    reg.write_text(json.dumps(registry, indent=2))
    if args.deploy:
        shutil.copy2(best, versions_dir / "best.pt")
        print(f"Deployed to {versions_dir / 'best.pt'}")


if __name__ == "__main__":
    main()
