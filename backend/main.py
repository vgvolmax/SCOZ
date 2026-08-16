from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import APP_NAME, FRONTEND_DIR, FRONTEND_INDEX, VERSION

app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": APP_NAME, "version": VERSION}


@app.get("/", response_class=FileResponse)
def index() -> FileResponse:
    return FileResponse(FRONTEND_INDEX)


app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")
