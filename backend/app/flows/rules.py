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
from app.flows.fields import topic_code
from app.flows.model import Graph, OutputNode, PromptNode, SamplingNode
from app.query.model import QueryError, parse_query

VARIABLE = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")
# Variables que salen del análisis de la plataforma: vacías con conversaciones reales sin analizar (FE012).
PENDING_VARIABLES = {"summary", "main_topic"}
FIELD_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# Proveedores con clave configurada según el servicio de LLM, o `None` si no responde (FE013). Se consulta una vez por
# validación y solo si algún Prompt usa un proveedor real.
LlmKeys = Callable[[], dict[str, bool] | None]


def active_origin() -> str:
    return get_config().sources.origin


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
        if pending and active_origin() == "real":
            issues.append(Issue(
                "analysis_pending",
                f"Las conversaciones reales aún no tienen análisis: {', '.join('{{' + v + '}}' for v in pending)} "
                "llegará vacía al prompt.", node.id, "warning"))
        chained = any(isinstance(graph.node(source), PromptNode) for source in graph.inputs(node.id))
        if catalog.PREVIOUS_RESULT in used and not chained:
            issues.append(Issue("previous_result_without_chain",
                                "{{resultado_anterior}} solo está disponible en un prompt conectado a otro prompt.", node.id))
    return issues + _provider(node, llm_keys) + _output_format(node)


def _mapping(node: OutputNode, mapping, prompt: PromptNode) -> list[Issue]:
    """Una asignación de un Output `campo` frente al formato del Prompt de entrada (FE013, criterio 17)."""
    fmt = prompt.config.output
    label = catalog.target_label(mapping.target, get_config().checks)
    if fmt.type == "json":
        field = next((f for f in fmt.fields or [] if f.name == mapping.source), None)
        if field is None or field.type != "texto":
            return [Issue("invalid_mapping", f"{label}: elige un campo de texto del JSON del Prompt.", node.id)]
        free_text, values = field.options is None, field.options
    else:
        if mapping.source is not None:
            return [Issue("invalid_mapping", f"{label}: el Prompt no devuelve JSON, así que no hay campo de origen.",
                          node.id)]
        free_text, values = fmt.type == "texto", fmt.labels if fmt.type == "etiqueta" else None
    if mapping.target == "summary" and not free_text:
        return [Issue("summary_requires_text", "Summary necesita texto libre: un Prompt de texto o un campo de "
                                               "texto sin valores permitidos.", node.id)]
    if mapping.target == "main_topic":
        unknown = [v for v in values or [] if topic_code(v) is None]
        if not values or unknown:
            detail = f" No lo son: {', '.join(unknown)}." if unknown else ""
            return [Issue("main_topic_requires_taxonomy", "Main topic necesita etiquetas o valores permitidos que sean "
                                                          f"main topics activos de la taxonomía.{detail}", node.id)]
    return []


def _fields_output(node: OutputNode, graph: Graph) -> list[Issue]:
    cfg = node.config
    if not cfg.mappings:
        return [Issue("node_unconfigured", "Sin configurar: falta al menos un campo destino.", node.id)]
    issues = []
    if active_origin() != "real":
        issues.append(Issue("field_output_requires_real_data", "Guardar en campos solo funciona con datos reales.",
                            node.id))
    targets = [m.target for m in cfg.mappings]
    if len(set(targets)) != len(targets):
        issues.append(Issue("duplicate_target", "Un campo destino solo puede aparecer una vez.", node.id))
    prompt = next((graph.node(s) for s in graph.inputs(node.id) if isinstance(graph.node(s), PromptNode)), None)
    if prompt is None or prompt.config.output is None:
        return issues
    if (prompt.config.provider or catalog.SIMULATED) == catalog.SIMULATED:
        issues.append(Issue("simulated_values_to_real_data",
                            "El Prompt usa el proveedor Simulado: se guardarán resultados simulados en conversaciones "
                            "reales.", node.id, "warning"))
    if prompt.config.output.type != "json" and len(cfg.mappings) > 1:
        issues.append(Issue("invalid_mapping", "Un Prompt de texto o etiqueta solo da un valor: usa una sola "
                                               "asignación, o un Prompt JSON para varios campos.", node.id))
        return issues
    for mapping in cfg.mappings:
        issues += _mapping(node, mapping, prompt)
    return issues


def _output(node: OutputNode, graph: Graph) -> list[Issue]:
    cfg = node.config
    if cfg.kind == "campo":
        return _fields_output(node, graph)
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
    targets: set[str] = set()
    for node in graph.nodes:
        if isinstance(node, SamplingNode):
            issues += _sampling(node)
        elif isinstance(node, PromptNode):
            issues += _prompt(node, graph, llm_keys)
        else:
            issues += _output(node, graph)
            if node.config.kind == "campo":
                own = {m.target for m in node.config.mappings or []}
                if own & targets:
                    names = ", ".join(catalog.target_label(t, get_config().checks) for t in sorted(own & targets))
                    issues.append(Issue("duplicate_target", f"Otro Output ya guarda en: {names}.", node.id))
                targets |= own
            else:
                destination = _normalized(node.config.destination or "")
                if destination and destination in destinations:
                    issues.append(Issue("duplicate_destination",
                                        f"Ya hay otro Output con el destino «{node.config.destination.strip()}».",
                                        node.id))
                destinations.add(destination)
        loose = _disconnected(node, graph)
        if loose:
            issues.append(loose)
    return issues
