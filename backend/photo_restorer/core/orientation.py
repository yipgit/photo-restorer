from __future__ import annotations

from pathlib import Path
from .types import OrientationResult

# Conservative placeholder: later plug face/OCR/CLIP voters here.
def detect_orientation(image_path: str | Path) -> OrientationResult:
    return OrientationResult(angle=0, confidence=0.0, evidence=["conservative_default"])

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
