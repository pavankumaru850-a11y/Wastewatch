# WasteWatch v8 — dataset status and next steps

## Dataset imported
The supplied `wasteimages.zip` was compared with `dataset/raw/` in this project. It contains the same 95 source files.
After removing exact duplicate copies, `dataset/raw/` contains 93 unique photos.

## Important: model training is not ready yet
The supplied photos are raw images only. They do not include YOLO bounding-box annotations or class labels.
The training folders `training/dataset/images/{train,val,test}` and `training/dataset/labels/{train,val,test}` are intentionally empty.
Do not run `python train.py` yet; it will correctly stop instead of producing a misleading model.

## What the current photos can teach
Most photos show roadside/general waste or garbage piles. They are suitable as a starting point for a one-class detector (`waste`) after bounding boxes are drawn consistently.
They are not enough to train a reliable WASTE-vs-NOT-WASTE model because there are no clean-road / clean-drain / ordinary-scene negative photos.

## Annotation workflow (Windows PowerShell or CMD)
1. Open an annotation tool that exports YOLO detection format (for example, CVAT or makesense.ai).
2. Import all images from `dataset/raw/`.
3. Draw a tight bounding box around each visible waste pile/object that you want the model to detect. Use the single class `waste` (class ID `0`) to match `training/data.yaml`.
4. Export YOLO format. Every image must have a matching `.txt` label file. Each non-empty line must be:
   `0 x_center y_center width height`
   where all four coordinates are normalized to the range 0–1. Images with no waste should have an empty label file, but the current set is mostly waste scenes.
5. Extract the export to a folder such as `training/dataset_annotated/` with `images/` and `labels/` subfolders.
6. In a terminal:
   ```bat
   cd training
   python -m pip install -r requirements.txt
   python dataset_manager.py split --images dataset_annotated\images --labels dataset_annotated\labels --train 0.7 --val 0.2 --test 0.1
   python dataset_manager.py validate
   python dataset_manager.py stats
   python train.py
   python evaluate.py
   ```
7. Only after evaluation produces real test metrics should you export/register the model and activate it from the dashboard.

## Add negative examples
Collect real photos with no roadside waste (clean road, clean drain, pavement, grass, parked vehicles, shadows, etc.). Use them as background images with empty YOLO `.txt` label files, or use `python dataset_manager.py add-negatives --images <folder>`. Keep background images to around 10% or less of the detection dataset as configured in the project.

## Dataset limitations
- 93 unique images is a small dataset; expect weak generalization until you add many more varied images and annotate them.
- Split by source/location or capture session where possible to reduce leakage from near-identical scenes.
- Never report accuracy or claim deployment-ready performance until the held-out test set has been evaluated.


## Paper and plastic dataset preparation

The supplied images are copied to `training/dataset_annotated/images` for annotation. Target classes are `general_waste` (0), `plastic` (1), and `paper` (2) in `training/data.yaml`. These images are still unannotated: create YOLO bounding-box label files in `training/dataset_annotated/labels` before running the split command. This pack does not claim a trained model or invent labels. See `training/dataset_annotated/README_FIRST.txt`.
