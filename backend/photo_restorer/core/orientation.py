from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from .types import OrientationResult


def detect_orientation(
    image_path: str | Path,
    config: dict[str, Any] | None = None,
    device: str = "cpu",
) -> OrientationResult:
    """Detect photo orientation (0/90/180/270) using Xception-based classifier.

    Falls back to conservative default (angle=0) when the model is unavailable.
    """
    config = config or {}
    auto_rotate = config.get("auto_rotate", True)
    min_confidence = config.get("min_confidence", 0.75)

    if not auto_rotate:
        return OrientationResult(angle=0, confidence=0.0, evidence=["auto_rotate_disabled"])

    try:
        import torch
        import cv2
        from photo_restorer.models.ori.orientation_detector import get_detector, CLASS_TO_ANGLE
    except Exception:
        return OrientationResult(angle=0, confidence=0.0, evidence=["model_import_failed"])

    try:
        weights_path = config.get("orientation_weights", None)
        detector = get_detector(weights_path, device)
    except Exception as e:
        return OrientationResult(angle=0, confidence=0.0, evidence=[f"model_load_failed: {e}"])

    try:
        frame = cv2.imread(str(image_path))
        if frame is None:
            return OrientationResult(angle=0, confidence=0.0, evidence=["image_read_error"])
    except Exception as e:
        return OrientationResult(angle=0, confidence=0.0, evidence=[f"image_read_error: {e}"])

    try:
        pred_class = detector.detect(frame)
        angle = CLASS_TO_ANGLE.get(pred_class, 0)
    except Exception as e:
        return OrientationResult(angle=0, confidence=0.0, evidence=[f"model_inference_failed: {e}"])

    try:
        x = detector._preprocess(frame).to(detector.device)
        with torch.no_grad():
            logits = detector.model(x)
            probs = torch.softmax(logits, dim=1)
            confidence = float(probs[0, pred_class].item())
    except Exception:
        confidence = 0.5

    return OrientationResult(angle=angle, confidence=round(confidence, 4), evidence=[f"xception_orientation_class_{pred_class}"])

def apply_orientation(image_path: str | Path, out_path: str | Path, result: OrientationResult) -> Path:
    if result.angle == 0:
        from shutil import copy2
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        copy2(image_path, out_path)
        return Path(out_path)
    try:
        from PIL import Image
    except Exception as exc:
        raise RuntimeError("Pillow is required for rotation. Install with: pip install -e '.[vision]'") from exc
    img = Image.open(image_path)
    rotated = img.rotate(-result.angle, expand=True)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    rotated.save(out_path)
    return Path(out_path)
