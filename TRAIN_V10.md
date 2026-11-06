# WasteWatch v10 - waste / not-waste classifiers

The active `backend/models/best.pt` remains the item-localization detector.
Classifier checkpoints are kept separately in `backend/models/versions/` and
are registered in `backend/models/model_versions.json`.

## Latest training run: waste-not-waste-v3

Trained with `training/train_classifier.py` on
`training/dataset_binary_combined/waste` and
`training/dataset_binary_combined/not_waste`:

```powershell
python train_classifier.py --binary --waste .\dataset_binary_combined\waste --not-waste .\dataset_binary_combined\not_waste --epochs 30 --imgsz 224 --batch 16 --version waste-not-waste-v3
```

The trainer removed exact duplicate images before splitting. The saved
`training/dataset_cls/` is the split used for this run:

| Split | not_waste | waste | Total |
|---|---:|---:|---:|
| Train | 283 | 410 | 693 |
| Validation | 60 | 87 | 147 |
| Held-out test | 62 | 89 | 151 |
| Total | 405 | 586 | 991 |

The source folders contain 1,084 images before duplicate removal. The model
achieved **99.34% top-1 accuracy** on the held-out test split and is registered
as `waste-not-waste-v3` at
`backend/models/versions/waste-not-waste-v3.pt`. It is not deployed; the
active detector is unchanged.

The split is random by image, not grouped by original scene, so similar or
related photos may occur across splits. The two-class top-5 score is not
informative. Treat the test result as a preliminary measurement, not evidence
of production performance. Validate on new, independently collected field
photos before using this classifier operationally.

## Existing deployed classifier versions

`waste-not-waste-v1` and `waste-not-waste-v2` are earlier classifiers. The
model version registry records their measured metrics and deployment status.
Their historical training details should not be inferred from the latest v3
run.
