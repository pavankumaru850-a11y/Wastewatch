"""
train.py -- trains a YOLO detector on the WasteWatch dataset.

Requires dataset/images/{train,val} and dataset/labels/{train,val} to
already be populated (use dataset_manager.py split, fed by images
annotated with the annotation tool). Refuses to run against an empty
or unlabeled dataset instead of silently producing a useless model.

Configure via environment variables (or edit the DEFAULTS below):
    WW_EPOCHS        default 50
    WW_IMGSZ         default 640
    WW_BATCH         default 8
    WW_MODEL         default yolov8n.pt   (base checkpoint to fine-tune from)
    WW_CONF          default 0.40         (written into training_config.txt for the backend to read)
    WW_DATA_YAML     default ./data.yaml
    WW_PROJECT_DIR   default ./runs

Training does NOT deploy anything. The trained checkpoint stays in
training/runs/wastewatch/weights/best.pt. To put a model into service:
    python evaluate.py     (real test-split metrics -> evaluation.json)
    python export.py --run runs/wastewatch --version v1     (versioned, with metrics)
then activate it from the dashboard (System & AI Models) -- the backend refuses
models with no recorded metrics.

Usage:
    pip install ultralytics
    python train.py
"""
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent

DEFAULTS = {
    "WW_EPOCHS": "50",
    "WW_IMGSZ": "640",
    "WW_BATCH": "8",
    "WW_MODEL": "yolov8n.pt",
    "WW_CONF": "0.40",
    "WW_DATA_YAML": str(HERE / "data.yaml"),
    "WW_PROJECT_DIR": str(HERE / "runs"),
}


def cfg(key):
    return os.environ.get(key, DEFAULTS[key])


def check_dataset_ready(data_yaml: Path):
    dataset_dir = data_yaml.parent / "dataset"
    train_imgs = list((dataset_dir / "images" / "train").glob("*.*"))
    val_imgs = list((dataset_dir / "images" / "val").glob("*.*"))
    train_imgs = [p for p in train_imgs if p.name != ".gitkeep"]
    val_imgs = [p for p in val_imgs if p.name != ".gitkeep"]

    if not train_imgs:
        print("ERROR: dataset/images/train is empty.")
        print("Annotate images (see the annotation tool) and run:")
        print("  python dataset_manager.py split --images ../dataset/annotated/images "
              "--labels ../dataset/annotated/labels")
        print("before training. Refusing to train on an empty dataset.")
        sys.exit(1)
    if not val_imgs:
        print("ERROR: dataset/images/val is empty. A validation split is required "
              "to get real precision/recall/mAP numbers. Re-run the split step.")
        sys.exit(1)

    unlabeled = [p for p in train_imgs if not (dataset_dir / "labels" / "train" / f"{p.stem}.txt").exists()]
    if unlabeled:
        print(f"ERROR: {len(unlabeled)} training image(s) have no label file. "
              f"Run 'python dataset_manager.py validate' for the full list.")
        sys.exit(1)

    import dataset_manager as dm
    bg = dm.background_counts(("train", "val"))
    print(f"Dataset check OK: {len(train_imgs)} train / {len(val_imgs)} val images, all labeled "
          f"(background/not-waste: {bg['train']} train, {bg['val']} val).")
    if bg["train"] == len(train_imgs):
        print("ERROR: every training image is a background image -- there is no waste to learn from.")
        sys.exit(1)
    check_class_coverage()


def check_class_coverage():
    """A class the model never saw cannot be detected. Refuse to train with empty classes
    (they only produce meaningless 0 mAP rows) unless the user explicitly overrides."""
    import dataset_manager as dm
    classes = dm.load_classes()
    counts = dm.class_counts(("train",))["train"]
    empty = [n for cid, n in classes.items() if counts.get(cid, {"instances": 0})["instances"] == 0]
    thin = [n for cid, n in classes.items() if 0 < counts.get(cid, {"instances": 0})["instances"] < dm.MIN_INSTANCES_PER_CLASS]
    if thin:
        print(f"WARNING: fewer than {dm.MIN_INSTANCES_PER_CLASS} training examples for: {', '.join(thin)}. "
              "Metrics for these classes will not be reliable.")
    if empty and os.environ.get("WW_ALLOW_EMPTY_CLASSES") != "1":
        print(f"ERROR: no training examples for class(es): {', '.join(empty)}.")
        print("Annotate examples of them, or comment them out at the END of data.yaml, "
              "or set WW_ALLOW_EMPTY_CLASSES=1 to train anyway.")
        sys.exit(1)


def main():
    data_yaml = Path(cfg("WW_DATA_YAML"))
    check_dataset_ready(data_yaml)

    from resolve_data import resolved_data_yaml
    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics is not installed. Run: pip install ultralytics")
        sys.exit(1)

    epochs = int(cfg("WW_EPOCHS"))
    imgsz = int(cfg("WW_IMGSZ"))
    batch = int(cfg("WW_BATCH"))
    base_model = cfg("WW_MODEL")
    project_dir = cfg("WW_PROJECT_DIR")

    print(f"Training: model={base_model} epochs={epochs} imgsz={imgsz} batch={batch}")
    model = YOLO(base_model)
    results = model.train(
        data=resolved_data_yaml(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        project=project_dir,
        name="wastewatch",
        exist_ok=True,
    )

    run_dir = Path(results.save_dir)
    best_ckpt = run_dir / "weights" / "best.pt"
    if not best_ckpt.exists():
        print(f"ERROR: training finished but {best_ckpt} was not produced. Check the log above.")
        sys.exit(1)

    import json
    import dataset_manager as dm
    (run_dir / "run_info.json").write_text(json.dumps({
        "base_model": base_model, "epochs": epochs, "imgsz": imgsz, "batch": batch,
        "dataset_version": dm.dataset_version(),
        "class_counts_train": dm.class_counts(("train",))["train"],
    }, indent=2))

    print("\nTraining complete. NOTHING was deployed.")
    print(f"Run artifacts (results.csv, loss curves, confusion matrix): {run_dir}")
    print("Next: python evaluate.py --weights", best_ckpt)
    print("      python export.py --run", run_dir, "--version v1")
    print("The validation numbers in results.csv were used to pick best.pt; use evaluate.py "
          "(held-out test split) for the numbers you report.")


if __name__ == "__main__":
    main()
