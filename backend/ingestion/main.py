"""Aplicación FastAPI del servicio de ingesta (FE011).

`uvicorn ingestion.main:app --port 8001` desde `backend/`. No declara CORS: solo la llama la API, nunca un navegador.
Toda ruta exige el token interno salvo la documentación propia (`/openapi.json` y `/docs`).
"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from ingestion import db
from ingestion.settings import Settings, load_settings
from ingestion.security import internal_token_guard

VERSION = "0.1.0"


def create_app(settings: Settings | None = None, migrate_on_start: bool = True) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if migrate_on_start:
            with db.connect(settings.database_url) as conn:
                db.migrate(conn)
        yield

    app = FastAPI(title="Servicio de ingesta de Genesys Cloud", version=VERSION, lifespan=lifespan,
                  dependencies=[Depends(internal_token_guard(settings.token))])
    app.state.settings = settings

    @app.get("/health", summary="Estado del servicio y de PostgreSQL")
    def health():
        if not db.ping(settings.database_url):
            return JSONResponse({"status": "error", "database": "no disponible"}, status_code=503)
        return {"status": "ok", "database": "ok"}

    return app


def __getattr__(name: str):
    # `app` se crea al pedirlo (uvicorn), no al importar el módulo: los tests construyen la suya con `create_app`.
    if name == "app":
        return create_app()
    raise AttributeError(name)
