"""Gemini (Google): `generateContent` de la API de Gemini (FE013).

Documentación consultada el 2026-10-12: https://ai.google.dev/api/generate-content y
https://ai.google.dev/gemini-api/docs/generate-content/structured-output. El JSON con esquema va en
`generationConfig.responseMimeType` + `responseJsonSchema`: comprobado contra la API real ese día, la forma REST de la
guía (`responseFormat.text` con `mimeType: "application/json"`) responde `400`. La clave viaja en la cabecera
`x-goog-api-key`, nunca en la URL.
"""
from typing import Any

import httpx

from llm.providers.base import Completion, CompletionRequest, HttpProvider

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class Gemini(HttpProvider):
    name, label, key_env = "gemini", "Gemini", "GEMINI_API_KEY"

    def build(self, request: CompletionRequest, key: str) -> tuple[str, dict[str, str], dict[str, Any]]:
        body: dict[str, Any] = {"contents": [{"role": "user", "parts": [{"text": request.prompt}]}]}
        config: dict[str, Any] = {}
        if request.temperature is not None:
            config["temperature"] = request.temperature
        if request.output.type == "json":
            config["responseMimeType"] = "application/json"
            config["responseJsonSchema"] = request.output.schema
        if config:
            body["generationConfig"] = config
        return f"{BASE_URL}/{request.model}:generateContent", {"x-goog-api-key": key}, body

    def rejects_key(self, response: httpx.Response) -> bool:
        # Una clave no válida llega como `400 INVALID_ARGUMENT` con el motivo `API_KEY_INVALID`.
        return super().rejects_key(response) or (response.status_code == 400 and "API_KEY_INVALID" in response.text)

    def parse(self, body: dict[str, Any], request: CompletionRequest) -> Completion:
        blocked = (body.get("promptFeedback") or {}).get("blockReason")
        if blocked:
            raise self.failure(f"blocked the prompt ({blocked})")
        candidate = body["candidates"][0]
        reason = candidate.get("finishReason")
        if reason == "MAX_TOKENS":
            raise self.failure("returned a truncated response")
        if reason not in (None, "STOP"):
            raise self.failure(f"did not finish the answer ({reason})")
        # Las partes de razonamiento (`thought`) no son la respuesta.
        text = "".join(p["text"] for p in candidate["content"]["parts"] if "text" in p and not p.get("thought"))
        usage = body.get("usageMetadata") or {}
        return Completion(text=text, model=body.get("modelVersion") or request.model,
                          input_tokens=usage.get("promptTokenCount"), output_tokens=usage.get("candidatesTokenCount"))
