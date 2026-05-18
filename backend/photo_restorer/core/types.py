from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Literal

Point = tuple[float, float]

@dataclass
class PhotoRegion:
    id: str
    polygon: list[Point]
    confidence: float = 1.0
    source: str = "opencv"

@dataclass
class OrientationResult:
    angle: int = 0
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)

@dataclass
class ProcessedPhoto:
    source_image: str
    region_id: str
    raw_crop: str | None = None
    rectified_crop: str | None = None
    oriented_crop: str | None = None
    final_image: str | None = None
    orientation: OrientationResult = field(default_factory=OrientationResult)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ProjectMetadata:
    input_paths: list[str]
    preset: str
    photos: list[ProcessedPhoto] = field(default_factory=list)
    status: Literal["created", "running", "completed", "failed"] = "created"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
