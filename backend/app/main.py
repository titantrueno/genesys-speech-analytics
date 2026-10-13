import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import auth
from app.config.store import get_config
from app.data.real import begin_request
from app.data.repository import DataUnavailable
from app.openapi.spec import API_VERSION, build_openapi
from app.routers import auth as auth_router
from app.routers import config as config_router
from app.routers import conversations as conversations_router
from app.routers import downloads as downloads_router
from app.routers import flows as flows_router
from app.routers import metrics as metrics_router
from app.routers import query as query_router
from app.routers import search as search_router
from app.routers import users as users_router
from app.state_backend import StateUnavailable


AUTH_VERSION_HEADER = "X-Auth-Version"
DATA_UNAVAILABLE = "Los datos reales no están disponibles"


@asynccontextmanager
async def lifespan(_: FastAPI):
    # La configuración guardada (el origen de datos, FE015) se carga antes de construir el índice de búsqueda, que se
    # construye al arrancar y no en la primera búsqueda (FE003).
    get_config()
    search_router.search_index.engine()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Speech & Text Analytics API", version=API_VERSION, lifespan=lifespan)
    origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=[AUTH_VERSION_HEADER],
    )

    @app.middleware("http")
    async def new_request(request: Request, call_next):
        """Cada petición comprueba una vez si PostgreSQL tiene datos nuevos (FE012, criterio 4)."""
        begin_request()
        return await call_next(request)

    @app.middleware("http")
    async def auth_version(request: Request, call_next):
        """Versión de usuarios y roles: si cambia, el front vuelve a pedir `/api/auth/me` (FE006).

        Solo en peticiones con sesión: sin ella no hay permisos que refrescar y no se revela la actividad de la gestión.
        """
        response = await call_next(request)
        if "authorization" in request.headers:
            response.headers[AUTH_VERSION_HEADER] = str(auth.get_store().version)
        return response

    @app.exception_handler(DataUnavailable)
    async def data_unavailable(_: Request, __: DataUnavailable) -> JSONResponse:
        """El origen `real` no responde (FE012, criterio 3): las secciones de datos caen; Configuración sigue sirviendo."""
        return JSONResponse({"detail": DATA_UNAVAILABLE}, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    @app.exception_handler(StateUnavailable)
    async def state_unavailable(_: Request, exc: StateUnavailable) -> JSONResponse:
        """No se pueden leer o guardar los flujos de insights o la configuración (FE015): el cambio no se aplica."""
        return JSONResponse({"detail": exc.detail}, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(auth_router.router)
    app.include_router(metrics_router.router)
    app.include_router(conversations_router.router)
    app.include_router(query_router.router)
    app.include_router(search_router.router)
    app.include_router(flows_router.router)
    app.include_router(downloads_router.router)
    app.include_router(config_router.router)
    app.include_router(users_router.router)

    def openapi() -> dict:
        # Esquema completo (respuestas, errores, seguridad); se construye una vez y lo sirven /openapi.json y /docs.
        if app.openapi_schema is None:
            app.openapi_schema = build_openapi(app)
        return app.openapi_schema

    app.openapi = openapi
    return app


app = create_app()
