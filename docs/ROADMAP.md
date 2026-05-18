# Roadmap

## MVP 1 — Scan crop organizer

Status: scaffold implemented.

- [x] Python package skeleton
- [x] CLI commands: `inspect-config`, `detect`, `run`
- [x] OpenCV contour-based multi-photo detection
- [x] Perspective crop / rectify
- [x] Output tree and metadata
- [x] FastAPI scaffold
- [x] Desktop UI scaffold
- [ ] Interactive crop-box editing in UI
- [ ] Detection overlays
- [ ] Project save/load in UI

## MVP 2 — Orientation and basic enhancement

- [ ] A4 page detection for phone photos
- [ ] Shadow/lighting correction for phone photos
- [ ] Deskew small-angle rotation
- [ ] Face/OCR/scene voting for 0/90/180/270 orientation
- [ ] White balance / CLAHE / denoise / sharpen steps
- [ ] Before/after slider

## MVP 3 — Local GPU restoration on Windows 3070

- [ ] LaMa adapter with mask input
- [ ] Manual mask brush in UI
- [ ] CodeFormer adapter
- [ ] GFPGAN adapter
- [ ] Real-ESRGAN adapter
- [ ] DiffBIR adapter with low-VRAM/tiled settings
- [ ] Batch queue, pause/resume, retry

## MVP 4 — Advanced/API restoration

- [ ] Remote API adapter
- [ ] SUPIR/FaithDiff backend option
- [ ] SDXL inpainting backend option
- [ ] Multi-preset side-by-side comparison
- [ ] Model registry/download manager

## Immediate next implementation step

Build UI-to-backend project flow:

1. Start FastAPI server locally.
2. UI selects files/folder.
3. Backend creates project metadata.
4. UI displays detected crop boxes over the scan.
5. User adjusts boxes and runs crop-only export.

This locks down the hardest product loop before adding heavy models.
