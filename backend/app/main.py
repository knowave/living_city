import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    DomainError,
    DomainValidationError,
    InvalidStateError,
    NotFoundError,
)

logger = logging.getLogger(__name__)

# uvicorn configures only its own loggers; give app.* (runner cycle logs, measurements) an INFO handler.
_app_logger = logging.getLogger("app")
if not _app_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    _app_logger.addHandler(_handler)
    _app_logger.setLevel(logging.INFO)

_DOMAIN_STATUS: dict[type[DomainError], int] = {
    NotFoundError: 404,
    ConflictError: 409,
    InvalidStateError: 409,
    DomainValidationError: 422,
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.DB_AUTO_SYNC:
        import app.models  # noqa: F401  (register tables on Base.metadata)
        from app.db.base import Base
        from app.db.session import engine

        try:
            Base.metadata.create_all(bind=engine)
        except OperationalError as e:
            logger.warning("DB auto-sync skipped, database unreachable: %s", e.__cause__ or e)
    manager = None
    if settings.RUNNER_ENABLED:
        from app.api.deps import build_runner_manager

        manager = build_runner_manager()
        manager.start()
    yield
    if manager is not None:
        await manager.stop()


async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
    status = next((code for cls, code in _DOMAIN_STATUS.items() if isinstance(exc, cls)), 400)
    error = {"code": exc.code, "message": exc.message}
    if exc.details is not None:
        error["details"] = jsonable_encoder(exc.details)
    return JSONResponse(status_code=status, content={"error": error})


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request",
                "details": jsonable_encoder(exc.errors()),
            }
        },
    )


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.include_router(api_router, prefix=settings.API_V1_STR)
app.add_exception_handler(DomainError, domain_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
