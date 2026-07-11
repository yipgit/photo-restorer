from __future__ import annotations

from pathlib import Path
from .config import load_config
from .crop import crop_and_rectify
from .detect import detect_photo_regions
from .io import collect_inputs, copy_originals, ensure_output_tree, write_json
from .orientation import apply_orientation, detect_orientation
from .types import ProcessedPhoto, ProjectMetadata
from photo_restorer.models.registry import get_adapter

class Pipeline:
    def __init__(self, preset: str = "family_photo_default", config_path: str | None = None):
        self.config = load_config(config_path or preset)
        self.preset = self.config.get("name", preset)

    def detect(self, input_path: str | Path, out_project: str | Path, recursive: bool = False) -> ProjectMetadata:
        inputs = collect_inputs(input_path, recursive=recursive)
        project = ProjectMetadata(input_paths=[str(p) for p in inputs], preset=self.preset)
        for img in inputs:
            regions = detect_photo_regions(img, self.config.get("crop", {}).get("min_area_ratio", 0.01))
            for region in regions:
                project.photos.append(ProcessedPhoto(source_image=str(img), region_id=region.id, metadata={"polygon": region.polygon, "region_confidence": region.confidence}))
        write_json(out_project, project.to_dict())
        return project

    def run(self, input_path: str | Path, out_dir: str | Path, recursive: bool = False, only_crop: bool = False, save_intermediate: bool = False) -> ProjectMetadata:
        inputs = collect_inputs(input_path, recursive=recursive)
        dirs = ensure_output_tree(out_dir)
        if save_intermediate:
            copy_originals(inputs, dirs["original"])
        project = ProjectMetadata(input_paths=[str(p) for p in inputs], preset=self.preset, status="running")
        for img in inputs:
            regions = detect_photo_regions(img, self.config.get("crop", {}).get("min_area_ratio", 0.01))
            for region in regions:
                stem = f"{Path(img).stem}_{region.id}"
                rectified = crop_and_rectify(img, region, dirs["rectified"] / f"{stem}.png", self.config.get("crop", {}).get("keep_border_px", 0))
                orient = detect_orientation(rectified, self.config.get("orientation", {}))
                oriented = apply_orientation(rectified, dirs["oriented"] / f"{stem}.png", orient)
                final = oriented
                metadata = {"polygon": region.polygon, "region_confidence": region.confidence}
                if not only_crop:
                    final = self._restore(oriented, dirs["final"] / f"{stem}.png", metadata)
                else:
                    from shutil import copy2
                    final = dirs["final"] / f"{stem}.png"
                    copy2(oriented, final)
                project.photos.append(ProcessedPhoto(source_image=str(img), region_id=region.id, rectified_crop=str(rectified), oriented_crop=str(oriented), final_image=str(final), orientation=orient, metadata=metadata))
        project.status = "completed"
        write_json(dirs["metadata"] / "project.json", project.to_dict())
        return project

    def _restore(self, image_path: Path, final_path: Path, metadata: dict) -> Path:
        repair = self.config.get("repair", {})
        current = image_path
        for step_name in ["defect_inpaint", "global_restore", "face_restore", "super_resolution"]:
            step = repair.get(step_name, {})
            if not step.get("enabled", False):
                continue
            adapter = get_adapter(step.get("model", "passthrough"))
            step_out = final_path.parent / f".{final_path.stem}.{step_name}.png"
            result = adapter.run(current, step_out, **step)
            metadata[step_name] = result.metadata
            current = result.output_path
        from shutil import copy2
        final_path.parent.mkdir(parents=True, exist_ok=True)
        copy2(current, final_path)
        return final_path
