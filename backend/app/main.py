from fastapi import FastAPI

from app.routers import auth as auth_router
from app.routers import conversations as conversations_router
from app.routers import metrics as metrics_router


def create_app() -> FastAPI:
    app = FastAPI(title="Speech & Text Analytics API")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(auth_router.router)
    app.include_router(metrics_router.router)
    app.include_router(conversations_router.router)
    return app


app = create_app()
