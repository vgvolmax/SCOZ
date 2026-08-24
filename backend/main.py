from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated

import httpx
from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, SecretStr, StrictBool, StrictInt, StrictStr, field_validator
from starlette.datastructures import UploadFile

from backend.application.ozon_products_import import import_ozon_products_xlsx, recover_interrupted_ozon_products_imports
from backend.application.ozon_search_visibility_import import (
    import_ozon_search_visibility_xlsx,
    recover_interrupted_ozon_search_visibility_imports,
)
from backend.application.ozon_seller_queries_import import import_ozon_seller_queries_xlsx, recover_interrupted_ozon_seller_queries_imports
from backend.application.ozon_query_metrics_import import import_ozon_query_metrics_xlsx, recover_interrupted_ozon_query_metrics_imports
from backend.config import APP_NAME, DATA_DIR, FRONTEND_DIR, FRONTEND_INDEX, VERSION, resolve_db_path
from backend.domain.product import ProductNotFound
from backend.domain.benchmark_selection import *
from backend.application.benchmark_selection import BenchmarkSelectionService
from backend.sources.mpstats import MPStatsClient
from backend.domain.product_snapshot import *
from backend.domain.search_visibility import (
    OzonSearchVisibilityImportFailure,
    SearchVisibilityConcurrentImportConflict,
    SearchVisibilityConflictingObservationRows,
    SearchVisibilityImportPersistenceError,
    SearchVisibilityIncompatibleReportSchema,
    SearchVisibilityInvalidObservedAt,
    SearchVisibilityInvalidSearchContext,
    SearchVisibilityNoUsableRows,
    SearchVisibilityUnsupportedUploadMediaType,
    SearchVisibilityUnsupportedWorkbook,
    SearchVisibilityUploadTooLarge,
    SearchVisibilityWrongReportType,
)
from backend.domain.product_query import *
from backend.domain.query_metric import *
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
    recover_interrupted_ozon_seller_queries_imports(db_path=resolve_db_path(),data_dir=DATA_DIR)
    recover_interrupted_ozon_query_metrics_imports(db_path=resolve_db_path(),data_dir=DATA_DIR)
    yield

app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": APP_NAME, "version": VERSION}

