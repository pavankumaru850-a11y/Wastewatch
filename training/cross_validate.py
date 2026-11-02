"""cross_validate.py -- k-fold (per source photo) estimate of the WASTE vs NOT WASTE classifier.
A single 29-image test split is too small to trust; this trains k models, each tested on photos it never saw.
    python cross_validate.py --folds 5 --epochs 30
"""
import argparse, json, statistics as st
from pathlib import Path
import build_scene_binary as b

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--folds", type=int, default=5)
ap.add_argument("--epochs", type=int, default=30)
ap.add_argument("--imgsz", type=int, default=224)
ap.add_argument("--model", default="yolov8n-cls.pt")
a = ap.parse_args()
from ultralytics import YOLO
scores = []
for f in range(a.folds):
    d = HERE / "dataset_cv"
    b.build(HERE / "dataset_annotated" / "images", HERE / "dataset_annotated" / "labels", d, folds=a.folds, fold=f)
    r = YOLO(a.model).train(data=str(d), epochs=a.epochs, imgsz=a.imgsz, batch=16, project=str(HERE / "runs"),
                            name=f"cv{f}", exist_ok=True, verbose=False, plots=False)
    m = YOLO(str(Path(r.save_dir) / "weights" / "best.pt")).val(data=str(d), split="test", imgsz=a.imgsz, verbose=False)
    scores.append(float(m.top1)); print(f"fold {f}: test top-1 = {scores[-1]:.3f}")
print(f"\n{a.folds}-fold CV top-1: mean={st.mean(scores):.3f}  min={min(scores):.3f}  max={max(scores):.3f}")
(HERE / "runs" / "cv_results.json").write_text(json.dumps({"folds": scores, "mean": st.mean(scores)}, indent=2))
