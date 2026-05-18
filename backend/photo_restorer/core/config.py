from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

PRESET_PACKAGE = "photo_restorer.presets"

class ConfigError(RuntimeError):
    pass

def _load_yaml_text(text: str) -> dict[str, Any]:
    if yaml is not None:
        return yaml.safe_load(text) or {}
    # tiny fallback for JSON-compatible configs
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError("PyYAML is required for YAML presets. Install with: pip install -e '.[vision]'") from exc

def load_preset(name: str) -> dict[str, Any]:
    filename = name if name.endswith(".yaml") else f"{name}.yaml"
    try:
        text = resources.files(PRESET_PACKAGE).joinpath(filename).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(f"Preset not found: {name}") from exc
    return _load_yaml_text(text)

def load_config(path_or_preset: str | Path) -> dict[str, Any]:
    path = Path(path_or_preset)
    if path.exists():
        return _load_yaml_text(path.read_text(encoding="utf-8"))
    return load_preset(str(path_or_preset))