ERRORS={UnsupportedWorkbook:(422,"UNSUPPORTED_WORKBOOK","Не удалось прочитать XLSX-файл."),WrongReportType:(422,"WRONG_REPORT_TYPE","Выберите отчёт Ozon «Товары на Ozon»."),IncompatibleReportSchema:(422,"INCOMPATIBLE_REPORT_SCHEMA","Версия или структура отчёта не поддерживается."),InvalidReportPeriod:(422,"INVALID_REPORT_PERIOD","Не удалось прочитать дату формирования или период отчёта."),InvalidMetricValue:(422,"INVALID_METRIC_VALUE","Некорректное значение показателя."),ConflictingObservationRows:(422,"CONFLICTING_OBSERVATION_ROWS","В отчёте есть противоречивые строки одного товара."),ConcurrentImportConflict:(409,"CONCURRENT_IMPORT_CONFLICT","Другой импорт уже выполняется. Дождитесь его завершения."),UploadTooLarge:(413,"UPLOAD_TOO_LARGE","Размер файла превышает 25 МиБ."),UnsupportedUploadMediaType:(415,"UNSUPPORTED_UPLOAD_MEDIA_TYPE","Выберите XLSX-файл."),ImportPersistenceError:(500,"IMPORT_PERSISTENCE_ERROR","Не удалось сохранить импорт. Данные не изменены.")}
SEARCH_VISIBILITY_ERRORS={
    SearchVisibilityUnsupportedWorkbook:(422,"UNSUPPORTED_WORKBOOK","Не удалось прочитать XLSX-файл."),
    SearchVisibilityWrongReportType:(422,"WRONG_REPORT_TYPE","Выберите XLSX-выгрузку Ozon с факторами поисковой выдачи."),
    SearchVisibilityIncompatibleReportSchema:(422,"INCOMPATIBLE_REPORT_SCHEMA","Версия или структура отчёта не поддерживается."),
    SearchVisibilityInvalidObservedAt:(422,"INVALID_OBSERVED_AT","Не удалось прочитать дату или время наблюдения."),
    SearchVisibilityInvalidSearchContext:(422,"INVALID_SEARCH_CONTEXT","Не удалось прочитать поисковый запрос или кластер."),
    SearchVisibilityConflictingObservationRows:(422,"CONFLICTING_OBSERVATION_ROWS","В отчёте есть противоречивые строки одного товара."),
    SearchVisibilityNoUsableRows:(422,"NO_USABLE_ROWS","В отчёте нет пригодных строк товаров."),
    SearchVisibilityConcurrentImportConflict:(409,"CONCURRENT_IMPORT_CONFLICT","Другой импорт уже выполняется. Дождитесь его завершения."),
    SearchVisibilityUploadTooLarge:(413,"UPLOAD_TOO_LARGE","Размер файла превышает 25 МиБ."),
    SearchVisibilityUnsupportedUploadMediaType:(415,"UNSUPPORTED_UPLOAD_MEDIA_TYPE","Выберите XLSX-файл."),
    SearchVisibilityImportPersistenceError:(500,"IMPORT_PERSISTENCE_ERROR","Не удалось сохранить импорт. Данные не изменены."),
}
SELLER_QUERIES_ERRORS={SellerQueriesUnsupportedWorkbook:(422,"UNSUPPORTED_WORKBOOK","Не удалось прочитать XLSX-файл."),SellerQueriesWrongReportType:(422,"WRONG_REPORT_TYPE","Выберите отчёт Ozon «Запросы моего товара»."),SellerQueriesIncompatibleReportSchema:(422,"INCOMPATIBLE_REPORT_SCHEMA","Версия или структура отчёта не поддерживается."),SellerQueriesInvalidGeneratedAt:(422,"INVALID_GENERATED_AT","Не удалось прочитать дату формирования отчёта."),SellerQueriesInvalidReportPeriod:(422,"INVALID_REPORT_PERIOD","Не удалось прочитать период отчёта."),SellerQueriesInvalidProductContext:(422,"INVALID_PRODUCT_CONTEXT","Не удалось прочитать данные товара."),SellerQueriesConflictingObservationRows:(422,"CONFLICTING_OBSERVATION_ROWS","В отчёте есть противоречивые строки одного запроса."),SellerQueriesNoUsableRows:(422,"NO_USABLE_ROWS","В отчёте нет пригодных строк запросов."),SellerQueriesConcurrentImportConflict:(409,"CONCURRENT_IMPORT_CONFLICT","Другой импорт уже выполняется. Дождитесь его завершения."),SellerQueriesUploadTooLarge:(413,"UPLOAD_TOO_LARGE","Размер файла превышает 25 МиБ."),SellerQueriesUnsupportedUploadMediaType:(415,"UNSUPPORTED_UPLOAD_MEDIA_TYPE","Выберите XLSX-файл."),SellerQueriesImportPersistenceError:(500,"IMPORT_PERSISTENCE_ERROR","Не удалось сохранить импорт. Данные не изменены.")}
QUERY_METRICS_ERRORS={QueryMetricsUnsupportedWorkbook:(422,"UNSUPPORTED_WORKBOOK","Не удалось прочитать XLSX-файл."),QueryMetricsWrongReportType:(422,"WRONG_REPORT_TYPE","Выберите отчёт Ozon с метриками поисковых запросов."),QueryMetricsIncompatibleReportSchema:(422,"INCOMPATIBLE_REPORT_SCHEMA","Версия или структура отчёта не поддерживается."),QueryMetricsInvalidReportPeriod:(422,"INVALID_REPORT_PERIOD","Не удалось прочитать период отчёта."),QueryMetricsConflictingObservationRows:(422,"CONFLICTING_OBSERVATION_ROWS","В отчёте есть противоречивые строки одного запроса."),QueryMetricsNoUsableRows:(422,"NO_USABLE_ROWS","В отчёте нет пригодных строк запросов."),QueryMetricsConcurrentImportConflict:(409,"CONCURRENT_IMPORT_CONFLICT","Другой импорт уже выполняется. Дождитесь его завершения."),QueryMetricsUploadTooLarge:(413,"UPLOAD_TOO_LARGE","Размер файла превышает 25 МиБ."),QueryMetricsUnsupportedUploadMediaType:(415,"UNSUPPORTED_UPLOAD_MEDIA_TYPE","Выберите XLSX-файл."),QueryMetricsImportPersistenceError:(500,"IMPORT_PERSISTENCE_ERROR","Не удалось сохранить импорт. Данные не изменены.")}

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
async def post_ozon_search_visibility_import(request: Request) -> dict[str,object]:
    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        status,code,message=SEARCH_VISIBILITY_ERRORS[SearchVisibilityUnsupportedUploadMediaType]
        return JSONResponse(status_code=status,content={"error":{"code":code,"message":message},"result":None})
    form=await request.form()
    file=form.get("file")
    if not isinstance(file,UploadFile):
        raise HTTPException(status_code=422,detail="Multipart field 'file' is required")
    try:
        return _json(import_ozon_search_visibility_xlsx(upload=file.file,original_name=file.filename or "",db_path=resolve_db_path(),data_dir=DATA_DIR))
    except OzonSearchVisibilityImportFailure as failure:
        status,code,message=SEARCH_VISIBILITY_ERRORS.get(type(failure.error),(500,"IMPORT_PERSISTENCE_ERROR","Не удалось сохранить импорт. Данные не изменены."))
        return JSONResponse(status_code=status,content={"error":{"code":code,"message":message},"result":_json(failure.result)})
    finally:
        await file.close()

