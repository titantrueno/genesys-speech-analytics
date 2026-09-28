"""Checks de cumplimiento editables (FE005, criterio 9): modelo y estado inicial.

Los seis checks de FE001 (`builtin`) conservan el resultado del análisis mock; sus frases solo documentan qué se espera.
Un check nuevo se evalúa por sus frases en los turnos del agente (ver `app/config/compliance.py`).
"""
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app import ids
from app.config.model import Section
from app.config.taxonomy import Description, Name
from app.data.catalog import COMPLIANCE_CHECKS

MAX_PHRASES = 20
MAX_PHRASE = 120
Channel = Literal["voz", "chat", "ambos"]
Phrase = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_PHRASE)]

# Frases que dice el agente cuando el análisis da el check por cumplido (app/data/generator.py).
BUILTIN_PHRASES = {
    "saludo": ["le atiende", "¿En qué puedo ayudarle?"],
    "verificacion_identidad": ["para verificar su identidad", "identidad verificada"],
    "proteccion_datos": ["política de protección de datos"],
    "no_solicitar_pin": ["nunca le pediremos el PIN ni sus claves completas"],
    "bloqueo_preventivo": ["bloquear preventivamente la tarjeta"],
    "despedida": ["Resumiendo", "¿Puedo ayudarle en algo más?"],
}
BUILTIN_DESCRIPTIONS = {
    "saludo": "El agente saluda y se identifica al empezar.",
    "verificacion_identidad": "Verifica la identidad del cliente antes de dar información.",
    "proteccion_datos": "Informa del tratamiento de los datos personales.",
    "no_solicitar_pin": "No pide el PIN ni claves completas en ningún momento.",
    "bloqueo_preventivo": "Ofrece el bloqueo preventivo en casos de fraude.",
    "despedida": "Se despide resumiendo la gestión realizada.",
}


class CheckIn(Section):
    code: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
    name: Name
    description: Description = ""
    phrases: list[Phrase] = Field(min_length=1, max_length=MAX_PHRASES)
    channel: Channel = "ambos"
    active: bool = True


@dataclass(frozen=True)
class Check:
    id: str
    code: str
    name: str
    description: str
    phrases: tuple[str, ...]
    channel: str
    active: bool
    builtin: bool

    @classmethod
    def from_input(cls, data: CheckIn, builtin: bool) -> "Check":
        return cls(ids.stable_id(ids.CHECK, data.code), data.code, data.name, data.description, tuple(data.phrases),
                   data.channel, data.active, builtin)

    @property
    def evaluation(self) -> str:
        return "analisis" if self.builtin else "frases"

    def applies_to(self, channel: str) -> bool:
        return self.channel in ("ambos", channel)

    def audit_value(self) -> dict:
        return {"code": self.code, "name": self.name, "description": self.description, "phrases": list(self.phrases),
                "channel": self.channel, "active": self.active}

    def to_dict(self) -> dict:
        return {"id": self.id, **self.audit_value(), "evaluation": self.evaluation, "builtin": self.builtin}


def initial_checks() -> dict[str, Check]:
    return {code: Check(ids.stable_id(ids.CHECK, code), code, name, BUILTIN_DESCRIPTIONS[code],
                        tuple(BUILTIN_PHRASES[code]), "ambos", True, True)
            for code, name in COMPLIANCE_CHECKS.items()}
