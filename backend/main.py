from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, StrictBool
from starlette.datastructures import UploadFile

from backend.application.ozon_products_import import import_ozon_products_xlsx, recover_interrupted_ozon_products_imports
from backend.application.ozon_search_visibility_import import (
    import_ozon_search_visibility_xlsx,
    recover_interrupted_ozon_search_visibility_imports,
)
from backend.config import APP_NAME, DATA_DIR, FRONTEND_DIR, FRONTEND_INDEX, VERSION, resolve_db_path
from backend.domain.product import ProductNotFound
from backend.domain.product_snapshot import *
from backend.domain.search_visibility import *
from backend.persistence.connection import transaction
from backend.persistence.repositories.lineage import LineageRepository
from backend.persistence.repositories.products import ProductRepository

def _json(value):
    if hasattr(value,"__dataclass_fields__"): return {key:_json(item) for key,item in asdict(value).items()}
    if isinstance(value,Enum): return value.value
    if isinstance(value,Decimal): return format(value,"f")
    if isinstance(value,(date,datetime)): return value.isoformat()
    if isinstance(value,(list,tuple)): return [_json(item) for item in value]
    if isinstance(value,dict): return {key:_json(item) for key,item in value.items()}
    return value

@asynccontextmanager
async def lifespan(app: FastAPI):
    recover_interrupted_ozon_products_imports(db_path=resolve_db_path(),data_dir=DATA_DIR)
    recover_interrupted_ozon_search_visibility_imports(db_path=resolve_db_path(),data_dir=DATA_DIR)
    yield

app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": APP_NAME, "version": VERSION}

ERRORS={UnsupportedWorkbook:(422,"UNSUPPORTED_WORKBOOK","Не удалось прочитать XLSX-файл."),WrongReportType:(422,"WRONG_REPORT_TYPE","Выберите отчёт Ozon «Товары на Ozon»."),IncompatibleReportSchema:(422,"INCOMPATIBLE_REPORT_SCHEMA","Версия или структура отчёта не поддерживается."),InvalidReportPeriod:(422,"INVALID_REPORT_PERIOD","Не удалось прочитать дату формирования или период отчёта."),InvalidMetricValue:(422,"INVALID_METRIC_VALUE","Некорректное значение показателя."),ConflictingObservationRows:(422,"CONFLICTING_OBSERVATION_ROWS","В отчёте есть противоречивые строки одного товара."),ConcurrentImportConflict:(409,"CONCURRENT_IMPORT_CONFLICT","Другой импорт уже выполняется. Дождитесь его завершения."),UploadTooLarge:(413,"UPLOAD_TOO_LARGE","Размер файла превышает 25 МиБ."),UnsupportedUploadMediaType:(415,"UNSUPPORTED_UPLOAD_MEDIA_TYPE","Выберите XLSX-файл."),ImportPersistenceError:(500,"IMPORT_PERSISTENCE_ERROR","Не удалось сохранить импорт. Данные не изменены.")}

SEARCH_VISIBILITY_ERRORS = {
    SearchVisibilityUnsupportedWorkbook: (422, "UNSUPPORTED_WORKBOOK", "Не удалось прочитать XLSX-файл."),
    SearchVisibilityWrongReportType: (422, "WRONG_REPORT_TYPE", "Выберите XLSX-выгрузку Ozon с факторами поисковой выдачи."),
    SearchVisibilityIncompatibleReportSchema: (422, "INCOMPATIBLE_REPORT_SCHEMA", "Версия или структура отчёта не поддерживается."),
    SearchVisibilityInvalidObservedAt: (422, "INVALID_OBSERVED_AT", "Не удалось прочитать дату или время наблюдения."),
    SearchVisibilityInvalidSearchContext: (422, "INVALID_SEARCH_CONTEXT", "Не удалось прочитать поисковый запрос или кластер."),
    SearchVisibilityConflictingObservationRows: (422, "CONFLICTING_OBSERVATION_ROWS", "В отчёте есть противоречивые строки одного товара."),
    SearchVisibilityNoUsableRows: (422, "NO_USABLE_ROWS", "В отчёте нет пригодных строк товаров."),
    SearchVisibilityConcurrentImportConflict: (409, "CONCURRENT_IMPORT_CONFLICT", "Другой импорт уже выполняется. Дождитесь его завершения."),
    SearchVisibilityUploadTooLarge: (413, "UPLOAD_TOO_LARGE", "Размер файла превышает 25 МиБ."),
    SearchVisibilityUnsupportedUploadMediaType: (415, "UNSUPPORTED_UPLOAD_MEDIA_TYPE", "Выберите XLSX-файл."),
    SearchVisibilityImportPersistenceError: (500, "IMPORT_PERSISTENCE_ERROR", "Не удалось сохранить импорт. Данные не изменены."),
}

