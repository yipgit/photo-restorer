from __future__ import annotations

from pathlib import Path

try:
    import cv2
except Exception:
    cv2 = None

from .base import ModelResult


class DenoiseAdapter:
    name = "denoise"

    def __init__(self):
        pass

    def run(self, image_path: Path, output_path: Path, **params) -> ModelResult:
        if cv2 is None:
            raise RuntimeError("opencv-python is required")
        strength = float(params.get("strength", 0.5))
        strength = max(0.1, min(1.0, strength))

        image_np = cv2.imread(str(image_path))
        if image_np is None:
            raise RuntimeError(f"Failed to read image: {image_path}")

        h = max(3, int(5 + strength * 10))
        denoised = cv2.fastNlMeansDenoisingColored(image_np, None, h, h, 7, 21)
        blended = cv2.addWeighted(image_np, 1 - strength, denoised, strength, 0)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), blended)

        return ModelResult(output_path=output_path, metadata={
            "adapter": self.name,
            "strength": strength,
            "method": "fast_nl_means_denoising",
        })
