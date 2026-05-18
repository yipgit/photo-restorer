from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

try:
    from fastapi import FastAPI, UploadFile, File, Form
    from fastapi.responses import JSONResponse
except Exception as exc:  # pragma: no cover
    raise RuntimeError("FastAPI dependencies missing. Install with: pip install -e '.[api]'") from exc

from photo_restorer import __version__
from photo_restorer.core.pipeline import Pipeline

app = FastAPI(title="Photo Restorer API", version=__version__)

@app.get("/health")
def health():
    return {"ok": True, "version": __version__}

@app.post("/run")
async def run_one(file: UploadFile = File(...), preset: str = Form("family_photo_default")):
    with TemporaryDirectory() as td:
        td_path = Path(td)
        src = td_path / file.filename
        src.write_bytes(await file.read())
        out = td_path / "out"
        project = Pipeline(preset=preset).run(src, out, only_crop=False, save_intermediate=True)
        return JSONResponse(project.to_dict())
