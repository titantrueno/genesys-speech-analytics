"""Prompts con un LLM real a través del servicio de LLM (FE013, criterios 11 a 14; ADR-006).

`LlmPromptRunner` renderiza la plantilla (siempre con texto enmascarado), pide al servicio la respuesta en el formato
del nodo y la valida: el texto se recorta y no puede quedar vacío; la etiqueta debe ser una de la lista (sin distinguir
mayúsculas, tildes ni espacios en los extremos) y se devuelve tal como está escrita en la lista; el JSON debe tener
exactamente los campos del esquema con su tipo. `RoutingPromptRunner` elige por el proveedor del nodo: sin proveedor o
con `simulado`, el `MockPromptRunner` de siempre.
"""
import json
from typing import Any

from app.flows import catalog
from app.flows.model import PromptConfig
from app.flows.prompting import (MockPromptRunner, PromptFailed, PromptRejected, PromptRunner, PromptUnavailable,
                                 render_template)
from app.llm_client import UNAVAILABLE, LlmClient, LlmError, LlmUnavailable
from app.models import Conversation
from app.text import normalize_text

JSON_TYPES = {"texto": "string", "numero": "number", "booleano": "boolean"}
STOPPING_CODES = {"missing_key", "key_rejected", "unknown_provider"}


def json_schema(config: PromptConfig) -> dict:
    fields = config.output.fields or []
    return {"type": "object", "additionalProperties": False, "required": [f.name for f in fields],
            "properties": {f.name: {"type": JSON_TYPES[f.type]} for f in fields}}


def _instructions(config: PromptConfig) -> str:
    """Lo que el modelo necesita saber del formato y que la plantilla de la persona usuaria puede no decir."""
    output = config.output
    if output.type == "etiqueta":
        return ("\n\nResponde únicamente con una de estas etiquetas, escrita exactamente igual y sin nada más: "
                + " | ".join(output.labels))
    if output.type == "json":
        return "\n\nResponde únicamente con un objeto JSON con los campos: " + ", ".join(
            f"{f.name} ({f.type})" for f in output.fields or [])
    return ""


def _is_type(value: Any, field_type: str) -> bool:
    if field_type == "booleano":
        return isinstance(value, bool)
    if field_type == "numero":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, str)


def validate_answer(config: PromptConfig, text: str) -> Any:
    output = config.output
    answer = text.strip()
    if output.type == "texto":
        if not answer:
            raise PromptRejected("La respuesta está vacía")
        return answer
    if output.type == "etiqueta":
        wanted = normalize_text(answer)
        label = next((label for label in output.labels if normalize_text(label.strip()) == wanted), None)
        if label is None:
            raise PromptRejected(f"«{answer[:80]}» no es una de las etiquetas")
        return label
    try:
        data = json.loads(answer)
    except ValueError:
        raise PromptRejected("La respuesta no es JSON válido") from None
    fields = {f.name: f.type for f in output.fields or []}
    if not isinstance(data, dict) or set(data) != set(fields):
        raise PromptRejected("El JSON no tiene exactamente los campos del esquema")
    wrong = [name for name, field_type in fields.items() if not _is_type(data[name], field_type)]
    if wrong:
        raise PromptRejected(f"Tipo incorrecto en: {', '.join(wrong)}")
    return {name: data[name] for name in fields}


class LlmPromptRunner:
    parallelism = 4  # como el límite por defecto del servicio (`LLM_MAX_CONCURRENCY`)

    def __init__(self, client: LlmClient):
        self.client = client

    def run(self, config: PromptConfig, conversation: Conversation, previous: Any | None) -> Any:
        output: dict[str, Any] = {"type": config.output.type}
        if config.output.type == "etiqueta":
            output["labels"] = list(config.output.labels)
        elif config.output.type == "json":
            output["schema"] = json_schema(config)
        body = {"provider": config.provider, "model": config.model, "output": output,
                "prompt": render_template(config.template, conversation, previous) + _instructions(config),
                "temperature": config.temperature if catalog.supports_temperature(config.model) else None}
        try:
            text = self.client.complete(body)["text"]
        except LlmUnavailable:
            raise PromptUnavailable(UNAVAILABLE) from None
        except LlmError as exc:
            raise (PromptUnavailable if exc.code in STOPPING_CODES else PromptFailed)(exc.detail) from None
        return validate_answer(config, text)


class RoutingPromptRunner:
    def __init__(self, simulated: PromptRunner, llm: LlmPromptRunner):
        self.simulated, self.llm = simulated, llm

    def _runner(self, config: PromptConfig):
        return self.simulated if (config.provider or catalog.SIMULATED) == catalog.SIMULATED else self.llm

    def run(self, config: PromptConfig, conversation: Conversation, previous: Any | None) -> Any:
        return self._runner(config).run(config, conversation, previous)

    def parallelism_for(self, config: PromptConfig) -> int:
        return getattr(self._runner(config), "parallelism", 1)


def build_runner(client: LlmClient) -> RoutingPromptRunner:
    return RoutingPromptRunner(MockPromptRunner(), LlmPromptRunner(client))
