"""Aplicación FastAPI del servicio de LLM (FE013).

`uvicorn llm.main:app --port 8002` desde `backend/`. Es el único proceso que conoce las claves de los proveedores; solo
lo llama la API, nunca un navegador (no declara CORS). Todas las rutas exigen el token interno `LLM_TOKEN` salvo
`/health`, que dice si el servicio responde y qué proveedores tienen clave (sí o no, nunca la clave).
"""
import time
from collections.abc import Callable
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, FastAPI, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from llm.providers import REGISTRY
from llm.providers.base import CompletionRequest, LlmProvider, OutputSpec, ProviderError
from llm.security import internal_token_guard
from llm.service import BACKOFF_S, Completer, UnknownProvider
from llm.settings import Settings, load_settings

VERSION = "0.9.0"  # se entrega con la plataforma
TIMEOUT_S = 60.0
MODEL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$"  # el modelo va en la URL de Gemini: nada de `/` ni `..`
TEST_PROMPT = "Responde únicamente con la palabra: ok"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class OutputIn(_Strict):
    type: Literal["texto", "etiqueta", "json"] = "texto"
    labels: list[str] | None = None
    schema_: dict | None = Field(None, alias="schema")


class CompleteIn(_Strict):
    provider: str
    model: str = Field(pattern=MODEL_PATTERN)
    prompt: str = Field(min_length=1, max_length=200_000)
    temperature: float | None = Field(None, ge=0, le=2)
    output: OutputIn = OutputIn()


class TestIn(_Strict):
    model: str = Field(pattern=MODEL_PATTERN)


class Failure(Exception):
    def __init__(self, exc: Exception):
        unknown = isinstance(exc, UnknownProvider)
        self.status = status.HTTP_404_NOT_FOUND if unknown else exc.status
        self.body = {"detail": f"Proveedor desconocido: {exc}" if unknown else str(exc),
                     "code": "unknown_provider" if unknown else exc.code}


def create_app(settings: Settings | None = None, providers: dict[str, LlmProvider] | None = None,
               http: httpx.Client | None = None, sleep: Callable[[float], None] = time.sleep,
               backoff: tuple[float, ...] = BACKOFF_S) -> FastAPI:
    settings = settings or load_settings()
    providers = providers or REGISTRY
    completer = Completer(settings, providers, http or httpx.Client(timeout=TIMEOUT_S), sleep, backoff)
    app = FastAPI(title="Servicio de LLM", version=VERSION)

    @app.exception_handler(Failure)
    async def failure(_, exc: Failure) -> JSONResponse:
        return JSONResponse(exc.body, status_code=exc.status)

    @app.get("/health", summary="Estado del servicio y proveedores con clave configurada")
    def health():
        return {"status": "ok", "keys": {name: completer.key_configured(name) for name in providers}}

    router = APIRouter(dependencies=[Depends(internal_token_guard(settings.token))])

    def run(name: str, request: CompletionRequest):
        try:
            return completer.complete(name, request)
        except (UnknownProvider, ProviderError) as exc:
            raise Failure(exc) from None

    @router.post("/complete", summary="Respuesta del modelo a un prompt, con el formato pedido")
    def complete(body: CompleteIn):
        output = OutputSpec(body.output.type, body.output.labels, body.output.schema_)
        result = run(body.provider, CompletionRequest(body.model, body.prompt, output, body.temperature))
        return {"text": result.text, "provider": body.provider, "model": result.model,
                "usage": {"input_tokens": result.input_tokens, "output_tokens": result.output_tokens}}

    @router.post("/providers/{name}/test", summary="Prueba un proveedor con una petición mínima")
    def test_provider(name: str, body: TestIn):
        run(name, CompletionRequest(body.model, TEST_PROMPT, OutputSpec("texto")))
        return {"ok": True, "provider": name, "model": body.model, "message": "El proveedor respondió correctamente"}

    app.include_router(router)
    return app


def __getattr__(name: str):
    # `app` se crea al pedirlo (uvicorn), no al importar el módulo: los tests construyen la suya con `create_app`.
    if name == "app":
        return create_app()
    raise AttributeError(name)
