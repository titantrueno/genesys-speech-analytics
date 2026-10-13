"""Modelos de cada sección de la configuración (FE005). Todas rechazan campos desconocidos."""
from functools import cache
from typing import Annotated, Any, Literal, TypeVar
from zoneinfo import available_timezones

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError, field_validator, model_validator

from app.flows.catalog import PROVIDERS

LANGUAGES = {"es-ES": "Español (España)", "en-US": "English (United States)"}
MAX_PLATFORM_NAME = 60

SECTIONS = {
    "general": "General",
    "fuentes": "Fuentes de datos",
    "taxonomia": "Taxonomía",
    "kpis": "KPIs y objetivos",
    "cumplimiento": "Cumplimiento",
    "privacidad": "Privacidad",
    "modelos": "Modelos de IA",
}


@cache
def timezones() -> list[str]:
    return sorted(available_timezones())


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GeneralConfig(Section):
    platform_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_PLATFORM_NAME)]
    timezone: str
    language: str

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        if value not in timezones():
            raise ValueError("Unknown time zone")
        return value

    @field_validator("language")
    @classmethod
    def _available_language(cls, value: str) -> str:
        if value not in LANGUAGES:
            raise ValueError(f"Language not available; options: {', '.join(LANGUAGES)}")
        return value


class SourcesConfig(Section):
    """Data origin of the whole platform (FE012): the synthetic dataset or the real Genesys conversations."""
    origin: Literal["sintetico", "real"]


class PrivacyConfig(Section):
    pii_masking: bool


class AiConfig(Section):
    provider: str
    model: str

    @field_validator("provider")
    @classmethod
    def _known_provider(cls, value: str) -> str:
        if value not in PROVIDERS:
            raise ValueError("Unknown provider")
        return value

    @model_validator(mode="after")
    def _model_of_provider(self) -> "AiConfig":
        if self.provider in PROVIDERS and self.model not in PROVIDERS[self.provider]["models"]:
            raise ValidationError.from_exception_data("AiConfig", [{
                "type": "value_error", "loc": ("model",), "input": self.model,
                "ctx": {"error": ValueError("The model does not belong to the provider")},
            }])
        return self


_MESSAGES = {
    "missing": "Required field",
    "extra_forbidden": "Field not allowed",
    "string_type": "Must be a text",
    "bool_type": "Must be true or false",
    "bool_parsing": "Must be true or false",
    "int_type": "Must be an integer",
    "int_parsing": "Must be an integer",
    "float_type": "Must be a number",
    "float_parsing": "Must be a number",
    "list_type": "Must be a list",
    "dict_type": "Must be an object",
    "model_type": "Must be an object",
}


def _message(err: dict) -> str:
    ctx = err.get("ctx") or {}
    match err["type"]:
        case "value_error":
            return str(ctx.get("error", err["msg"]))
        case "string_too_short":
            return "Cannot be empty" if ctx.get("min_length") == 1 else f"Minimum {ctx['min_length']} characters"
        case "string_too_long":
            return f"Maximum {ctx['max_length']} characters"
        case "too_short":
            return f"Minimum {ctx['min_length']} items"
        case "too_long":
            return f"Maximum {ctx['max_length']} items"
        case "greater_than_equal":
            return f"Must be greater than or equal to {ctx['ge']}"
        case "less_than_equal":
            return f"Must be less than or equal to {ctx['le']}"
        case "string_pattern_mismatch":
            return "Invalid format"
        case other:
            return _MESSAGES.get(other, err["msg"])


def field_errors(exc: ValidationError) -> list[dict]:
    """Errores en el formato de FastAPI (`loc`, `msg`, `type`) con mensajes en español para la UI."""
    return [{"loc": ["body", *err["loc"]], "msg": _message(err), "type": err["type"]} for err in exc.errors()]


Model = TypeVar("Model", bound=BaseModel)


def parse_body(model: type[Model], payload: Any) -> Model:
    """Valida el cuerpo con `model` y responde `422` con errores por campo en español."""
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=field_errors(exc)) from None
