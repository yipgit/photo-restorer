from __future__ import annotations

from .base import PassthroughAdapter

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
    name_lower = name.lower()
    if name_lower == "lama":
        try:
            from .lama import LaMaAdapter
            return LaMaAdapter()
        except Exception:
            return PassthroughAdapter()
    if name_lower == "codeformer":
        try:
            from .codeformer import CodeFormerAdapter
            return CodeFormerAdapter()
        except Exception:
            return PassthroughAdapter()
    if name_lower == "denoise":
        from .denoise import DenoiseAdapter
        return DenoiseAdapter()
    if name_lower == "clean":
        from .clean import CleanAdapter
        return CleanAdapter()
    if name_lower == "enhance":
        from .enhance import EnhanceAdapter
        return EnhanceAdapter()
    try:
        return _MODEL_REGISTRY[name_lower]()
    except KeyError as exc:
        raise ValueError(f"Unknown model adapter: {name}") from exc
