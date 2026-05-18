from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

@dataclass
class PipelineStep:
    key: str
    label: str
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)

DEFAULT_PIPELINE = [
    PipelineStep("crop", "照片识别 / 裁切 / 透视校正", True),
    PipelineStep("orientation", "内容方向识别 / 旋转", True),
    PipelineStep("defect_inpaint", "霉点 / 污渍 / 划痕修复", False, {"model": "lama"}),
    PipelineStep("global_restore", "整体恢复增强 / 去模糊", False, {"model": "diffbir"}),
    PipelineStep("face_restore", "人脸修复", False, {"model": "codeformer", "fidelity": 0.7}),
    PipelineStep("super_resolution", "超分输出", False, {"model": "realesrgan", "scale": 2}),
]

def default_pipeline_dict() -> list[dict[str, Any]]:
    return [step.__dict__.copy() for step in DEFAULT_PIPELINE]
