"""Local YOLO inference with explicit geological and general-demo modes."""

from __future__ import annotations

import os
from functools import lru_cache
from io import BytesIO
from pathlib import Path

DEMO_WEIGHTS = Path(__file__).resolve().parents[2] / "vision_models" / "yolo11n.pt"


class VisionUnavailable(RuntimeError):
    pass


def weights_path() -> Path | None:
    configured = os.getenv("GEOLOGICAL_YOLO_WEIGHTS", "").strip()
    return Path(configured).expanduser() if configured else (DEMO_WEIGHTS if DEMO_WEIGHTS.is_file() else None)


def status() -> dict:
    path = weights_path()
    if path is None or not path.is_file():
        return {"available": False, "reason": "No local YOLO weights available; configure geological weights or install the demo model"}
    mode = "geological_unvalidated" if os.getenv("GEOLOGICAL_YOLO_WEIGHTS", "").strip() else "general_objects_demo"
    try:
        import ultralytics  # noqa: F401
        import PIL  # noqa: F401
    except ImportError:
        return {"available": False, "reason": "Install ultralytics and pillow to use configured weights"}
    reason = ("General object detector ready; it does not detect rockfall hazards or predict slope failure"
              if mode == "general_objects_demo" else
              "Geological weights configured; inference and mine-site validity remain unverified")
    return {"available": True, "mode": mode, "reason": reason, "weights_filename": path.name}


@lru_cache(maxsize=2)
def _model(path: str):
    try:
        from ultralytics import YOLO
        return YOLO(path)
    except Exception as exc:
        raise VisionUnavailable(f"Could not load configured YOLO weights: {exc}") from exc


def detect_image(data: bytes) -> dict:
    state = status()
    if not state["available"]:
        raise VisionUnavailable(state["reason"])
    try:
        from PIL import Image
        with Image.open(BytesIO(data)) as original:
            image = original.convert("RGB")
        result = _model(str(weights_path())).predict(source=image, verbose=False)[0]
        detections = []
        for box in result.boxes:
            class_id = int(box.cls.item())
            detections.append({"class_name": result.names[class_id], "confidence": round(float(box.conf.item()), 4),
                               "box_xyxy": [round(float(v), 2) for v in box.xyxy[0].tolist()]})
        is_demo = state["mode"] == "general_objects_demo"
        return {"status": "analyzed_demo_objects" if is_demo else "analyzed_unvalidated", "detections": detections,
                "image_width": image.width, "image_height": image.height,
                "annotated_image": None, "model_file": weights_path().name, "model_scope": state["mode"],
                "message": ("General YOLO object detection completed. This model does not detect rockfall hazards or predict slope failure."
                            if is_demo else
                            "YOLO objects detected using configured weights. This does not predict future rockfall or establish mine-site accuracy.")}
    except VisionUnavailable:
        raise
    except Exception as exc:
        raise VisionUnavailable(f"YOLO inference failed: {exc}") from exc
