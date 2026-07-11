from __future__ import annotations

from pathlib import Path

import numpy as np

try:
    import cv2
except Exception:
    cv2 = None

from .base import ModelResult


def _clahe_enhance(image_np, clip_limit=2.0):
    lab = cv2.cvtColor(image_np, cv2.COLOR_BGR2LAB)
    L, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    L = clahe.apply(L)
    enhanced = cv2.merge([L, a, b])
    return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)


def _white_balance(image_np, strength=0.5):
    result = image_np.copy().astype(np.float32)
    for c in range(3):
        channel = result[:, :, c]
        mean_val = channel.mean()
        if mean_val < 1:
            continue
        target = 128.0
        gain = (target / mean_val - 1) * strength + 1
        result[:, :, c] = np.clip(channel * gain, 0, 255)
    return result.astype(np.uint8)


def _vignette_correct(image_np, strength=0.5):
    h, w = image_np.shape[:2]
    cx, cy = w / 2, h / 2
    max_radius = np.sqrt(cx ** 2 + cy ** 2)
    y, x = np.ogrid[:h, :w]
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    falloff = np.clip(1.0 - (dist / max_radius) * strength, 0.7, 1.0)
    result = image_np.copy().astype(np.float32)
    for c in range(3):
        result[:, :, c] = np.clip(result[:, :, c] / falloff, 0, 255)
    return result.astype(np.uint8)


def _bw_enhance(image_np, strength=0.5):
    gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY)
    if np.std(gray) < 30:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        blended = cv2.addWeighted(gray, 1 - strength, enhanced, strength, 0)
        return cv2.cvtColor(blended, cv2.COLOR_GRAY2BGR)
    return image_np


class EnhanceAdapter:
    name = "enhance"

    def __init__(self):
        pass

    def run(self, image_path: Path, output_path: Path, **params) -> ModelResult:
        if cv2 is None:
            raise RuntimeError("opencv-python is required")
        strength = float(params.get("strength", 0.5))
        strength = max(0.0, min(1.0, strength))

        image_np = cv2.imread(str(image_path))
        if image_np is None:
            raise RuntimeError(f"Failed to read image: {image_path}")

        result = image_np.copy()
        result = _bw_enhance(result, strength)
        clip_limit = 0.5 + strength * 3.0
        result = _clahe_enhance(result, clip_limit)
        result = _white_balance(result, strength)
        result = _vignette_correct(result, strength * 0.5)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), result)

        return ModelResult(output_path=output_path, metadata={
            "adapter": self.name,
            "strength": strength,
            "method": "clahe_white_balance_vignette_bw",
        })
