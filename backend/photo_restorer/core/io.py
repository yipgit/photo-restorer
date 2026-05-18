from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Iterable

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}

def collect_inputs(path: str | Path, recursive: bool = False) -> list[Path]:
    p = Path(path)
    if p.is_file():
        return [p]
    globber = p.rglob if recursive else p.glob
    return sorted(x for x in globber("*") if x.suffix.lower() in IMAGE_EXTS)

def ensure_output_tree(root: str | Path) -> dict[str, Path]:
    root = Path(root)
    dirs = {
        "root": root,
        "original": root / "00_original",
        "overlay": root / "01_detected_overlay",
        "raw_crop": root / "02_raw_crop",
        "rectified": root / "03_rectified",
        "oriented": root / "04_oriented",
        "inpainted": root / "05_inpainted",
        "restored": root / "06_restored",
        "final": root / "07_final",
        "metadata": root / "metadata",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs

def copy_originals(inputs: Iterable[Path], dest: Path) -> None:
    for src in inputs:
        target = dest / src.name
        if src.resolve() != target.resolve():
            shutil.copy2(src, target)

def write_json(path: str | Path, data: object) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
