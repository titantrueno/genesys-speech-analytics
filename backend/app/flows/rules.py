"""Conexiones y validación de completitud de un flujo (FE004, criterios 2 y 4).

`validate` no bloquea el guardado: bloquea la ejecución y alimenta el botón «Validar» del editor.
"""
import copy
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass

from app.flows import catalog
from app.flows.connections import Rejection, connection_rejection
from app.config.store import get_config
from app.flows.model import Graph, OutputNode, PromptNode, SamplingNode
from app.query.model import QueryError, parse_query

VARIABLE = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")
# Variables que salen del análisis de la plataforma: vacías con conversaciones reales sin analizar (FE012).
PENDING_VARIABLES = {"summary", "main_topic"}
FIELD_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# Proveedores con clave configurada según el servicio de LLM, o `None` si no responde (FE013). Se consulta una vez por
# validación y solo si algún Prompt usa un proveedor real.
LlmKeys = Callable[[], dict[str, bool] | None]


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    node_id: str | None = None
    # `warning` avisa sin bloquear la ejecución (FE012); `error` la bloquea.
    severity: str = "error"

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.severity == "error":  # el formato de FE004 no cambia: `severity` solo aparece en los avisos
            del data["severity"]
        return data


def blocking(issues: list[Issue]) -> list[Issue]:
    return [issue for issue in issues if issue.severity == "error"]


def can_connect(graph: Graph, source: str, target: str) -> Rejection | None:
    types = {n.id: n.type for n in graph.nodes}
    return connection_rejection(types, [(e.source, e.target) for e in graph.edges], source, target)


def template_variables(template: str) -> list[str]:
    return VARIABLE.findall(template)


def _normalized(text: str) -> str:
    return text.strip().casefold()


def _missing(pairs: list[tuple[str, bool]]) -> list[str]:
    return [label for label, present in pairs if not present]


def _sampling(node: SamplingNode) -> list[Issue]:
    cfg = node.config
    missing = _missing([
        ("filtros", cfg.query is not None),
        ("método", cfg.method is not None),
        ("tamaño de muestra", cfg.size is not None),
        ("criterio de estratificación", cfg.method != "estratificado" or cfg.stratify_by is not None),
        ("criterio de orden", cfg.method != "primeros_n" or cfg.order_by is not None),
        ("sentido del orden", cfg.method != "primeros_n" or cfg.order is not None),
    ])
    issues = [Issue("node_unconfigured", f"Sin configurar: falta {', '.join(missing)}.", node.id)] if missing else []
    if cfg.query is not None:
        try:
            parse_query(copy.deepcopy(cfg.query))
        except QueryError as exc:
            detail = "; ".join(e["message"] for e in exc.errors)
            issues.append(Issue("invalid_config", f"Los filtros del Sampling no son válidos: {detail}", node.id))
    return issues


def _output_format(node: PromptNode) -> list[Issue]:
    fmt = node.config.output
    if fmt is None or fmt.type == "texto":
        return []
    if fmt.type == "etiqueta":
        labels = [_normalized(label) for label in fmt.labels or []]
        if len(labels) < 2 or "" in labels or len(set(labels)) != len(labels):
            return [Issue("invalid_config", "El formato «etiqueta» necesita al menos 2 etiquetas distintas y no vacías.", node.id)]
        return []
    names = [f.name for f in fmt.fields or []]
    if not names:
        return [Issue("invalid_config", "El esquema JSON necesita al menos un campo.", node.id)]
    invalid = [n for n in names if not FIELD_NAME.match(n)]
    if invalid:
        return [Issue("invalid_config", f"Nombre de campo no válido: {', '.join(invalid)} (letras, números y _, sin empezar por número).", node.id)]
    if len({n.casefold() for n in names}) != len(names):
        return [Issue("invalid_config", "El esquema JSON tiene campos repetidos.", node.id)]
    return []


def _provider(node: PromptNode, llm_keys: LlmKeys | None) -> list[Issue]:
    cfg = node.config
    provider = cfg.provider or catalog.SIMULATED
    spec = catalog.PROVIDERS[provider]
    if cfg.model is not None and cfg.model not in spec["models"]:
        return [Issue("model_not_in_provider",
                      f"El modelo {catalog.MODELS[cfg.model]} no pertenece al proveedor {spec['label']}.", node.id)]
    if provider == catalog.SIMULATED or llm_keys is None:
        return []
    keys = llm_keys()
    if keys is None:
        return [Issue("llm_unavailable",
                      f"El servicio de LLM no está disponible: no se puede ejecutar con {spec['label']}.", node.id)]
    if not keys.get(provider):
        return [Issue("provider_without_key", f"El proveedor {spec['label']} no tiene clave configurada.", node.id)]
    return []


