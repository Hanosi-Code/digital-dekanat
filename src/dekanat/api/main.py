from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from ..core.config import load_doc_types
from ..core.ingest import IngestError
from ..core.pipeline import Pipeline
from ..core.schemas import AnalyzeResponse

app = FastAPI(title="Онлайн-деканат", version="0.1.0")
_pipeline: Pipeline | None = None


def get_pipeline() -> Pipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = Pipeline()
    return _pipeline


@app.on_event("startup")
def warmup() -> None:
    get_pipeline()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/doc-types")
def doc_types() -> list[dict]:
    return [
        {"id": d.id, "title": d.title,
         "fields": [{"id": f.id, "label": f.label, "required": f.required} for f in d.fields]}
        for d in load_doc_types().values()
    ]


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(file: UploadFile = File(...), question: str = Form(...),
                  doc_type: str | None = Form(None)) -> AnalyzeResponse:
    data = await file.read()
    try:
        return get_pipeline().run(data, file.filename or "", question, doc_type or None)
    except IngestError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
