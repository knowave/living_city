import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.exc import OperationalError

from app.api.v1.api import api_router
from app.core.config import settings

logger = logging.getLogger(__name__)


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
    yield


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.include_router(api_router, prefix=settings.API_V1_STR)