async def _post_query_import(request: Request, *, service, errors, media_error):
    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        status,code,message=errors[media_error]
        return JSONResponse(status_code=status,content={"error":{"code":code,"message":message},"result":None})
    form=await request.form(); file=form.get("file")
    if not isinstance(file,UploadFile): raise HTTPException(status_code=422,detail="Multipart field 'file' is required")
    try:
        return _json(service(upload=file.file,original_name=file.filename or "",db_path=resolve_db_path(),data_dir=DATA_DIR))
    except (OzonSellerQueriesImportFailure,OzonQueryMetricsImportFailure) as failure:
        status,code,message=errors.get(type(failure.error),(500,"IMPORT_PERSISTENCE_ERROR","Не удалось сохранить импорт. Данные не изменены."))
        return JSONResponse(status_code=status,content={"error":{"code":code,"message":message},"result":_json(failure.result)})
    finally: await file.close()

@app.post("/api/imports/ozon-seller-queries")
async def post_ozon_seller_queries_import(request: Request):
    return await _post_query_import(request,service=import_ozon_seller_queries_xlsx,errors=SELLER_QUERIES_ERRORS,media_error=SellerQueriesUnsupportedUploadMediaType)

@app.post("/api/imports/ozon-query-metrics")
async def post_ozon_query_metrics_import(request: Request):
    return await _post_query_import(request,service=import_ozon_query_metrics_xlsx,errors=QUERY_METRICS_ERRORS,media_error=QueryMetricsUnsupportedUploadMediaType)

@app.get("/api/imports")
def get_imports(limit: int=Query(50,ge=1,le=100),offset: int=Query(0,ge=0)) -> dict[str,object]:
    with transaction() as conn:
        repo=LineageRepository(conn); return {"items":_json(repo.list_import_history(limit=limit,offset=offset)),"total":repo.count_import_history(),"source_availability":repo.get_pr5_source_availability()}

@app.get("/api/products")
def get_products(limit: int=Query(100,ge=1,le=100),offset: int=Query(0,ge=0)) -> dict[str,object]:
    with transaction() as conn:
        repo=ProductRepository(conn); return {"items":_json(repo.list_ozon_products(limit=limit,offset=offset)),"total":repo.count_ozon_products(),"readiness":"READY" if repo.any_owned() else "SELECT_OWN_PRODUCTS"}

class OwnershipUpdate(BaseModel): is_owned: StrictBool

PositiveStrictInt = Annotated[StrictInt, Field(gt=0)]

def _is_canonical_ozon_product_id(value: str) -> bool:
    return value.isascii() and value.isdigit() and int(value) > 0 and str(int(value)) == value

class RelevantQueriesRequest(BaseModel):
    search_query_ids: list[PositiveStrictInt] = Field(max_length=10_000)

class ManualCandidateRequest(BaseModel):
    ozon_product_id: StrictStr

class BenchmarkRevisionRequest(BaseModel):
    member_product_ids: list[PositiveStrictInt] = Field(max_length=1_000)

