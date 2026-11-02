WASTEWATCH COMBINED WASTE / NOT-WASTE CLASSIFICATION DATASET
==============================================================

Merged from:
- WasteWatch raw waste images
- dataset_cls.zip images from all train/val/test splits

Final verified counts (exact duplicate images removed):
- waste: 186 images
- not_waste: 186 images
- total: 372 images

Folders:
  dataset_binary_combined/
    waste/
    not_waste/

The source images are copied here and original files are unchanged. The training script
will create a fresh stratified 70/15/15 train/validation/test split and remove exact
duplicates when run. The labels inherit the folders they were supplied in; please spot-check
labels before production use. In particular, whether something is "waste" can depend on context.

TRAIN
-----
From this training directory:

  python -m pip install -r requirements.txt
  python train_classifier.py --binary ^
    --waste dataset_binary_combined/waste ^
    --not-waste dataset_binary_combined/not_waste ^
    --epochs 30 --imgsz 224 --batch 16 --version waste-not-waste-v1 --deploy

Windows PowerShell / macOS / Linux can run the command on one line:
  python train_classifier.py --binary --waste dataset_binary_combined/waste --not-waste dataset_binary_combined/not_waste --epochs 30 --imgsz 224 --batch 16 --version waste-not-waste-v1 --deploy

Notes:
- Training downloads/uses the Ultralytics YOLO classification checkpoint (default: yolov8n-cls.pt);
  internet access may be required the first time.
- A GPU is recommended. With only 372 images, results are a baseline, not production-ready.
- Keep the held-out test split untouched when evaluating changes.
- `--deploy` copies trained weights to ../backend/models/best.pt.
