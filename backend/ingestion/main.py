"""Aplicación FastAPI del servicio de ingesta (FE011).

`uvicorn ingestion.main:app --port 8001` desde `backend/`. No declara CORS: solo la llama la API, nunca un navegador.
Toda ruta exige el token interno salvo la documentación propia (`/openapi.json` y `/docs`).

Al arrancar: aplica las migraciones, da por interrumpidas las ejecuciones que quedaron activas, recalcula la próxima
ejecución de cada flujo programado (las perdidas no se recuperan) y arranca el programador.
"""
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

from app.clock import now as real_now
from ingestion import db, flows
from ingestion.analysis import build_analysis_router
from ingestion.api import Context, build_insight_downloads_router, build_router, build_status_router
from ingestion.genesys.client import GenesysAuthError, GenesysClient
from ingestion.pipeline.analyze import Analyzer
from ingestion.pipeline.read import read_conversation
from ingestion.scheduler import Job, Scheduler
from ingestion.security import internal_token_guard
from ingestion.settings import Settings, load_settings
from ingestion.state import build_state_router

VERSION = "0.13.0"  # se entrega con la plataforma
MAX_PARALLEL_RUNS = 2


def genesys_client_factory(settings: Settings) -> Callable[[], GenesysClient]:
    def factory() -> GenesysClient:
        if not (settings.genesys_client_id and settings.genesys_client_secret and settings.genesys_region):
            raise GenesysAuthError("Genesys credentials (GENESYS_*) are missing in the .env")
        return GenesysClient(settings.genesys_client_id, settings.genesys_client_secret, settings.genesys_region)
    return factory


def create_app(settings: Settings | None = None, migrate_on_start: bool = True,
               client_factory: Callable[[], GenesysClient] | None = None, clock: Callable[[], datetime] = real_now,
               run_in_background: Callable[[Job], None] | None = None, scheduler: bool = True,
               analyzer: Analyzer | None = None) -> FastAPI:
    settings = settings or load_settings()
    client_factory = client_factory or genesys_client_factory(settings)
    pool = None
    if run_in_background is None:
        pool = ThreadPoolExecutor(max_workers=MAX_PARALLEL_RUNS, thread_name_prefix="descarga")
        run_in_background = pool.submit
    ctx = Context(settings.database_url, clock, client_factory, run_in_background, analyzer,
                  region=settings.genesys_region,
                  credentials_configured=bool(settings.genesys_client_id and settings.genesys_client_secret))
    programmer = Scheduler(settings.database_url, client_factory, clock, run_in_background, analyzer)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if migrate_on_start:
            with db.connect(settings.database_url) as conn:
                db.migrate(conn)
                flows.interrupt_active_runs(conn, clock())
                flows.refresh_schedules(conn, clock())
            if scheduler:
                programmer.start()
        yield
        programmer.stop()
        if pool:
            pool.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="Genesys Cloud ingestion service", version=VERSION, lifespan=lifespan,
                  dependencies=[Depends(internal_token_guard(settings.token))])
    app.state.settings = settings
    app.state.scheduler = programmer

    @app.get("/health", summary="Status of the service and of PostgreSQL")
    def health():
        if not db.ping(settings.database_url):
            return JSONResponse({"status": "error", "database": "unavailable"}, status_code=503)
        return {"status": "ok", "database": "ok"}

    @app.get("/conversations/{key}", summary="Normalized conversation by its 1CO or its Genesys identifier")
    def get_conversation(key: str):
        with db.connect(settings.database_url) as conn:
            conversation = read_conversation(conn, key)
        if conversation is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        return conversation

    app.include_router(build_router(ctx))
    app.include_router(build_insight_downloads_router(ctx))
    app.include_router(build_status_router(ctx))
    app.include_router(build_analysis_router(settings.database_url, clock))
    app.include_router(build_state_router(settings.database_url, clock))
    return app


def __getattr__(name: str):
    # `app` se crea al pedirlo (uvicorn), no al importar el módulo: los tests construyen la suya con `create_app`.
    if name == "app":
        return create_app()
    raise AttributeError(name)
