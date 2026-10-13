"""Anthropic: Messages API (FE013).

`POST /v1/messages` con `x-api-key` y `anthropic-version: 2023-06-01`. Los modelos vigentes (Claude Opus 5.5,
Sonnet 5.5 y Haiku 5.5) rechazan `temperature`: el catálogo de la API lo sabe y no la envía. Piensan siempre, así que la
respuesta puede traer bloques `thinking` antes del texto, y `max_tokens` deja margen para ello. En Opus 5.5 y Sonnet
5.5 se activa el respaldo en el servidor (`fallbacks: "default"`): si el modelo declina por seguridad, la API reintenta
con otro modelo en la misma llamada. El JSON con esquema va en `output_config.format`.
"""
from typing import Any

from llm.providers.base import RETRYABLE, Completion, CompletionRequest, HttpProvider

URL = "https://api.anthropic.com/v1/messages"
VERSION = "2023-06-01"
MAX_TOKENS = 16000
FALLBACK_BETA = "server-side-fallback-2026-07-01"
FALLBACK_MODELS = frozenset({"claude-opus-5-5", "claude-sonnet-5-5"})


class Anthropic(HttpProvider):
    name, label, key_env = "anthropic", "Anthropic", "ANTHROPIC_API_KEY"
    retryable = RETRYABLE | {529}  # `overloaded_error`

    def build(self, request: CompletionRequest, key: str) -> tuple[str, dict[str, str], dict[str, Any]]:
        headers = {"x-api-key": key, "anthropic-version": VERSION}
        body: dict[str, Any] = {"model": request.model, "max_tokens": MAX_TOKENS,
                                "messages": [{"role": "user", "content": request.prompt}]}
        if request.model in FALLBACK_MODELS:
            headers["anthropic-beta"] = FALLBACK_BETA
            body["fallbacks"] = "default"
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.output.type == "json":
            body["output_config"] = {"format": {"type": "json_schema", "schema": request.output.schema}}
        return URL, headers, body

    def parse(self, body: dict[str, Any], request: CompletionRequest) -> Completion:
        stop = body["stop_reason"]
        if stop == "refusal":
            raise self.failure("declined to answer")
        if stop == "max_tokens":
            raise self.failure("returned a truncated response")
        text = "".join(block["text"] for block in body["content"] if block.get("type") == "text")
        usage = body.get("usage") or {}
        return Completion(text=text, model=body.get("model") or request.model,
                          input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"))
