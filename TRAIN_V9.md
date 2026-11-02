# WasteWatch v9 - dataset annotated (first pass) and how to train

## What changed from v8
- `training/dataset_annotated/labels/` now holds 93 YOLO label files (one per photo). The CVAT export you supplied
  (`general_waste.zip`) had **empty** label files, so these boxes were drawn by reviewing each photo (Claude), not exported from CVAT.
- Classes match `training/data.yaml`: 0 general_waste, 1 plastic, 2 paper. (The CVAT project's misspelt extra
  classes `general_Waste` / `Plastik` / `Paper` are NOT used - see `cvat_original_obj.names`.)
- The set is already split (65 train / 18 val / 10 test) and passes `python dataset_manager.py validate`.

## Honest limits (read before reporting results)
- Boxes are ROUGH, one box per waste pile/object group. Check them in CVAT/makesense.ai (import `dataset_annotated/images`
  + `labels`, class order from `classes.txt`) and tighten them. Re-run the split after any fix.
- plastic = 7 boxes, paper = 1 box. That is far too few to train those classes. Realistically this trains a single
  "waste" detector. Add 100+ labelled examples per class, or set `nc: 1` in data.yaml.
- 93 photos only, no clean/negative photos. For the WASTE vs NOT WASTE decision use `train_classifier.py --binary` with 100+ not-waste photos.
- Several photos are stock/watermarked images; photos 60 and 89 are collages. Remove them for a cleaner set.

## Train (Windows cmd)
    cd training
    python -m pip install -r requirements.txt
    python dataset_manager.py validate
    python train.py
    python evaluate.py
Report only the metrics `evaluate.py` prints on the held-out test split.
