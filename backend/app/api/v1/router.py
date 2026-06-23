from fastapi import APIRouter

from app.api.v1.endpoints import auth, estantes, health, import_, movimientos, productos, sectores, ubicaciones, usuarios

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(usuarios.router, prefix="/usuarios", tags=["usuarios"])
api_router.include_router(import_.router, prefix="/import", tags=["import"])
api_router.include_router(productos.router, prefix="/productos", tags=["productos"])
api_router.include_router(estantes.router, prefix="/estantes", tags=["estantes"])
api_router.include_router(estantes.depositos_router, prefix="/depositos", tags=["depositos"])
api_router.include_router(ubicaciones.router, prefix="/ubicaciones", tags=["ubicaciones"])
api_router.include_router(sectores.router, prefix="/sectores", tags=["sectores"])
api_router.include_router(movimientos.router, prefix="/movimientos", tags=["movimientos"])
