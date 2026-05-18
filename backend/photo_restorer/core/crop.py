from __future__ import annotations

from pathlib import Path
from .detect import _require_cv2, order_polygon
from .types import PhotoRegion

def crop_and_rectify(image_path: str | Path, region: PhotoRegion, out_path: str | Path, keep_border_px: int = 0) -> Path:
    cv2 = _require_cv2()
    import numpy as np

    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")
    pts = np.array(order_polygon(region.polygon), dtype="float32")
    (tl, tr, br, bl) = pts
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_w = int(max(width_a, width_b)) + keep_border_px * 2
    max_h = int(max(height_a, height_b)) + keep_border_px * 2
    dst = np.array([
        [keep_border_px, keep_border_px],
        [max_w - keep_border_px - 1, keep_border_px],
        [max_w - keep_border_px - 1, max_h - keep_border_px - 1],
        [keep_border_px, max_h - keep_border_px - 1],
    ], dtype="float32")
    matrix = cv2.getPerspectiveTransform(pts, dst)
    warped = cv2.warpPerspective(img, matrix, (max_w, max_h))
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), warped)
    return out
