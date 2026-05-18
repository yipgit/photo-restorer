from __future__ import annotations

import argparse
import json
from pathlib import Path
from .core.config import load_config
from .core.pipeline import Pipeline

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="photo-restorer")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_cfg = sub.add_parser("inspect-config")
    p_cfg.add_argument("--preset", default="family_photo_default")
    p_cfg.add_argument("--config")

    p_detect = sub.add_parser("detect")
    p_detect.add_argument("input")
    p_detect.add_argument("--out", required=True)
    p_detect.add_argument("--preset", default="family_photo_default")
    p_detect.add_argument("--config")
    p_detect.add_argument("--recursive", action="store_true")

    p_run = sub.add_parser("run")
    p_run.add_argument("input")
    p_run.add_argument("--out", required=True)
    p_run.add_argument("--preset", default="family_photo_default")
    p_run.add_argument("--config")
    p_run.add_argument("--recursive", action="store_true")
    p_run.add_argument("--only-crop", action="store_true")
    p_run.add_argument("--save-intermediate", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "inspect-config":
        print(json.dumps(load_config(args.config or args.preset), ensure_ascii=False, indent=2))
        return 0
    pipe = Pipeline(preset=getattr(args, "preset", "family_photo_default"), config_path=getattr(args, "config", None))
    if args.cmd == "detect":
        project = pipe.detect(args.input, args.out, recursive=args.recursive)
        print(json.dumps(project.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "run":
        project = pipe.run(args.input, args.out, recursive=args.recursive, only_crop=args.only_crop, save_intermediate=args.save_intermediate)
        print(f"completed: {len(project.photos)} photos -> {Path(args.out).resolve()}")
        return 0
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
