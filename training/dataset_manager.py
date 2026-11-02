"""
dataset_manager.py

Utility for preparing and validating the WasteWatch YOLO dataset.

Two things it does, as two subcommands:

  validate  -- scan dataset/images/* and dataset/labels/* and report:
               missing images, missing labels, invalid YOLO lines,
               unknown class ids, empty annotation files,
               out-of-range coordinates, duplicate images (by content hash)

  stats     -- per-class counts, background-image counts, dataset version

  add-negatives -- add "NOT waste" photos (clean streets, empty drains, parks,
               people, vehicles...) as YOLO *background* images: an image with an
               empty label file. They teach the detector what NOT to flag.

  split     -- take annotated images + labels sitting in one folder
               (e.g. what the browser annotation tool exports) and split
               them into dataset/images/{train,val,test} and
               dataset/labels/{train,val,test} at a given ratio.

Nothing here trains a model or invents labels -- it only checks and
organizes files that already exist. Run with --help for options.

Examples:
    python dataset_manager.py validate
    python dataset_manager.py add-negatives --images ../dataset/not_waste
    python dataset_manager.py split --images ../dataset/annotated/images \\
        --labels ../dataset/annotated/labels --train 0.7 --val 0.2 --test 0.1
"""
import argparse
import hashlib
import random
import shutil
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

import os

HERE = Path(os.environ.get("WW_TRAINING_DIR") or Path(__file__).resolve().parent)  # env override is for tests
DATA_YAML = HERE / "data.yaml"
MAX_BACKGROUND_RATIO = 0.10  # Ultralytics suggests keeping background images to ~0-10% of the dataset
MIN_INSTANCES_PER_CLASS = 30  # below this a class is too thin to trust; see docs/ai-training.md
IMG_EXTS = {".jpg", ".jpeg", ".png"}


def load_classes() -> dict:
    if yaml is None:
        print("PyYAML not installed (pip install pyyaml). Cannot read data.yaml.")
        sys.exit(1)
    with open(DATA_YAML) as f:
        cfg = yaml.safe_load(f)
    return {int(k): v for k, v in cfg["names"].items()}


def file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def validate():
    classes = load_classes()
    max_class_id = max(classes.keys())
    dataset_dir = HERE / "dataset"
    issues = {
        "missing_labels": [],
        "missing_images": [],
        "invalid_lines": [],
        "unknown_class_id": [],
        "bad_coords": [],
    }
    seen_hashes = {}
    duplicates = []
    total_images = 0
    background = 0  # images with an empty label file = valid "no waste here" negatives

    for split in ("train", "val", "test"):
        img_dir = dataset_dir / "images" / split
        lbl_dir = dataset_dir / "labels" / split
        images = sorted(p for p in img_dir.glob("*") if p.suffix.lower() in IMG_EXTS)
        labels = sorted(p for p in lbl_dir.glob("*.txt"))
        label_stems = {p.stem for p in labels}
        image_stems = {p.stem for p in images}

        for img in images:
            total_images += 1
            h = file_hash(img)
            if h in seen_hashes:
                duplicates.append((str(img.relative_to(HERE)), seen_hashes[h]))
            else:
                seen_hashes[h] = str(img.relative_to(HERE))
            if img.stem not in label_stems:
                issues["missing_labels"].append(str(img.relative_to(HERE)))

        for lbl in labels:
            if lbl.stem not in image_stems:
                issues["missing_images"].append(str(lbl.relative_to(HERE)))
                continue
            lines = [l.strip() for l in lbl.read_text().splitlines() if l.strip()]
            if not lines:
                background += 1  # valid YOLO background/negative image
                continue
            for line in lines:
                parts = line.split()
                if len(parts) != 5:
                    issues["invalid_lines"].append(f"{lbl.relative_to(HERE)}: '{line}'")
                    continue
                try:
                    cls_id = int(parts[0])
                    coords = [float(x) for x in parts[1:]]
                except ValueError:
                    issues["invalid_lines"].append(f"{lbl.relative_to(HERE)}: '{line}'")
                    continue
                if cls_id < 0 or cls_id > max_class_id:
                    issues["unknown_class_id"].append(f"{lbl.relative_to(HERE)}: class {cls_id}")
                if not all(0.0 <= c <= 1.0 for c in coords):
                    issues["bad_coords"].append(f"{lbl.relative_to(HERE)}: '{line}'")

    print(f"Scanned {total_images} images across train/val/test "
          f"({background} background / not-waste, {total_images - background} with waste labels).\n")
    if total_images and background / total_images > MAX_BACKGROUND_RATIO:
        print(f"NOTE: background images are {background / total_images:.0%} of the dataset "
              f"(>{MAX_BACKGROUND_RATIO:.0%}). Too many negatives can make the model under-detect real waste.\n")
    any_issue = False
    for key, items in issues.items():
        if items:
            any_issue = True
            print(f"[{key}] {len(items)} issue(s):")
            for i in items[:15]:
                print(f"   - {i}")
            if len(items) > 15:
                print(f"   ... and {len(items) - 15} more")
            print()
    if duplicates:
        any_issue = True
        print(f"[duplicate_images] {len(duplicates)} duplicate(s):")
        for a, b in duplicates[:15]:
            print(f"   - {a}  ==  {b}")
        print()

    if not any_issue:
        print("No issues found. Dataset is structurally valid YOLO format.")
    return 1 if any_issue else 0


