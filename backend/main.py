from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import APP_NAME, FRONTEND_DIST, VERSION

app = FastAPI(title=APP_NAME, version=VERSION)

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": APP_NAME, "version": VERSION}

@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIST / "index.html")

app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")
