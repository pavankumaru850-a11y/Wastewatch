"""
build_scene_binary.py -- builds a WASTE vs NOT WASTE classification dataset from the
annotated roadside photos in dataset_annotated/ (images + YOLO boxes).

WHY THIS EXISTS
  The old dataset_binary_combined/not_waste folder holds 186 TrashNet photos of single sheets of
  paper on a plain studio background. A model trained on those learns "studio table vs outdoor
  scene" (it scores ~100% and is useless on a real clean road). Here the negatives come from the
  SAME roadside photos: regions that lie outside every waste box (road, sky, grass, buildings,
  clean pavement), so the model has to learn what waste looks like, not what the background is.

  * waste     = the full photo (it contains labelled waste)
  * not_waste = random crops that do not overlap any waste box (padded by BOX_PAD)

LEAKAGE GUARD
  Splitting is done per SOURCE PHOTO. A photo and every crop taken from it always land in the same
  split, so test scores are not inflated by near-identical images.

Usage:
    python build_scene_binary.py                 # writes dataset_cls/{train,val,test}/{waste,not_waste}
    python build_scene_binary.py --folds 5 --fold 2   # k-fold split (for cross_validate.py)
"""
import argparse
import random
import shutil
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
IMG_EXTS = {".jpg", ".jpeg", ".png"}
MAX_OVERLAP = 0.0        # a not_waste crop may not touch any (padded) waste box
BOX_PAD = 0.08           # boxes are rough, grow them by 8% of image size before testing overlap
MIN_CROP_SIDE = 0.28     # crop sides are 28%..60% of the image side
MAX_CROP_SIDE = 0.60
CROPS_PER_IMAGE = 3


def read_boxes(label_file: Path):
    boxes = []
    if label_file.exists():
        for line in label_file.read_text().splitlines():
            p = line.split()
            if len(p) >= 5:
                _, x, y, w, h = int(p[0]), *map(float, p[1:5])
                boxes.append((x - w / 2 - BOX_PAD, y - h / 2 - BOX_PAD, x + w / 2 + BOX_PAD, y + h / 2 + BOX_PAD))
    return boxes


def overlap_frac(crop, boxes):
    """Fraction of the crop covered by the union of boxes (grid sampling, good enough)."""
    x1, y1, x2, y2 = crop
    n, hit = 24, 0
    for i in range(n):
        for j in range(n):
            px, py = x1 + (x2 - x1) * (i + .5) / n, y1 + (y2 - y1) * (j + .5) / n
            if any(b[0] <= px <= b[2] and b[1] <= py <= b[3] for b in boxes):
                hit += 1
    return hit / (n * n)


def negative_crops(boxes, w, h, rng, want=CROPS_PER_IMAGE, tries=200):
    found = []
    for _ in range(tries):
        if len(found) >= want:
            break
        cw = rng.uniform(MIN_CROP_SIDE, MAX_CROP_SIDE)
        ch = rng.uniform(MIN_CROP_SIDE, MAX_CROP_SIDE)
        x1, y1 = rng.uniform(0, 1 - cw), rng.uniform(0, 1 - ch)
        crop = (x1, y1, x1 + cw, y1 + ch)
        if overlap_frac(crop, boxes) > MAX_OVERLAP:
            continue
        # keep crops that are not near-duplicates of one already taken from this photo
        if any(abs(crop[0] - c[0]) < .15 and abs(crop[1] - c[1]) < .15 for c in found):
            continue
        found.append(crop)
    return found


def build(images_dir: Path, labels_dir: Path, out: Path, ratios=(0.70, 0.15, 0.15), seed=42,
          folds=0, fold=0):
    rng = random.Random(seed)
    sources = sorted(p for p in images_dir.iterdir() if p.suffix.lower() in IMG_EXTS)
    if not sources:
        raise SystemExit(f"No images in {images_dir}")
    order = sources[:]
    rng.shuffle(order)

    if folds:
        # k-fold: this fold = test, next fold = val, the rest = train
        k = len(order) / folds
        chunk = lambda i: order[int(round(i * k)):int(round((i + 1) * k))]  # noqa: E731
        test, val = chunk(fold % folds), chunk((fold + 1) % folds)
        held = set(test) | set(val)
        split_of = {p: "test" for p in test}
        split_of.update({p: "val" for p in val})
        split_of.update({p: "train" for p in order if p not in held})
    else:
        n = len(order)
        n_train, n_val = int(n * ratios[0]), int(n * ratios[1])
        split_of = {}
        for i, p in enumerate(order):
            split_of[p] = "train" if i < n_train else "val" if i < n_train + n_val else "test"

    if out.exists():
        shutil.rmtree(out)
    counts = {s: {"waste": 0, "not_waste": 0} for s in ("train", "val", "test")}
    for p in sources:
        split = split_of[p]
        img = Image.open(p).convert("RGB")
        w, h = img.size
        for cls in ("waste", "not_waste"):
            (out / split / cls).mkdir(parents=True, exist_ok=True)
        img.save(out / split / "waste" / f"{p.stem}.jpg", quality=92)
        counts[split]["waste"] += 1
        for i, (x1, y1, x2, y2) in enumerate(negative_crops(read_boxes(labels_dir / f"{p.stem}.txt"), w, h, rng)):
            img.crop((int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h))).save(
                out / split / "not_waste" / f"{p.stem}_bg{i}.jpg", quality=92)
            counts[split]["not_waste"] += 1
    print(f"Scene dataset written to {out}")
    for s, c in counts.items():
        print(f"  {s:<5} waste={c['waste']:<4} not_waste={c['not_waste']}")
    return counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", default=str(HERE / "dataset_annotated" / "images"))
    ap.add_argument("--labels", default=str(HERE / "dataset_annotated" / "labels"))
    ap.add_argument("--out", default=str(HERE / "dataset_cls"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--folds", type=int, default=0)
    ap.add_argument("--fold", type=int, default=0)
    a = ap.parse_args()
    build(Path(a.images), Path(a.labels), Path(a.out), seed=a.seed, folds=a.folds, fold=a.fold)
