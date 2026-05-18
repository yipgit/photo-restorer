# Architecture

## Components

- `backend/photo_restorer/core`: deterministic crop/orientation/pipeline logic
- `backend/photo_restorer/models`: pluggable restoration model adapters
- `backend/photo_restorer/api`: local FastAPI server for desktop UI
- `apps/desktop`: Tauri-ready web UI scaffold
- `backend/photo_restorer/presets`: shared YAML presets used by UI and CLI

## Model Adapter Contract

Every model adapter receives `image_path`, `output_path`, and params from YAML. It returns an output path and metadata. This keeps local CUDA models and remote API models interchangeable.

Planned adapters:

- LaMa: mold/scratch/stain inpainting with mask support
- CodeFormer/GFPGAN: face restoration
- Real-ESRGAN: super resolution/background enhancement
- DiffBIR: blind image restoration
- API: SUPIR/FaithDiff/SDXL or remote GPU endpoint

## Windows 3070 Strategy

Default GPU stack should fit 8GB VRAM where possible:

1. LaMa
2. CodeFormer or GFPGAN
3. Real-ESRGAN 2x
4. DiffBIR with tiled/low-vram settings

SUPIR/FaithDiff stay experimental/API until measured on target machine.
