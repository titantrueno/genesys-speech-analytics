import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth as auth_router
from app.routers import config as config_router
from app.routers import conversations as conversations_router
from app.routers import flows as flows_router
from app.routers import metrics as metrics_router
from app.routers import query as query_router
from app.routers import search as search_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    # El índice de búsqueda se construye al arrancar, no en la primera búsqueda (FE003).
    search_router.build_default_engine()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Speech & Text Analytics API", lifespan=lifespan)
    origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(auth_router.router)
    app.include_router(metrics_router.router)
    app.include_router(conversations_router.router)
    app.include_router(query_router.router)
    app.include_router(search_router.router)
    app.include_router(flows_router.router)
    app.include_router(config_router.router)
    return app


app = create_app()
