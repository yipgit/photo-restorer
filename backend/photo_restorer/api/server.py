from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

try:
    from fastapi import FastAPI, UploadFile, File, Form
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from fastapi.staticfiles import StaticFiles
except Exception as exc:  # pragma: no cover
    raise RuntimeError("FastAPI dependencies missing. Install with: pip install -e '.[api]'") from exc

from photo_restorer import __version__
from photo_restorer.core.pipeline import Pipeline

REPO_ROOT = Path(__file__).resolve().parents[3]
API_OUTPUT_ROOT = REPO_ROOT / "outputs" / "api-runs"
API_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Photo Restorer API", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/outputs", StaticFiles(directory=str(API_OUTPUT_ROOT)), name="outputs")

@app.get("/health")
def health():
    return {"ok": True, "version": __version__, "outputRoot": str(API_OUTPUT_ROOT)}

@app.post("/run")
async def run_one(
    file: UploadFile = File(...),
    preset: str = Form("family_photo_default"),
    only_crop: bool = Form(False),
):
    job_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
    job_dir = API_OUTPUT_ROOT / job_id
    input_dir = job_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(file.filename or "scan.png").name
    src = input_dir / safe_name
    src.write_bytes(await file.read())

    project = Pipeline(preset=preset).run(src, job_dir, only_crop=only_crop, save_intermediate=True)
    data = project.to_dict()
    data["jobId"] = job_id
    data["outputDir"] = str(job_dir)
    for photo in data.get("photos", []):
        final_image = photo.get("final_image")
        if final_image:
            try:
                rel = Path(final_image).resolve().relative_to(API_OUTPUT_ROOT.resolve())
                photo["final_url"] = f"/outputs/{rel.as_posix()}"
            except ValueError:
                pass
    return JSONResponse(data)
