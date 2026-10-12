"""Contrato de un proveedor de LLM (FE013, criterio 4).

Un proveedor recibe una `CompletionRequest` y devuelve una `Completion`. Los proveedores con red (`HttpProvider`)
solo saben construir su petición y leer su respuesta; la clasificación de errores es común:

- `KeyRejected`: el proveedor rechaza la clave (`401`/`403`); no se reintenta.
- `Transient`: límite de tasa, error del servidor o de red; el servicio reintenta.
- `ProviderFailure`: cualquier otro fallo (`4xx`, respuesta bloqueada, cortada o con forma inesperada).

Los mensajes nunca incluyen el cuerpo de error del proveedor, que puede repetir la clave o el prompt.
"""
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx

RETRYABLE = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class OutputSpec:
    type: Literal["texto", "etiqueta", "json"]
    labels: list[str] | None = None
    schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class CompletionRequest:
    model: str
    prompt: str
    output: OutputSpec
    temperature: float | None = None  # `None`: el modelo no la admite y no se envía


@dataclass(frozen=True)
class Completion:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class ProviderError(Exception):
    status = 502
    code = "provider_failure"  # la API distingue los fallos por el código, no por el texto


class MissingKey(ProviderError):
    status = 503
    code = "missing_key"


class KeyRejected(ProviderError):
    code = "key_rejected"

    def __init__(self):
        super().__init__("El proveedor rechazó la clave")


class Transient(ProviderError):
    pass


class ProviderFailure(ProviderError):
    pass


class LlmProvider(Protocol):
    name: str
    label: str
    needs_key: bool
    key_env: str | None

    def complete(self, request: CompletionRequest, key: str | None, http: httpx.Client | None) -> Completion: ...


class HttpProvider:
    name: str
    label: str
    key_env: str
    needs_key = True
    retryable = RETRYABLE

    def build(self, request: CompletionRequest, key: str) -> tuple[str, dict[str, str], dict[str, Any]]:
        """URL, cabeceras y cuerpo JSON de la petición."""
        raise NotImplementedError

    def parse(self, body: dict[str, Any], request: CompletionRequest) -> Completion:
        raise NotImplementedError

    def rejects_key(self, response: httpx.Response) -> bool:
        return response.status_code in (401, 403)

    def failure(self, reason: str) -> ProviderFailure:
        return ProviderFailure(f"{self.label} {reason}")

    def complete(self, request: CompletionRequest, key: str | None, http: httpx.Client | None) -> Completion:
        url, headers, body = self.build(request, key)
        try:
            response = http.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise Transient(f"No se pudo contactar con {self.label} ({type(exc).__name__})") from None
        if self.rejects_key(response):
            raise KeyRejected()
        if response.status_code in self.retryable:
            raise Transient(f"{self.label} respondió {response.status_code}")
        if response.status_code >= 400:
            raise self.failure(f"respondió {response.status_code}")
        try:
            return self.parse(response.json(), request)
        except ProviderError:
            raise
        except (ValueError, KeyError, TypeError, IndexError, AttributeError):
            raise self.failure("devolvió una respuesta con forma inesperada") from None
