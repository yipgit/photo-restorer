from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Any

@dataclass
class ModelResult:
    output_path: Path
    metadata: dict[str, Any]

class ImageModelAdapter(Protocol):
    name: str
    def run(self, image_path: Path, output_path: Path, **params: Any) -> ModelResult: ...

class PassthroughAdapter:
    name = "passthrough"
    def run(self, image_path: Path, output_path: Path, **params: Any) -> ModelResult:
        from shutil import copy2
        output_path.parent.mkdir(parents=True, exist_ok=True)
        copy2(image_path, output_path)
        return ModelResult(output_path=output_path, metadata={"adapter": self.name, "params": params})
