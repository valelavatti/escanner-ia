from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, import_, usuarios

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(usuarios.router, prefix="/usuarios", tags=["usuarios"])
api_router.include_router(import_.router, prefix="/import", tags=["import"])