def _prompt(node: PromptNode, graph: Graph, llm_keys: LlmKeys | None = None) -> list[Issue]:
    cfg = node.config
    template = (cfg.template or "").strip()
    missing = _missing([("plantilla", bool(template)), ("modelo", cfg.model is not None),
                        ("temperatura", cfg.temperature is not None), ("formato de salida", cfg.output is not None)])
    issues = [Issue("node_unconfigured", f"Sin configurar: falta {', '.join(missing)}.", node.id)] if missing else []
    if template:
        used = template_variables(template)
        unknown = sorted({v for v in used if v not in catalog.VARIABLES})
        if unknown:
            issues.append(Issue("unknown_variable", f"Variable desconocida: {', '.join('{{' + v + '}}' for v in unknown)}.", node.id))
        if not any(v in catalog.VARIABLES for v in used):
            issues.append(Issue("prompt_without_variables",
                                "El prompt no usa ninguna variable: todas las conversaciones recibirían el mismo texto.", node.id))
        pending = sorted({v for v in used if v in PENDING_VARIABLES})
        if pending and get_config().sources.origin == "real":
            issues.append(Issue(
                "analysis_pending",
                f"Las conversaciones reales aún no tienen análisis: {', '.join('{{' + v + '}}' for v in pending)} "
                "llegará vacía al prompt.", node.id, "warning"))
        chained = any(isinstance(graph.node(source), PromptNode) for source in graph.inputs(node.id))
        if catalog.PREVIOUS_RESULT in used and not chained:
            issues.append(Issue("previous_result_without_chain",
                                "{{resultado_anterior}} solo está disponible en un prompt conectado a otro prompt.", node.id))
    return issues + _provider(node, llm_keys) + _output_format(node)


def _output(node: OutputNode, graph: Graph) -> list[Issue]:
    cfg = node.config
    missing = _missing([("tipo", cfg.kind is not None), ("nombre de destino", bool((cfg.destination or "").strip())),
                        ("agregación", cfg.kind != "metrica" or cfg.aggregation is not None)])
    issues = [Issue("node_unconfigured", f"Sin configurar: falta {', '.join(missing)}.", node.id)] if missing else []
    if cfg.kind == "metrica":
        for source in graph.inputs(node.id):
            prompt = graph.node(source)
            fmt = prompt.config.output if isinstance(prompt, PromptNode) else None
            if fmt is not None and fmt.type != "etiqueta":
                issues.append(Issue("metric_requires_labels",
                                    "Una métrica agregada necesita un prompt con formato «etiqueta».", node.id))
    return issues


def _disconnected(node, graph: Graph) -> Issue | None:
    has_input, has_output = bool(graph.inputs(node.id)), bool(graph.outputs(node.id))
    loose = {"sampling": not has_output, "prompt": not (has_input and has_output), "output": not has_input}[node.type]
    if not loose:
        return None
    needs = {"sampling": "conéctalo a un Prompt", "prompt": "necesita una entrada y al menos una salida",
             "output": "conéctale un Prompt"}[node.type]
    return Issue("disconnected_node", f"Nodo suelto: {needs}.", node.id)


def _once(llm_keys: LlmKeys | None) -> LlmKeys | None:
    if llm_keys is None:
        return None
    cached: list = []

    def read() -> dict[str, bool] | None:
        if not cached:
            cached.append(llm_keys())
        return cached[0]
    return read


def validate(graph: Graph, llm_keys: LlmKeys | None = None) -> list[Issue]:
    """Sin `llm_keys` no se comprueban las claves de los proveedores (las reglas siguen siendo puras en los tests)."""
    llm_keys = _once(llm_keys)
    types = [n.type for n in graph.nodes]
    issues: list[Issue] = []
    if "sampling" not in types:
        issues.append(Issue("missing_sampling", "El flujo necesita un nodo Sampling."))
    if "output" not in types:
        issues.append(Issue("missing_output", "El flujo necesita al menos un nodo Output."))
    destinations: set[str] = set()
    for node in graph.nodes:
        if isinstance(node, SamplingNode):
            issues += _sampling(node)
        elif isinstance(node, PromptNode):
            issues += _prompt(node, graph, llm_keys)
        else:
            issues += _output(node, graph)
            destination = _normalized(node.config.destination or "")
            if destination and destination in destinations:
                issues.append(Issue("duplicate_destination",
                                    f"Ya hay otro Output con el destino «{node.config.destination.strip()}».", node.id))
            destinations.add(destination)
        loose = _disconnected(node, graph)
        if loose:
            issues.append(loose)
    return issues
