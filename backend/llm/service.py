"""Llamadas a los proveedores con límite de concurrencia y reintentos (FE013, criterios 6 y 7).

- Como mucho `max_concurrency` llamadas a la vez entre todas las peticiones (un semáforo global).
- `Transient` (límite de tasa, error del servidor o de red) se reintenta 2 veces, con esperas de 0,5 s y 1 s fuera del
  semáforo; si persiste, se convierte en `ProviderFailure` con el mismo mensaje.
- El log registra proveedor, modelo, intento, duración y resultado: nunca el prompt, la respuesta ni las claves.
"""
import logging
import threading
import time
from collections.abc import Callable

import httpx

from llm.providers.base import (Completion, CompletionRequest, LlmProvider, MissingKey, ProviderError,
                                ProviderFailure, Transient)
from llm.settings import Settings

logger = logging.getLogger("llm")
BACKOFF_S = (0.5, 1.0)


class UnknownProvider(Exception):
    pass


class Completer:
    def __init__(self, settings: Settings, providers: dict[str, LlmProvider], http: httpx.Client | None,
                 sleep: Callable[[float], None] = time.sleep, backoff: tuple[float, ...] = BACKOFF_S):
        self.settings, self.providers, self.http, self.sleep, self.backoff = settings, providers, http, sleep, backoff
        self._slots = threading.BoundedSemaphore(settings.max_concurrency)

    def key_configured(self, name: str) -> bool:
        provider = self.providers[name]
        return not provider.needs_key or bool(self.settings.api_keys.get(provider.key_env))

    def complete(self, name: str, request: CompletionRequest) -> Completion:
        provider = self.providers.get(name)
        if provider is None:
            raise UnknownProvider(name)
        key = self.settings.api_keys.get(provider.key_env) if provider.needs_key else None
        if provider.needs_key and not key:
            raise MissingKey(f"El proveedor {provider.label} no tiene clave configurada")
        for attempt in range(len(self.backoff) + 1):
            started = time.monotonic()
            try:
                with self._slots:
                    result = provider.complete(request, key, self.http)
            except Transient as exc:
                self._log(logging.WARNING, name, request, attempt, started, f"transitorio: {exc}")
                if attempt == len(self.backoff):
                    raise ProviderFailure(str(exc)) from None
                self.sleep(self.backoff[attempt])
                continue
            except ProviderError as exc:
                self._log(logging.WARNING, name, request, attempt, started, f"error: {exc}")
                raise
            self._log(logging.INFO, name, request, attempt, started, "ok")
            return result
        raise AssertionError("inalcanzable")

    @staticmethod
    def _log(level: int, name: str, request: CompletionRequest, attempt: int, started: float, outcome: str) -> None:
        logger.log(level, "proveedor=%s modelo=%s intento=%d duración_ms=%d resultado=%s", name, request.model,
                   attempt + 1, (time.monotonic() - started) * 1000, outcome)