def class_counts(splits=("train", "val", "test")) -> dict:
    """{split: {class_id: {"instances": n, "images": n}}} from the YOLO label files on disk."""
    out = {}
    for split in splits:
        per = {}
        for lbl in sorted((HERE / "dataset" / "labels" / split).glob("*.txt")):
            seen = set()
            for line in lbl.read_text().splitlines():
                parts = line.split()
                if len(parts) != 5:
                    continue
                try:
                    cid = int(parts[0])
                except ValueError:
                    continue
                d = per.setdefault(cid, {"instances": 0, "images": 0})
                d["instances"] += 1
                if cid not in seen:
                    d["images"] += 1
                    seen.add(cid)
        out[split] = per
    return out


def background_counts(splits=("train", "val", "test")) -> dict:
    """{split: number of images whose label file is empty (not-waste negatives)}."""
    out = {}
    for split in splits:
        n = 0
        for lbl in (HERE / "dataset" / "labels" / split).glob("*.txt"):
            if not lbl.read_text().strip():
                n += 1
        out[split] = n
    return out


def dataset_version() -> str:
    """Short content fingerprint of the current dataset (file names + sizes), stored with every model."""
    h = hashlib.sha1()
    for split in ("train", "val", "test"):
        for sub in ("images", "labels"):
            for f in sorted((HERE / "dataset" / sub / split).glob("*")):
                if f.name != ".gitkeep":
                    h.update(f"{sub}/{split}/{f.name}:{f.stat().st_size}".encode())
    return h.hexdigest()[:10]


def stats() -> int:
    classes = load_classes()
    counts = class_counts()
    print("Dataset statistics (from label files on disk)\n")
    print(f"{'class':<18}" + "".join(f"{sp:>16}" for sp in ("train", "val", "test")))
    thin = []
    for cid, name in sorted(classes.items()):
        row = f"{name:<18}"
        for sp in ("train", "val", "test"):
            d = counts[sp].get(cid, {"instances": 0, "images": 0})
            row += f"{str(d['instances']) + ' obj/' + str(d['images']) + ' img':>16}"
        print(row)
        if counts["train"].get(cid, {"instances": 0})["instances"] < MIN_INSTANCES_PER_CLASS:
            thin.append(name)
    bg = background_counts()
    row = f"{'(background)':<18}" + "".join(f"{str(bg[sp]) + ' img':>16}" for sp in ("train", "val", "test"))
    print(row)
    print(f"\nDataset version: {dataset_version()}")
    if thin:
        print(f"\nWARNING: fewer than {MIN_INSTANCES_PER_CLASS} training examples for: {', '.join(thin)}.")
        print("Annotate more images of these classes (or remove them from data.yaml) before trusting their metrics.")
    return 0


def split(images_dir: str, labels_dir: str, train: float, val: float, test: float, seed: int):
    assert abs(train + val + test - 1.0) < 1e-6, "train+val+test ratios must sum to 1.0"
    src_images = Path(images_dir)
    src_labels = Path(labels_dir)
    images = sorted(p for p in src_images.glob("*") if p.suffix.lower() in IMG_EXTS)
    if not images:
        print(f"No images found in {src_images}")
        return 1

    random.seed(seed)
    random.shuffle(images)
    n = len(images)
    n_train = int(n * train)
    n_val = int(n * val)
    splits = {
        "train": images[:n_train],
        "val": images[n_train:n_train + n_val],
        "test": images[n_train + n_val:],
    }

    dataset_dir = HERE / "dataset"
    skipped_no_label = []
    for split_name, imgs in splits.items():
        img_out = dataset_dir / "images" / split_name
        lbl_out = dataset_dir / "labels" / split_name
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)
        for img in imgs:
            label_path = src_labels / f"{img.stem}.txt"
            if not label_path.exists():
                skipped_no_label.append(img.name)
                continue
            shutil.copy2(img, img_out / img.name)
            shutil.copy2(label_path, lbl_out / label_path.name)

    for split_name, imgs in splits.items():
        placed = len([i for i in imgs if (src_labels / f'{i.stem}.txt').exists()])
        print(f"{split_name}: {placed} image+label pairs")

    if skipped_no_label:
        print(f"\nSkipped {len(skipped_no_label)} image(s) with no matching label "
              f"(annotate them first):")
        for name in skipped_no_label[:15]:
            print(f"   - {name}")
        if len(skipped_no_label) > 15:
            print(f"   ... and {len(skipped_no_label) - 15} more")
    return 0


