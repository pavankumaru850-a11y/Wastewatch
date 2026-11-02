WASTEWATCH PAPER + PLASTIC DATASET PREPARATION

Images copied from the supplied wasteimages dataset are in images/. They are UNANNOTATED.
Do not run the split command until every image has a matching YOLO .txt annotation in labels/.

Target classes (must match training/data.yaml):
0 general_waste
1 plastic
2 paper

Use CVAT or makesense.ai: create bounding boxes around each visible waste object and assign the correct class.
Export YOLO detection labels. Ensure image and label basenames match, e.g. 1.jpg and 1.txt.
If an image contains multiple types, annotate each object with its own class. Do not label an object as paper/plastic unless it is clearly identifiable.

The supplied photos are not automatically class-labelled, and no model has been trained by this preparation step. Add more diverse plastic and paper examples plus clean/no-waste images before claiming reliable performance.

UPDATE (v9): labels/ now contains first-pass YOLO boxes for all 93 images (see ../../TRAIN_V9.md). Review and tighten them.
