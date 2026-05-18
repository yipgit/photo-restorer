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

def detect_photo_regions(image_path: str | Path, min_area_ratio: float = 0.01) -> list[PhotoRegion]:
    cv2 = _require_cv2()
    import numpy as np

    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 40, 140)
    kernel = np.ones((5, 5), np.uint8)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = h * w * min_area_ratio
    candidates: list[PhotoRegion] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.025 * peri, True)
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
        if aspect > 8:
            continue
        candidates.append(PhotoRegion(id=f"photo_{len(candidates)+1:03d}", polygon=[(float(a), float(b)) for a, b in poly], confidence=0.8))

    # stable reading order
    candidates.sort(key=lambda r: (min(p[1] for p in r.polygon), min(p[0] for p in r.polygon)))
    for i, r in enumerate(candidates, 1):
        r.id = f"photo_{i:03d}"
    return candidates