def add_negatives(images_dir: str, train: float, val: float, test: float, seed: int, move: bool = False):
    """Register 'not waste' photos as YOLO background images (empty label file each).
    Skips exact duplicates of anything already in the dataset or earlier in this batch."""
    assert abs(train + val + test - 1.0) < 1e-6, "train+val+test ratios must sum to 1.0"
    src = Path(images_dir)
    images = sorted(p for p in src.rglob("*") if p.suffix.lower() in IMG_EXTS)
    if not images:
        print(f"No images found in {src}")
        return 1

    dataset_dir = HERE / "dataset"
    seen = {}
    for sp in ("train", "val", "test"):
        for f in (dataset_dir / "images" / sp).glob("*"):
            if f.suffix.lower() in IMG_EXTS:
                seen[file_hash(f)] = f.name
    fresh, dupes = [], 0
    for img in images:
        h = file_hash(img)
        if h in seen:
            dupes += 1
            continue
        seen[h] = img.name
        fresh.append(img)
    if not fresh:
        print(f"All {len(images)} image(s) were duplicates of images already in the dataset.")
        return 1

    random.Random(seed).shuffle(fresh)
    n = len(fresh)
    n_train = int(n * train)
    n_val = int(n * val)
    parts = {"train": fresh[:n_train], "val": fresh[n_train:n_train + n_val], "test": fresh[n_train + n_val:]}
    for sp, imgs in parts.items():
        img_out = dataset_dir / "images" / sp
        lbl_out = dataset_dir / "labels" / sp
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)
        for img in imgs:
            name = f"neg_{img.stem}{img.suffix.lower()}"
            k = 1
            while (img_out / name).exists():  # never overwrite an existing file
                name = f"neg_{img.stem}_{k}{img.suffix.lower()}"
                k += 1
            (shutil.move if move else shutil.copy2)(img, img_out / name)
            (lbl_out / f"{Path(name).stem}.txt").write_text("")  # empty label = nothing to detect
        print(f"{sp}: {len(imgs)} background image(s)")
    print(f"\nAdded {n} not-waste image(s); skipped {dupes} duplicate(s).")
    bg = sum(background_counts().values())
    total = sum(len([f for f in (dataset_dir / 'images' / sp).glob('*') if f.suffix.lower() in IMG_EXTS])
                for sp in ("train", "val", "test"))
    if total and bg / total > MAX_BACKGROUND_RATIO:
        print(f"NOTE: background images are now {bg / total:.0%} of the dataset (suggested max "
              f"{MAX_BACKGROUND_RATIO:.0%}). Add more labeled waste photos to rebalance.")
    return 0


def main():
    p = argparse.ArgumentParser(description="WasteWatch dataset validate/split tool")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="Check dataset/images + dataset/labels for problems")
    sub.add_parser("stats", help="Per-class / per-split counts and dataset version")

    ng = sub.add_parser("add-negatives", help="Add 'not waste' photos as background (empty-label) images")
    ng.add_argument("--images", required=True, help="Folder of photos that contain NO waste")
    ng.add_argument("--train", type=float, default=0.7)
    ng.add_argument("--val", type=float, default=0.2)
    ng.add_argument("--test", type=float, default=0.1)
    ng.add_argument("--seed", type=int, default=42)
    ng.add_argument("--move", action="store_true", help="move instead of copy the source files")

    sp = sub.add_parser("split", help="Split annotated images+labels into train/val/test")
    sp.add_argument("--images", required=True, help="Folder of annotated images")
    sp.add_argument("--labels", required=True, help="Folder of matching YOLO .txt labels")
    sp.add_argument("--train", type=float, default=0.7)
    sp.add_argument("--val", type=float, default=0.2)
    sp.add_argument("--test", type=float, default=0.1)
    sp.add_argument("--seed", type=int, default=42)

    args = p.parse_args()
    if args.command == "validate":
        sys.exit(validate())
    elif args.command == "stats":
        sys.exit(stats())
    elif args.command == "add-negatives":
        sys.exit(add_negatives(args.images, args.train, args.val, args.test, args.seed, args.move))
    elif args.command == "split":
        sys.exit(split(args.images, args.labels, args.train, args.val, args.test, args.seed))


if __name__ == "__main__":
    main()
