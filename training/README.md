## Combined WASTE vs NOT_WASTE dataset (added)

The folder `dataset_binary_combined/` combines the WasteWatch raw waste photos with the supplied
`dataset_cls.zip` waste and not-waste classes. It contains 186 waste + 186 not-waste images
(372 total). See `dataset_binary_combined/README_COMBINED_DATASET.txt` for counts and training steps.

Quick training command from this folder:

```bat
python -m pip install -r requirements.txt
python train_classifier.py --binary --waste dataset_binary_combined/waste --not-waste dataset_binary_combined/not_waste --epochs 30 --imgsz 224 --batch 16 --version waste-not-waste-v1 --deploy
```

# WasteWatch — dataset & training pipeline

## Goal: WASTE or NOT WASTE

The app only needs a yes/no decision per photo, so there are no waste types any more.
Quickest route (no annotation): a 2-class photo classifier.

```bat
cd training
pip install ultralytics
python train_classifier.py --binary ^
    --waste ..\dataset\raw C:\data\dataset-resized ^
    --not-waste C:\data\not_waste --deploy
```

- `--waste` takes any number of folders (searched recursively); `--not-waste` likewise.
- Duplicates are removed and the bigger class is capped at 2x the smaller one (`--max-ratio`), so the
  model does not just answer "waste" every time. Aim for 100+ photos per class.
- Make the not-waste photos look like your real use: clean roadside, empty drains, shops, people, animals.
  A model trained on tidy product photos only will not recognise a pile of roadside garbage.
- `--deploy` writes `backend/models/best.pt`. Install `ultralytics` in the backend too, then restart it.

The older detector path (`train.py`, boxes) now has a single class `waste`; not-waste photos go in with
`dataset_manager.py add-negatives`.

## What's actually in `wasteimages.zip`

Verified by scanning the file (not assumed):

- **95 JPEGs**, all valid, none corrupt.
- ~5.4 MB total. Dimensions range from 250×150 up to 738×728 — mixed sizes, mixed
  aspect ratios, mostly wide roadside/street scenes rather than tight product shots.
- **2 duplicate pairs** by content hash: `7.jpg`==`6.jpg`, `77.jpg`==`75.jpg`.
  Drop the duplicates before annotating so the same photo doesn't end up in both
  train and val.
- **Zero label files.** No bounding boxes, no class assignments. This is a raw
  photo dump, not a YOLO dataset yet — nothing in this folder can train a model
  until someone draws boxes and assigns classes.
- Spot-checked several images: they're wide scene shots of roadside garbage piles,
  a municipal collection truck, mixed trash — not close-ups of single isolated
  items. That affects what's realistic to detect: expect the model to learn
  "garbage pile" / "general_waste" style detections more reliably than fine
  distinctions like paper-vs-plastic on a cluttered pile, unless the boxes you
  draw are tight and consistent.

## Pipeline in this folder

```
dataset_manager.py   validate dataset/, or split annotated images+labels into train/val/test
train.py              fine-tunes a YOLOv8 checkpoint on dataset/, writes backend/models/best.pt
validate.py           re-runs validation on a checkpoint, prints real precision/recall/mAP
export.py             registers a trained run as a model_versions record, optionally deploys it
data.yaml             class list + dataset paths (edit this to add new waste classes)
dataset/              images/{train,val,test} + labels/{train,val,test} — currently empty
```

`../dataset/raw/` holds the 95 original images, untouched, as a reference copy.

## The step that's missing: annotation

None of these scripts can invent bounding boxes. Use the annotation tool
(published as a separate artifact) to load the images and draw boxes with class
labels, then export a YOLO-format ZIP (`images/` + `labels/` + `classes.txt`).

Once you have that export:

```bash
cd training
unzip ~/Downloads/wastewatch_annotations.zip -d ../dataset/annotated
pip install pyyaml
python dataset_manager.py validate            # sanity-check nothing's malformed
python dataset_manager.py split \
    --images ../dataset/annotated/images \
    --labels ../dataset/annotated/labels \
    --train 0.7 --val 0.2 --test 0.1
```

Then train:

```bash
pip install ultralytics
python train.py            # defaults: epochs=50, imgsz=640, batch=8, yolov8n.pt base
python validate.py --weights ../backend/models/best.pt --split test
```

`train.py` refuses to run if `dataset/images/train` or `dataset/images/val` is
empty, or if any training image has no matching label — on purpose, so it can't
silently produce a model trained on nothing.

## Adding "not waste" images (negatives)

To stop the model flagging clean streets, empty drains, parks, people or vehicles as waste,
add photos that contain **no waste**. In YOLO these are *background images*: an image with an
empty `.txt` label file. No boxes, no new class.

```bash
# put your not-waste photos in any folder, then:
python dataset_manager.py add-negatives --images ../dataset/not_waste
python dataset_manager.py stats      # shows a "(background)" row per split
python dataset_manager.py validate   # empty labels are valid, counted as background
```

- Images are split 70/20/10 into train/val/test and saved as `neg_<name>.jpg` + empty `neg_<name>.txt`.
- Exact duplicates (of each other or of images already in the dataset) are skipped.
- Add `--move` to move instead of copy; `--train/--val/--test` change the ratios.
- Keep negatives to roughly **10% or less** of the dataset; the tool warns above that.
- Best negatives are *look-alikes*: wet roads, shadows, leaves, bags of shopping, parked bikes, clean drains.
- Do not box anything in these images. If an image has any waste in it, annotate it normally instead.

## Honest expectations for 95 images

95 images is a small dataset for object detection, even split across only 4
classes. Realistic outcomes:

- A YOLOv8n fine-tune will run and produce *some* numbers, but precision/recall
  on that few examples per class will likely be noisy and not production-grade.
  Report exactly what `validate.py` prints — don't round up.
- More images per class (aim for 100+ *annotated instances* per class, not per
  photo) will matter more than any hyperparameter tweak at this stage.
- Data augmentation (Ultralytics' defaults: flips, HSV jitter, mosaic) is already
  on and helps some, but doesn't substitute for more labeled examples.

## Configuration

All of `train.py`'s settings are environment variables (see the top of the file):
`WW_EPOCHS`, `WW_IMGSZ`, `WW_BATCH`, `WW_MODEL`, `WW_DATA_YAML`, `WW_PROJECT_DIR`.
Nothing is hard-coded to a path outside this repo.
