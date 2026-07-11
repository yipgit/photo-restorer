from __future__ import annotations

from pathlib import Path

import numpy as np

try:
    import cv2
except Exception:
    cv2 = None

from .base import ModelResult


def _detect_mold_spots(gray, strength=0.5):
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    block_size = 7 + int(strength * 6)
    if block_size % 2 == 0:
        block_size += 1
    C = 2 + int(strength * 4)
    thresh = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block_size, C)

    kernel = np.ones((3, 3), np.uint8)
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    dilate_iter = max(1, int(1 + strength * 3))
    dilated = cv2.dilate(opened, kernel, iterations=dilate_iter)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask = np.zeros_like(gray)
    max_area = 100 + int(strength * 400)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 3 or area > max_area:
            continue
        cv2.drawContours(mask, [cnt], -1, 255, -1)
    return mask


class CleanAdapter:
    name = "clean"

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
        gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY)
        mask = _detect_mold_spots(gray, strength)
        spot_pixels = int(np.sum(mask > 0))
        if spot_pixels == 0:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(output_path), image_np)
            return ModelResult(output_path=output_path, metadata={
                "adapter": self.name, "strength": strength, "spot_pixels": 0,
                "method": "mold_spot_detection_inpaint",
            })
        dilate_kernel = np.ones((3, 3), np.uint8)
        dilated_mask = cv2.dilate(mask, dilate_kernel, iterations=max(1, int(2 + strength * 4)))
        inpaint_radius = max(5, int(5 + strength * 8))
        result = cv2.inpaint(image_np, dilated_mask, inpaint_radius, cv2.INPAINT_TELEA)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), result)

        return ModelResult(output_path=output_path, metadata={
            "adapter": self.name,
            "strength": strength,
            "spot_pixels": spot_pixels,
            "inpaint_radius": inpaint_radius,
            "method": "mold_spot_detection_inpaint",
        })