class MPStatsTestRequest(BaseModel):
    token: SecretStr
    ozon_product_id: StrictStr
    @field_validator("token")
    @classmethod
    def validate_token(cls, value):
        if not 1 <= len(value.get_secret_value()) <= 4096: raise ValueError("token length must be between 1 and 4096 characters")
        return value
    @field_validator("ozon_product_id")
    @classmethod
    def validate_ozon_product_id(cls, value):
        if not _is_canonical_ozon_product_id(value): raise ValueError("invalid canonical Ozon product ID")
        return value

class MPStatsPreviewsRequest(BaseModel):
    token: SecretStr
    ozon_product_ids: list[StrictStr] = Field(min_length=1, max_length=500)
    @field_validator("token")
    @classmethod
    def validate_token(cls, value):
        if not 1 <= len(value.get_secret_value()) <= 4096: raise ValueError("token length must be between 1 and 4096 characters")
        return value
    @field_validator("ozon_product_ids")
    @classmethod
    def validate_ozon_product_ids(cls, values):
        if any(not _is_canonical_ozon_product_id(value) for value in values): raise ValueError("invalid canonical Ozon product ID")
        if len(set(values)) != len(values): raise ValueError("duplicate Ozon product ID")
        return values

PR6_ERRORS = {
    ProductNotFound:(404,"PRODUCT_NOT_FOUND","Товар не найден."),
    ProductNotOwnedError:(409,"PRODUCT_NOT_OWNED","Выберите свой товар из каталога."),
    NoOwnQueryDataError:(409,"NO_OWN_QUERY_DATA","Нет данных по поисковым запросам этого товара. Импортируйте отчёт «Запросы моего товара»."),
    RelevantQuerySelectionInvalidError:(422,"RELEVANT_QUERY_SELECTION_INVALID","Выбран некорректный набор поисковых запросов. Обновите список и повторите."),
    RelevantQuerySelectionEmptyError:(409,"RELEVANT_QUERY_SELECTION_EMPTY","Сначала выберите и сохраните хотя бы один релевантный запрос."),
    ManualOzonSkuInvalidError:(422,"MANUAL_OZON_SKU_INVALID","Введите корректный числовой SKU Ozon без ведущих нулей."),
    OwnProductCannotBeCompetitorError:(409,"OWN_PRODUCT_CANNOT_BE_COMPETITOR","Товар не может быть конкурентом самому себе."),
    BenchmarkEmptyError:(422,"BENCHMARK_EMPTY","Выберите хотя бы одного конкурента."),
    BenchmarkMemberInvalidError:(422,"BENCHMARK_MEMBER_INVALID","Состав конкурентов содержит недоступный или некорректный товар. Обновите список и повторите."),
    BenchmarkConcurrentWriteError:(409,"BENCHMARK_CONCURRENT_WRITE","Состав конкурентов изменился параллельно. Обновите данные и повторите."),
}
PR6_ERROR_TYPES=tuple(PR6_ERRORS)

def _pr6_error_response(error):
    status,code,message=PR6_ERRORS[type(error)]
    return JSONResponse(status_code=status,content={"error":{"code":code,"message":message}})

MPSTATS_ERRORS={
    MPStatsPendingError:(409,"MPSTATS_PENDING","MPStats ещё готовит ответ. Повторите запрос позже."),
    MPStatsAuthError:(401,"MPSTATS_AUTH","MPStats отклонил токен. Проверьте токен и повторите."),
    MPStatsRateLimitError:(429,"MPSTATS_RATE_LIMIT","Лимит MPStats исчерпан. Повторите позже."),
    MPStatsTimeoutError:(504,"MPSTATS_TIMEOUT","MPStats не ответил вовремя. Кандидаты сохранены; повторите загрузку фото."),
    MPStatsNetworkError:(502,"MPSTATS_NETWORK","Не удалось связаться с MPStats. Проверьте сеть и повторите."),
    MPStatsMalformedResponseError:(502,"MPSTATS_MALFORMED_RESPONSE","MPStats вернул неподдерживаемый ответ. Повторите позже."),
    MPStatsUpstreamError:(502,"MPSTATS_UPSTREAM","MPStats временно недоступен. Повторите позже."),
}
MPSTATS_ERROR_TYPES=tuple(MPSTATS_ERRORS)
def _mpstats_error_response(error):
    status,code,message=MPSTATS_ERRORS[type(error)]; content={"error":{"code":code,"message":message}}; headers={}
    retry=getattr(error,"retry_after_seconds",None)
    if retry is not None: content["retry_after_seconds"]=retry; headers["Retry-After"]=str(retry)
    return JSONResponse(status_code=status,content=content,headers=headers)

