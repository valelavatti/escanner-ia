from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import get_db_connection
from app.core.migrations import run_migrations

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup/shutdown logic."""
    connection = await get_db_connection(settings.db_path)
    try:
        await run_migrations(connection)
    finally:
        await connection.close()

    Path(settings.qr_cache_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="ASG Scanner API",
    version="0.1.0",
    lifespan=lifespan,
)


class DevCORSMiddleware(BaseHTTPMiddleware):
    """CORS middleware that allows all origins in development.

    In development, the frontend may be served from localhost, a LAN IP,
    or an ngrok HTTPS tunnel. Instead of maintaining an exhaustive allow-list,
    we allow all origins when the request includes an Origin header.
    For production, replace this with a strict allow-list.
    """

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        response = await call_next(request)
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, Accept"
        return response


# Handle CORS preflight (OPTIONS) before other middleware
@app.middleware("http")
async def cors_preflight(request: Request, call_next):
    if request.method == "OPTIONS":
        origin = request.headers.get("origin", "")
        from starlette.responses import Response
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept",
            },
        )
    response = await call_next(request)
    origin = request.headers.get("origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, Accept"
    return response


app.include_router(api_router, prefix="/api/v1")
