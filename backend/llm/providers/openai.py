"""OpenAI: Chat Completions (FE013).

Documentación consultada el 2026-10-12:
https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create y
https://developers.openai.com/api/docs/guides/structured-outputs (`response_format` con `json_schema` estricto).
"""
from typing import Any

from llm.providers.base import Completion, CompletionRequest, HttpProvider

URL = "https://api.openai.com/v1/chat/completions"


class OpenAI(HttpProvider):
    name, label, key_env = "openai", "OpenAI", "OPENAI_API_KEY"

    def build(self, request: CompletionRequest, key: str) -> tuple[str, dict[str, str], dict[str, Any]]:
        body: dict[str, Any] = {"model": request.model, "messages": [{"role": "user", "content": request.prompt}]}
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.output.type == "json":
            body["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "resultado", "schema": request.output.schema, "strict": True}}
        return URL, {"Authorization": f"Bearer {key}"}, body

    def parse(self, body: dict[str, Any], request: CompletionRequest) -> Completion:
        choice = body["choices"][0]
        message = choice["message"]
        if message.get("refusal"):
            raise self.failure("declined to answer")
        if choice.get("finish_reason") == "length":
            raise self.failure("returned a truncated response")
        usage = body.get("usage") or {}
        return Completion(text=message["content"], model=body.get("model") or request.model,
                          input_tokens=usage.get("prompt_tokens"), output_tokens=usage.get("completion_tokens"))
