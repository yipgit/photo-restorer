from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from photo_restorer.core.orientation import OrientationResult, detect_orientation, apply_orientation
from photo_restorer.models.registry import get_adapter

PIPELINE_ORDER = ["orientation", "denoise", "inpaint", "clean", "enhance", "face_restore", "super_res"]

@dataclass
class PhotoState:
    region_id: str
    original_path: Path
    output_dir: Path
    scan_stem: str = ""
    steps: dict[str, dict] = field(default_factory=lambda: {
        "orientation":   {"enabled": True,  "params": {"auto_rotate": True, "min_confidence": 0.7}, "path": None},
        "denoise":       {"enabled": False, "params": {"strength": 0.5}, "path": None},
        "inpaint":       {"enabled": False, "params": {"strength": "medium"}, "path": None},
        "clean":         {"enabled": False, "params": {"strength": 0.5}, "path": None},
        "enhance":       {"enabled": False, "params": {"strength": 0.5}, "path": None},
        "face_restore":  {"enabled": False, "params": {"fidelity": 0.7}, "path": None},
        "super_res":     {"enabled": False, "params": {"scale": 2}, "path": None},
    })

    def enable(self, step: str, value: bool):
        if step in self.steps:
            self.steps[step]["enabled"] = value

    def set_param(self, step: str, key: str, value):
        if step in self.steps:
            self.steps[step]["params"][key] = value

    def final_path(self) -> Path | None:
        for step in reversed(PIPELINE_ORDER):
            if self.steps[step]["enabled"] and self.steps[step]["path"]:
                return self.steps[step]["path"]
        return self.original_path


class PipelineRunner(QObject):
    finished = Signal(str, object)
    error = Signal(str, str)

    def __init__(self):
        super().__init__()
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._run)
        self._pending: PhotoState | None = None

    def schedule(self, state: PhotoState):
        self._pending = state
        self._timer.start(300)

    def _run(self):
        if self._pending is None:
            return
        state = self._pending
        self._pending = None
        try:
            current = state.original_path
            for step_name in PIPELINE_ORDER:
                step_info = state.steps[step_name]
                if not step_info["enabled"]:
                    continue
                step_path = state.output_dir / f"{state.original_path.stem}_{step_name}.png"
                if step_name == "orientation":
                    if step_info.get("path"):
                        current = step_info["path"]
                        continue
                    params = step_info["params"]
                    manual = params.get("manual_angle")
                    if manual is not None:
                        orient = OrientationResult(angle=manual, confidence=1.0, evidence=["manual"])
                    else:
                        orient = detect_orientation(current, params)
                    apply_orientation(current, step_path, orient)
                elif step_name in ("denoise", "inpaint", "clean", "enhance", "face_restore", "super_res"):
                    model_name = {"denoise": "denoise", "inpaint": "lama", "clean": "clean", "enhance": "enhance", "face_restore": "codeformer", "super_res": "realesrgan"}[step_name]
                    adapter = get_adapter(model_name)
                    adapter.run(current, step_path, **step_info["params"])
                current = step_path
                step_info["path"] = step_path
            final = state.final_path()
            self.finished.emit(state.region_id, final)
        except Exception as exc:
            self.error.emit(state.region_id, str(exc))
