from fastapi import APIRouter

from app.api.v1.endpoints import health, worlds

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(worlds.router)
