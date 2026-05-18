from __future__ import annotations

from pathlib import Path
from .types import PhotoRegion

class MissingVisionDependency(RuntimeError):
    pass

def _require_cv2():
    try:
        import cv2  # type: ignore
        import numpy as np  # noqa: F401
        return cv2
    except Exception as exc:
        raise MissingVisionDependency("OpenCV is required. Install with: pip install -e '.[vision]'") from exc

def order_polygon(points):
    import numpy as np
    pts = np.array(points, dtype="float32")
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).reshape(-1)
    return [tuple(pts[s.argmin()]), tuple(pts[diff.argmin()]), tuple(pts[s.argmax()]), tuple(pts[diff.argmax()])]

def detect_photo_regions(
    image_path: str | Path,
    min_area_ratio: float = 0.01,
    max_area_ratio: float = 0.95,
    canny_low: int = 25,
    canny_high: int = 120,
    blur_kernel: int = 5,
    morph_iterations: int = 2,
    approx_epsilon_ratio: float = 0.02,
) -> list[PhotoRegion]:
    """Detect photo quadrilaterals in a scanned page.

    The parameters are intentionally exposed for the PySide crop workbench:
    old scans vary a lot, so the user must be able to tune thresholds and
    rerun detection before manual point adjustment.
    """
    cv2 = _require_cv2()
    import numpy as np

    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if blur_kernel > 1:
        if blur_kernel % 2 == 0:
            blur_kernel += 1
        gray = cv2.GaussianBlur(gray, (blur_kernel, blur_kernel), 0)
    edges = cv2.Canny(gray, int(canny_low), int(canny_high))
    if morph_iterations > 0:
        kernel = np.ones((5, 5), np.uint8)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=int(morph_iterations))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = h * w * min_area_ratio
    max_area = h * w * max_area_ratio
    candidates: list[PhotoRegion] = []
    seen_boxes: list[tuple[int, int, int, int]] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, approx_epsilon_ratio * peri, True)
        if len(approx) < 4:
            continue
        if len(approx) > 4:
            rect = cv2.minAreaRect(contour)
            box = cv2.boxPoints(rect)
        else:
            box = approx.reshape(4, 2)
        poly = order_polygon(box)
        x, y, bw, bh = cv2.boundingRect(box.astype("float32"))
        aspect = max(bw, bh) / max(1, min(bw, bh))
        if aspect > 8 or bw < 20 or bh < 20:
            continue
        # simple duplicate suppression for nested/near-identical contours
        duplicate = False
        for sx, sy, sw, sh in seen_boxes:
            if abs(x - sx) < 12 and abs(y - sy) < 12 and abs(bw - sw) < 24 and abs(bh - sh) < 24:
                duplicate = True
                break
        if duplicate:
            continue
        seen_boxes.append((x, y, bw, bh))
        confidence = min(0.98, max(0.2, area / max(1, bw * bh)))
        candidates.append(PhotoRegion(id=f"photo_{len(candidates)+1:03d}", polygon=[(float(a), float(b)) for a, b in poly], confidence=float(confidence)))

    # stable reading order
    candidates.sort(key=lambda r: (min(p[1] for p in r.polygon), min(p[0] for p in r.polygon)))
    for i, r in enumerate(candidates, 1):
        r.id = f"photo_{i:03d}"
    return candidates
