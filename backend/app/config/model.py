"""Modelos de cada sección de la configuración (FE005). Todas rechazan campos desconocidos."""
from functools import cache
from typing import Annotated, Any, Literal, TypeVar
from zoneinfo import available_timezones

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError, field_validator, model_validator

from app.flows.catalog import PROVIDERS

LANGUAGES = {"es-ES": "Español (España)"}
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
            raise ValueError("Zona horaria desconocida")
        return value

    @field_validator("language")
    @classmethod
    def _available_language(cls, value: str) -> str:
        if value not in LANGUAGES:
            raise ValueError(f"Idioma no disponible; opciones: {', '.join(LANGUAGES)}")
        return value


class SourcesConfig(Section):
    """Origen de datos de toda la plataforma (FE012): el dataset sintético o las conversaciones reales de Genesys."""
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
            raise ValueError("Proveedor desconocido")
        return value

    @model_validator(mode="after")
    def _model_of_provider(self) -> "AiConfig":
        if self.provider in PROVIDERS and self.model not in PROVIDERS[self.provider]["models"]:
            raise ValidationError.from_exception_data("AiConfig", [{
                "type": "value_error", "loc": ("model",), "input": self.model,
                "ctx": {"error": ValueError("El modelo no pertenece al proveedor")},
            }])
        return self


_MESSAGES = {
    "missing": "Campo obligatorio",
    "extra_forbidden": "Campo no admitido",
    "string_type": "Debe ser un texto",
    "bool_type": "Debe ser verdadero o falso",
    "bool_parsing": "Debe ser verdadero o falso",
    "int_type": "Debe ser un número entero",
    "int_parsing": "Debe ser un número entero",
    "float_type": "Debe ser un número",
    "float_parsing": "Debe ser un número",
    "list_type": "Debe ser una lista",
    "dict_type": "Debe ser un objeto",
    "model_type": "Debe ser un objeto",
}


def _message(err: dict) -> str:
    ctx = err.get("ctx") or {}
    match err["type"]:
        case "value_error":
            return str(ctx.get("error", err["msg"]))
        case "string_too_short":
            return "No puede estar vacío" if ctx.get("min_length") == 1 else f"Mínimo {ctx['min_length']} caracteres"
        case "string_too_long":
            return f"Máximo {ctx['max_length']} caracteres"
        case "too_short":
            return f"Mínimo {ctx['min_length']} elementos"
        case "too_long":
            return f"Máximo {ctx['max_length']} elementos"
        case "greater_than_equal":
            return f"Debe ser mayor o igual que {ctx['ge']}"
        case "less_than_equal":
            return f"Debe ser menor o igual que {ctx['le']}"
        case "string_pattern_mismatch":
            return "Formato no válido"
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
