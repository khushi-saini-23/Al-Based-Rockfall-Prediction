# Local image-analysis weights

Run `python scripts/setup_vision_demo.py` from `backend/` after installing
`requirements-vision.txt`. This downloads and verifies Ultralytics' official
YOLO11 nano weights. The binary is ignored by Git. This general object detector
recognizes ordinary classes such as people and vehicles. It is **not** a
geological rockfall detector and its outputs do not affect risk assessments or
alerts.

To use separately reviewed task-specific weights instead, set
`GEOLOGICAL_YOLO_WEIGHTS` to a trusted local `.pt` file. Its results remain
unvalidated until evaluated on suitable open-pit mine images.
