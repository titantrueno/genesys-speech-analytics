from fastapi import FastAPI

from app.routers import auth as auth_router


def create_app() -> FastAPI:
    app = FastAPI(title="Speech & Text Analytics API")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(auth_router.router)
    return app


app = create_app()
