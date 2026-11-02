# AI training guide

## What the AI decides: WASTE or NOT WASTE

The app only needs a yes/no per photo. A photo the AI calls waste goes through the normal waste workflow (notification,
hotspot, priority, cleanup). A photo it calls not waste is stored separately (dashboard "Not Waste" page) and never counted as waste.
The backend treats any class named `not_waste` (also `non_waste`, `no_waste`, `clean`, `background`) as "not waste"; every other class, or a detection box, as waste.

### Quickest route: a 2-class classifier (no boxes to draw)
```bat
cd training
python train_classifier.py --binary --waste ..\dataset\raw C:\data\dataset-resized --not-waste C:\data\not_waste --deploy
```
Needs photos of BOTH kinds (100+ each is the minimum for something usable). Not-waste photos should look like real use:
clean roadside, empty drains, shops, people, animals. Install the backend requirements (`pip install -r ../backend/requirements.txt`)
and restart the backend after deploying new weights.
The older box-detector pipeline below still works with a single class `waste`; add not-waste photos with `python dataset_manager.py add-negatives --images <folder>`.

## Pipeline
```
collect images -> annotate (YOLO boxes) -> split train/val/test -> train -> evaluate on TEST -> export a version -> activate in dashboard
```
All commands run from `training/` (`pip install -r requirements.txt`; `ultralytics` pulls in PyTorch):

| Step | Command | Result |
|---|---|---|
| 1. Collect | put photos in `dataset/raw/` (already has some). Dashboard "Add to training dataset" also queues verified citizen reports | images |
| 2. Annotate | LabelImg, CVAT or Roboflow, export **YOLO** format (one `.txt` per image: `class x_center y_center width height`, 0-1) | labels |
| 3. Split | `python dataset_manager.py split --images <imgs> --labels <lbls>` | `dataset/{images,labels}/{train,val,test}` (70/20/10, pairs stay together, seeded) |
| 4. Check | `python dataset_manager.py validate` then `python dataset_manager.py stats` | catches bad class ids, out-of-range boxes, missing labels, the same image in two splits; shows per-class counts and a **dataset version** fingerprint |
| 5. Train | `python train.py` (options are environment variables: `WW_EPOCHS` (50), `WW_IMGSZ` (640), `WW_BATCH` (8), `WW_MODEL` (yolov8n.pt); Windows: `set WW_EPOCHS=80`) | `runs/wastewatch/` with loss curves (`results.png`), `results.csv`, weights. **Nothing is deployed.** |
| 6. Evaluate | `python evaluate.py --weights runs/wastewatch/weights/best.pt` | `evaluation.json` with precision, recall, mAP@50, mAP@50-95, per-class AP; confusion matrix + PR curves in `runs/wastewatch/eval_test/` |
| 7. Register | `python export.py --run runs/wastewatch --version v1 --notes "..."` | `backend/models/wastewatch_v1/` (weights, metrics, curves, confusion matrix) and an entry in `backend/models/model_versions.json` |
| 8. Activate | Dashboard -> **System & AI Models** -> Activate (or `export.py --deploy`) | hot-swaps the live model; survives restarts |

`export.py` refuses a run without `evaluation.json`, and activation refuses a model whose file is missing, has no recorded metrics, has mAP50 = 0, or fails to load (the previous model keeps serving).

## Folded / plain paper
The old "Unsupported data" message came from the model returning nothing for hard images. The application now shows a real message instead. **Whether the model actually recognises folded paper depends on training data, not code.** To fix it properly:
1. Photograph folded, crumpled and flat paper in many settings (indoor, roadside, wet, shaded, on grass/tarmac) - aim for **at least 150-200 annotated paper images**, more for variety.
2. Also include hard negatives (leaves, cloth, plastic sheets, cardboard) so the model learns what paper is *not*.
3. Annotate tightly with class `2 paper`, run steps 3-7, and compare **per-class recall for paper** in `evaluation.json` before and after.

## Reporting results honestly
* Quote the **test-split** numbers from `evaluation.json` together with the image count (`metrics_images` in the registry). Below ~30 test images the numbers are noise (`evaluate.py` prints a warning).
* Never quote an accuracy you did not measure. Validation numbers in `results.csv` were used to pick the best epoch, so they are optimistic.
* Mention the dataset version (`dataset_manager.py stats`) next to every model.
* Known limitations to state: small dataset, roadside domain shift (lighting, camera), class imbalance, no field trial yet.

## Testing the pipeline without a GPU
`training/tests/` (pytest) checks the dataset tools, the class-coverage guard, the evaluation report builder and the export/registry rules on synthetic data - no PyTorch needed. Run: `cd training && python -m pytest tests`.
