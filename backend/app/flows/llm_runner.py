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
from app.flows.rules import template_variables
from app.llm_client import UNAVAILABLE, LlmClient, LlmError, LlmUnavailable
from app.models import Conversation
from app.text import normalize_text

JSON_TYPES = {"texto": "string", "numero": "number", "booleano": "boolean", "lista": "array"}
STOPPING_CODES = {"missing_key", "key_rejected", "unknown_provider"}


def _property(field) -> dict:
    prop = {"type": "string"}
    if field.options:  # valores permitidos (FE013): el proveedor restringe la respuesta a ellos
        prop["enum"] = list(field.options)
    if field.type == "lista":  # lista de textos (FE014): los valores permitidos restringen cada elemento
        return {"type": "array", "items": prop}
    return prop if field.type == "texto" else {"type": JSON_TYPES[field.type]}


def json_schema(config: PromptConfig) -> dict:
    fields = config.output.fields or []
    return {"type": "object", "additionalProperties": False, "required": [f.name for f in fields],
            "properties": {f.name: _property(f) for f in fields}}


def _matching(value: str, options: list[str]) -> str | None:
    """La opción escrita como en la lista que coincide sin distinguir mayúsculas, tildes ni espacios en los extremos."""
    wanted = normalize_text(value.strip())
    return next((option for option in options if normalize_text(option.strip()) == wanted), None)


def _instructions(config: PromptConfig) -> str:
    """Lo que el modelo necesita saber del formato y que la plantilla de la persona usuaria puede no decir."""
    output = config.output
    if output.type == "etiqueta":
        return ("\n\nResponde únicamente con una de estas etiquetas, escrita exactamente igual y sin nada más: "
                + " | ".join(output.labels))
    if output.type == "json":
        return "\n\nResponde únicamente con un objeto JSON con los campos: " + ", ".join(
            f"{f.name} ({_type_hint(f)}: {' | '.join(f.options)})" if f.options else f"{f.name} ({_type_hint(f)})"
            for f in output.fields or [])
    return ""


def _type_hint(field) -> str:
    return "lista de textos" if field.type == "lista" else field.type


def _is_type(value: Any, field_type: str) -> bool:
    if field_type == "lista":
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
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
            raise PromptRejected("The answer is empty")
        return answer
    if output.type == "etiqueta":
        label = _matching(answer, output.labels)
        if label is None:
            raise PromptRejected(f"“{answer[:80]}” is not one of the labels")
        return label
    try:
        data = json.loads(answer)
    except ValueError:
        raise PromptRejected("The answer is not valid JSON") from None
    fields = {f.name: f.type for f in output.fields or []}
    if not isinstance(data, dict) or set(data) != set(fields):
        raise PromptRejected("The JSON does not have exactly the fields of the schema")
    wrong = [name for name, field_type in fields.items() if not _is_type(data[name], field_type)]
    if wrong:
        raise PromptRejected(f"Wrong type in: {', '.join(wrong)}")
    result = {name: data[name] for name in fields}
    for field in output.fields or []:
        if field.options:
            values = result[field.name] if field.type == "lista" else [result[field.name]]
            allowed = [_allowed(value, field) for value in values]
            result[field.name] = allowed if field.type == "lista" else allowed[0]
    return result


def _allowed(value: str, field) -> str:
    option = _matching(value, field.options)
    if option is None:
        raise PromptRejected(f"“{value[:80]}” is not an allowed value of {field.name}")
    return option


class LlmPromptRunner:
    parallelism = 4  # como el límite por defecto del servicio (`LLM_MAX_CONCURRENCY`)

    def __init__(self, client: LlmClient):
        self.client = client

    def run(self, config: PromptConfig, conversation: Conversation, previous: Any | None) -> Any:
        # Sin transcripción no hay nada que resumir: el LLM inventaría la respuesta (comprobado en T9 de FE013).
        if "transcripcion" in template_variables(config.template) and not any(t.text.strip() for t in conversation.turns):
            raise PromptRejected("The conversation has no transcript: it is not sent to the LLM")
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
