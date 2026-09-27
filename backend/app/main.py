from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Speech & Text Analytics API")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
