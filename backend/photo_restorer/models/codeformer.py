from __future__ import annotations

from pathlib import Path

import numpy as np

try:
    import cv2
except Exception:
    cv2 = None

from .base import ModelResult


def _detect_faces(image_np):
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(cascade_path)
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
    faces = cascade.detectMultiScale(gray, 1.1, 3, minSize=(40, 40))
    return faces


def _enhance_face(face_np, fidelity=0.7):
    enhanced = cv2.detailEnhance(face_np, sigma_s=10, sigma_r=0.15)
    smoothed = cv2.bilateralFilter(enhanced, 9, 75, 75)
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
    sharpened = cv2.filter2D(smoothed, -1, kernel)
    blended = (face_np * (1 - fidelity) + sharpened * fidelity).astype(np.uint8)
    return blended


class CodeFormerAdapter:
    name = "codeformer"

    def __init__(self):
        pass

    def run(self, image_path: Path, output_path: Path, **params) -> ModelResult:
        if cv2 is None:
            raise RuntimeError("opencv-python is required")
        fidelity = float(params.get("fidelity", 0.7))
        fidelity = max(0.0, min(1.0, fidelity))

        image_np = cv2.imread(str(image_path))
        if image_np is None:
            raise RuntimeError(f"Failed to read image: {image_path}")
        image_np = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
        result = image_np.copy()

        faces = _detect_faces(image_np)
        face_count = len(faces)
        if face_count == 0:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(output_path), cv2.cvtColor(result, cv2.COLOR_RGB2BGR))
            return ModelResult(output_path=output_path, metadata={
                "adapter": self.name,
                "fidelity": fidelity,
                "device": "cpu",
                "faces_detected": 0,
                "faces_restored": 0,
                "method": "opencv_detail_enhance",
            })

        for x, y, w, h in faces:
            margin = int(min(w, h) * 0.2)
            x1 = max(0, x - margin)
            y1 = max(0, y - margin)
            x2 = min(image_np.shape[1], x + w + margin)
            y2 = min(image_np.shape[0], y + h + margin)
            face_crop = result[y1:y2, x1:x2].copy()
            enhanced = _enhance_face(face_crop, fidelity)
            result[y1:y2, x1:x2] = cv2.resize(enhanced, (x2 - x1, y2 - y1))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), cv2.cvtColor(result, cv2.COLOR_RGB2BGR))

        return ModelResult(output_path=output_path, metadata={
            "adapter": self.name,
            "fidelity": fidelity,
            "device": "cpu",
            "faces_detected": face_count,
            "faces_restored": face_count,
            "method": "opencv_detail_enhance",
        })
