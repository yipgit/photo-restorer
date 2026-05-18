from __future__ import annotations

from .base import PassthroughAdapter

# Real adapters will be added incrementally. Names are stable config/API contracts.
_MODEL_REGISTRY = {
    "none": PassthroughAdapter,
    "passthrough": PassthroughAdapter,
    "lama": PassthroughAdapter,
    "codeformer": PassthroughAdapter,
    "gfpgan": PassthroughAdapter,
    "realesrgan": PassthroughAdapter,
    "diffbir": PassthroughAdapter,
    "api": PassthroughAdapter,
}

def get_adapter(name: str):
    try:
        return _MODEL_REGISTRY[name.lower()]()
    except KeyError as exc:
        raise ValueError(f"Unknown model adapter: {name}") from exc
