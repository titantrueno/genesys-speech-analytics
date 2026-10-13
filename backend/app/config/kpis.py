"""KPIs y objetivos (FE005, criterio 8): objetivo, umbrales verde/ámbar y dashboards donde se muestra cada KPI.

El sentido del KPI es fijo (`higher_is_better` de `KPI_DEFS`) y los umbrales deben ser coherentes con él: si más es
mejor, verde > ámbar; si más es peor, verde < ámbar. Un valor igual a un umbral toma el color mejor.
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import Field, ValidationError

from app.config.model import Section

if TYPE_CHECKING:
    from app.services.kpis import KpiDef

# Dashboards predefinidos del front (frontend/src/dashboards/definitions.tsx).
DASHBOARDS = {
    "vision-general": "Visión general",
    "calidad-y-cumplimiento": "Calidad y cumplimiento",
    "experiencia-de-cliente": "Experiencia de cliente",
}
DashboardSlug = Literal[tuple(DASHBOARDS)]  # type: ignore[valid-type]

# Rango admitido por unidad (objetivo y umbrales).
UNIT_RANGES = {"%": (0, 100), "1-5": (1, 5), "índice": (-1, 1), "s": (0, 86_400),
               "conversaciones": (0, 1_000_000), "turnos": (0, 1_000)}

# Estado inicial: tarjetas de cada dashboard en FE001 y umbrales elegidos con los valores reales de los últimos 30 días,
# para que de entrada haya tarjetas verdes, ámbar y rojas. Volumen y turnos no tienen un valor «bueno»: sin umbrales.
_DEFAULTS: dict[str, tuple[float | None, float | None, list[str]]] = {
    "volume": (None, None, ["vision-general"]),
    "aht_s": (240, 300, ["vision-general", "calidad-y-cumplimiento"]),
    "sentiment_avg": (0.1, 0, ["experiencia-de-cliente"]),
    "negative_pct": (20, 30, ["experiencia-de-cliente"]),
    "resolution_rate": (75, 60, ["vision-general", "calidad-y-cumplimiento"]),
    "escalation_rate": (12, 18, ["vision-general", "calidad-y-cumplimiento"]),
    "fcr_rate": (80, 70, ["vision-general"]),
    "csat_avg": (4, 3.5, ["vision-general", "experiencia-de-cliente"]),
    "effort_avg": (2.5, 3, ["experiencia-de-cliente"]),
    "compliance_rate": (80, 70, ["calidad-y-cumplimiento"]),
    "churn_high_pct": (15, 25, ["experiencia-de-cliente"]),
    "first_response_s": (60, 120, ["experiencia-de-cliente"]),
    "avg_turns": (None, None, ["calidad-y-cumplimiento"]),
}


class KpiTargetIn(Section):
    target: float | None = Field(None, allow_inf_nan=False)
    green: float | None = Field(None, allow_inf_nan=False)
    amber: float | None = Field(None, allow_inf_nan=False)
    dashboards: list[DashboardSlug] = Field(default_factory=list)  # type: ignore[valid-type]

    def validate_for(self, kpi: "KpiDef") -> "KpiTargetIn":
        """Reglas que dependen del KPI: rango de su unidad, umbrales completos y coherentes con su sentido."""
        low, high = UNIT_RANGES[kpi.unit]
        errors = []

        def error(field: str, message: str) -> None:
            errors.append({"type": "value_error", "loc": (field,), "input": getattr(self, field),
                           "ctx": {"error": ValueError(message)}})

        for name in ("target", "green", "amber"):
            value = getattr(self, name)
            if value is not None and not low <= value <= high:
                error(name, f"Must be between {low:g} and {high:g}")
        if (self.green is None) != (self.amber is None):
            error("amber" if self.amber is None else "green", "Provide both thresholds or neither")
        elif self.green is not None and not errors:
            coherent = self.green > self.amber if kpi.higher_is_better else self.green < self.amber
            if not coherent:
                error("amber", "Must be lower than the green threshold (more is better)" if kpi.higher_is_better
                      else "Must be higher than the green threshold (more is worse)")
        if len(set(self.dashboards)) != len(self.dashboards):
            error("dashboards", "There are repeated dashboards")
        if errors:
            raise ValidationError.from_exception_data("KpiTargetIn", errors)
        return self


@dataclass(frozen=True)
class KpiTarget:
    target: float | None
    green: float | None
    amber: float | None
    dashboards: tuple[str, ...]

    def status(self, value: float | None, higher_is_better: bool) -> str | None:
        if value is None or self.green is None or self.amber is None:
            return None
        if higher_is_better:
            return "verde" if value >= self.green else "ambar" if value >= self.amber else "rojo"
        return "verde" if value <= self.green else "ambar" if value <= self.amber else "rojo"

    def to_dict(self) -> dict:
        return {"target": self.target, "green": self.green, "amber": self.amber, "dashboards": list(self.dashboards)}


def initial_kpis() -> dict[str, KpiTarget]:
    return {code: KpiTarget(green, green, amber, tuple(dashboards))
            for code, (green, amber, dashboards) in _DEFAULTS.items()}