@app.patch("/api/products/{product_id}/ownership")
def patch_product_ownership(product_id: int,request: OwnershipUpdate) -> dict[str,object]:
    try:
        with transaction() as conn: product=ProductRepository(conn).set_owned(product_id,request.is_owned)
    except ProductNotFound: raise HTTPException(status_code=404,detail="Product not found") from None
    return {"id":product.id,"is_owned":product.is_owned,"updated_at":product.updated_at.isoformat()}

def _local_service(): return BenchmarkSelectionService(db_path=resolve_db_path())

@app.get("/api/products/{product_id}/relevant-queries")
def get_relevant_queries(product_id: Annotated[int,Path(gt=0)]):
    try: return _json(_local_service().get_relevant_queries(product_id))
    except PR6_ERROR_TYPES as error: return _pr6_error_response(error)

@app.put("/api/products/{product_id}/relevant-queries")
def put_relevant_queries(product_id: Annotated[int,Path(gt=0)],request: RelevantQueriesRequest):
    try: result=_local_service().replace_relevant_queries(product_id,tuple(request.search_query_ids))
    except PR6_ERROR_TYPES as error: return _pr6_error_response(error)
    return {**_json(result.selection),"changed":result.changed}

@app.get("/api/products/{product_id}/benchmark-candidates")
def get_benchmark_candidates(product_id: Annotated[int,Path(gt=0)],limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    try: return _json(_local_service().get_candidates(product_id,limit=limit,offset=offset))
    except PR6_ERROR_TYPES as error: return _pr6_error_response(error)

@app.post("/api/products/{product_id}/benchmark-candidates/manual")
def post_manual_candidate(product_id: Annotated[int,Path(gt=0)],request:ManualCandidateRequest):
    try: result=_local_service().add_manual_candidate(product_id,request.ozon_product_id)
    except PR6_ERROR_TYPES as error: return _pr6_error_response(error)
    return JSONResponse(status_code=201 if result.created else 200,content=_json(result))

@app.get("/api/products/{product_id}/benchmark")
def get_benchmark(product_id: Annotated[int,Path(gt=0)]):
    try: return _json(_local_service().get_benchmark(product_id))
    except PR6_ERROR_TYPES as error: return _pr6_error_response(error)

@app.post("/api/products/{product_id}/benchmark/revisions")
def post_benchmark_revision(product_id: Annotated[int,Path(gt=0)],request:BenchmarkRevisionRequest):
    try: result=_local_service().save_benchmark(product_id,tuple(request.member_product_ids))
    except PR6_ERROR_TYPES as error: return _pr6_error_response(error)
    return JSONResponse(status_code=201 if result.kind is not BenchmarkWriteKind.NO_CHANGE else 200,content={"result":result.kind.value,"benchmark_set":_json(result.benchmark_set),"revision":_json(result.revision)})

@app.post("/api/sources/mpstats/test")
def post_mpstats_test(request:MPStatsTestRequest):
    try:
        with httpx.Client(follow_redirects=False) as client:
            result=BenchmarkSelectionService(db_path=resolve_db_path(),mpstats_client=MPStatsClient(client)).test_mpstats(request.token,request.ozon_product_id)
    except MPSTATS_ERROR_TYPES as error: return _mpstats_error_response(error)
    return {"status":result.status.value,"message":"Подключение к MPStats подтверждено."}

@app.post("/api/sources/mpstats/ozon-product-previews")
def post_mpstats_previews(request:MPStatsPreviewsRequest):
    try:
        with httpx.Client(follow_redirects=False) as client:
            result=BenchmarkSelectionService(db_path=resolve_db_path(),mpstats_client=MPStatsClient(client)).enrich_mpstats_previews(request.token,tuple(request.ozon_product_ids))
    except MPSTATS_ERROR_TYPES as error: return _mpstats_error_response(error)
    return {"items":_json(result)}


@app.get("/", response_class=FileResponse)
def index() -> FileResponse:
    return FileResponse(FRONTEND_INDEX)


app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")
