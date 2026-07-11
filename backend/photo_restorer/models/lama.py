from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

try:
    import cv2
except Exception:
    cv2 = None

from .base import ModelResult

_MODEL_URL = "https://github.com/Sanster/models/releases/download/add_big_lama/big-lama.pt"
_MODEL_DIR = Path.home() / ".photo_restorer" / "models"
_MODEL_PATH = _MODEL_DIR / "big-lama.pt"

LAMA_STRENGTH = {
    "low": 0.5,
    "medium": 1.0,
    "high": 2.0,
}

def _download_model():
    if _MODEL_PATH.exists():
        return
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    import urllib.request
    urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)

def _get_device():
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")

def _norm(np_array):
    if np_array.max() <= 1.0:
        return (np_array * 255).astype(np.uint8)
    return np_array.astype(np.uint8)

def _pad16(x):
    h, w = x.shape[2], x.shape[3]
    new_h = (h + 15) // 16 * 16
    new_w = (w + 15) // 16 * 16
    if h == new_h and w == new_w:
        return x, (h, w)
    return F.interpolate(x, size=(new_h, new_w), mode="bilinear", align_corners=False), (h, w)

def _generate_mask(image_np, strength=1.0):
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
    edges = cv2.Canny(blur, 20, 80)
    combined = cv2.bitwise_or(thresh, edges)
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(combined, kernel, iterations=max(1, int(strength)))
    mask = (dilated > 0).astype(np.float32)
    if mask.sum() < 500:
        mask = np.ones_like(mask) * 0.1
    return mask

class LaMaAdapter:
    name = "lama"

    def __init__(self):
        self._model = None
        self._device = _get_device()

    def _load_model(self):
        if self._model is not None:
            return
        _download_model()
        self._model = torch.jit.load(str(_MODEL_PATH), map_location=self._device)
        self._model.eval()
        for p in self._model.parameters():
            p.requires_grad = False

    def run(self, image_path: Path, output_path: Path, **params) -> ModelResult:
        self._load_model()
        if cv2 is None:
            raise RuntimeError("opencv-python is required")
        strength_str = params.get("strength", "medium")
        strength_val = LAMA_STRENGTH.get(strength_str, 1.0)

        image_np = cv2.imread(str(image_path))
        if image_np is None:
            raise RuntimeError(f"Failed to read image: {image_path}")
        image_np = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
        h, w = image_np.shape[:2]

        mask = _generate_mask(image_np, strength_val)
        mask = (mask * 255).astype(np.uint8)
        mask[mask > 0] = 255

        image_t = torch.from_numpy(image_np).float().permute(2, 0, 1).unsqueeze(0) / 255.0
        mask_t = torch.from_numpy(mask).float().unsqueeze(0).unsqueeze(0) / 255.0

        image_t = image_t.to(self._device)
        mask_t = mask_t.to(self._device)

        image_t, orig = _pad16(image_t)
        mask_t, _ = _pad16(mask_t)

        with torch.no_grad():
            result = self._model(image_t, mask_t)
        result = result[:, :, :orig[0], :orig[1]]
        result = torch.clamp(result, 0, 1)

        result_np = (result[0].permute(1, 2, 0).cpu().numpy() * 255).astype(np.uint8)
        result_np = cv2.cvtColor(result_np, cv2.COLOR_RGB2BGR)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), result_np)

        return ModelResult(output_path=output_path, metadata={
            "adapter": self.name,
            "strength": strength_str,
            "device": str(self._device),
            "mask_pixels": int(mask.sum()),
        })
