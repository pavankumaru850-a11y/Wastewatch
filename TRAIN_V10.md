# WasteWatch v10 - trained WASTE vs NOT WASTE classifier

The classifier checkpoint (YOLOv8n-cls, 2 classes: `waste`, `not_waste`) is retained at
`backend/models/versions/waste-not-waste-v2.pt`. The active `backend/models/best.pt` is now the item-localization detector
described in the project README. The backend requirements include Ultralytics and PyTorch.

## How it was trained
Your `dataset_binary_combined/not_waste` folder was 186 TrashNet photos of single paper sheets on a plain table. Training on
that makes the model learn "table vs outdoors", not "waste vs clean", so it was NOT used for this model. Instead
`training/build_scene_binary.py` builds the dataset from your 93 annotated roadside photos:
- `waste`     = the full photo
- `not_waste` = crops that do not touch any waste box (road, sky, trees, buildings, clean pavement)
- split per SOURCE PHOTO (65 / 14 / 14 photos), so a photo and its crops are never in different splits.

Command used: `python train_classifier.py --scenes --epochs 40 --imgsz 224 --batch 16 --version waste-not-waste-v1 --deploy`
(about 2.5 minutes on CPU).

## Results (real, measured)
| Check | Result |
|---|---|
| Held-out test split (29 images from 14 unseen photos) | 100% top-1 |
| 5-fold cross-validation by photo (`cross_validate.py`) | mean 99.0%, folds 100 / 100 / 100 / 100 / 94.9% |
| Backend `run_detection` on the 29 test images | 15/15 WASTE_DETECTED, 14/14 NOT_WASTE |
| Tight crops of the waste boxes from unseen photos | 10 of 15 called waste |
| Non-roadside images (skimage samples) | mixed: some correct, some wrong |
| TrashNet paper-on-table photos | 43% called waste |

## Honest limits
1. Small data: 93 photos. The 99% is for roadside street photos like yours. Close-ups and unrelated images are unreliable.
2. Negatives are crops of the same photos; a few may contain small unlabelled waste, and the boxes were first-pass (drawn
   by Claude, not CVAT). Re-check boxes, then re-run training.
3. It decides waste vs not-waste for the whole photo. It does not locate waste or tell plastic from paper
   (only 7 plastic and 1 paper boxes exist). Keep the admin "It is waste" correction button in use.
4. To improve: add 100+ real phone photos of clean roads, empty drains, pavements, shops, people (`dataset_annotated/` style
   is not required, put them in `training/extra_not_waste/` and pass `--not-waste training/extra_not_waste` with the older
   `--binary` mode, or extend build_scene_binary.py), then re-train.

## Re-train
    cd training
    pip install -r requirements.txt
    python train_classifier.py --scenes --epochs 40 --batch 16 --version waste-not-waste-v2 --deploy
    python cross_validate.py --folds 5
The first run downloads the small pretrained `yolov8n-cls.pt` start weights automatically; `training/dataset_cls/` is regenerated each run.
The deployed weights live in `backend/models/best.pt` and `backend/models/versions/waste-not-waste-v1.pt`.