@app.post("/api/imports/ozon-products")
async def post_ozon_products_import(request: Request) -> dict[str,object]:
    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        status, code, message = ERRORS[UnsupportedUploadMediaType]
        return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}, "result": None})
    form = await request.form()
    file = form.get("file")
    if not isinstance(file, UploadFile):
        raise HTTPException(status_code=422, detail="Multipart field 'file' is required")
    try:
        return _json(import_ozon_products_xlsx(upload=file.file,original_name=file.filename or "",db_path=resolve_db_path(),data_dir=DATA_DIR))
    except OzonProductsImportFailure as failure:
        status,code,message=ERRORS.get(type(failure.error),(500,"IMPORT_PERSISTENCE_ERROR","Не удалось сохранить импорт. Данные не изменены."))
        return JSONResponse(status_code=status,content={"error":{"code":code,"message":message},"result":_json(failure.result)})
    finally: await file.close()

@app.post("/api/imports/ozon-search-visibility")
async def post_ozon_search_visibility_import(request: Request) -> dict[str, object]:
    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        status, code, message = SEARCH_VISIBILITY_ERRORS[SearchVisibilityUnsupportedUploadMediaType]
        return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}, "result": None})
    form = await request.form()
    file = form.get("file")
    if not isinstance(file, UploadFile):
        raise HTTPException(status_code=422, detail="Multipart field 'file' is required")
    try:
        return _json(import_ozon_search_visibility_xlsx(
            upload=file.file, original_name=file.filename or "",
            db_path=resolve_db_path(), data_dir=DATA_DIR,
        ))
    except OzonSearchVisibilityImportFailure as failure:
        status, code, message = SEARCH_VISIBILITY_ERRORS.get(
            type(failure.error), SEARCH_VISIBILITY_ERRORS[SearchVisibilityImportPersistenceError]
        )
        return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}, "result": _json(failure.result)})
    finally:
        await file.close()

@app.get("/api/imports")
def get_imports(limit: int=Query(50,ge=1,le=100),offset: int=Query(0,ge=0)) -> dict[str,object]:
    with transaction() as conn:
        repo=LineageRepository(conn); return {"items":_json(repo.list_import_history(limit=limit,offset=offset)),"total":repo.count_import_history()}

@app.get("/api/products")
def get_products(limit: int=Query(100,ge=1,le=100),offset: int=Query(0,ge=0)) -> dict[str,object]:
    with transaction() as conn:
        repo=ProductRepository(conn); return {"items":_json(repo.list_ozon_products(limit=limit,offset=offset)),"total":repo.count_ozon_products(),"readiness":"READY" if repo.any_owned() else "SELECT_OWN_PRODUCTS"}

class OwnershipUpdate(BaseModel): is_owned: StrictBool

@app.patch("/api/products/{product_id}/ownership")
def patch_product_ownership(product_id: int,request: OwnershipUpdate) -> dict[str,object]:
    try:
        with transaction() as conn: product=ProductRepository(conn).set_owned(product_id,request.is_owned)
    except ProductNotFound: raise HTTPException(status_code=404,detail="Product not found") from None
    return {"id":product.id,"is_owned":product.is_owned,"updated_at":product.updated_at.isoformat()}


@app.get("/", response_class=FileResponse)
def index() -> FileResponse:
    return FileResponse(FRONTEND_INDEX)


app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")
