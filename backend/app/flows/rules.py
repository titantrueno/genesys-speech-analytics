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
from app.flows.fields import accepts_option, topic_code
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
        ("filters", cfg.query is not None),
        ("method", cfg.method is not None),
        ("sample size", cfg.size is not None),
        ("stratification criterion", cfg.method != "estratificado" or cfg.stratify_by is not None),
        ("order criterion", cfg.method != "primeros_n" or cfg.order_by is not None),
        ("order direction", cfg.method != "primeros_n" or cfg.order is not None),
    ])
    issues = [Issue("node_unconfigured", f"Not configured: missing {', '.join(missing)}.", node.id)] if missing else []
    if cfg.query is not None:
        try:
            parse_query(copy.deepcopy(cfg.query))
        except QueryError as exc:
            detail = "; ".join(e["message"] for e in exc.errors)
            issues.append(Issue("invalid_config", f"The Sampling filters are not valid: {detail}", node.id))
    return issues


def _output_format(node: PromptNode) -> list[Issue]:
    fmt = node.config.output
    if fmt is None or fmt.type == "texto":
        return []
    if fmt.type == "etiqueta":
        labels = [_normalized(label) for label in fmt.labels or []]
        if len(labels) < 2 or "" in labels or len(set(labels)) != len(labels):
            return [Issue("invalid_config", "The \"etiqueta\" format needs at least 2 distinct, non-empty labels.", node.id)]
        return []
    names = [f.name for f in fmt.fields or []]
    if not names:
        return [Issue("invalid_config", "The JSON schema needs at least one field.", node.id)]
    invalid = [n for n in names if not FIELD_NAME.match(n)]
    if invalid:
        return [Issue("invalid_config", f"Invalid field name: {', '.join(invalid)} (letters, numbers and _, not starting with a number).", node.id)]
    if len({n.casefold() for n in names}) != len(names):
        return [Issue("invalid_config", "The JSON schema has repeated fields.", node.id)]
    return []


def _provider(node: PromptNode, llm_keys: LlmKeys | None) -> list[Issue]:
    cfg = node.config
    provider = cfg.provider or catalog.SIMULATED
    spec = catalog.PROVIDERS[provider]
    if cfg.model is not None and cfg.model not in spec["models"]:
        return [Issue("model_not_in_provider",
                      f"The model {catalog.MODELS[cfg.model]} does not belong to the provider {spec['label']}.", node.id)]
    if provider == catalog.SIMULATED or llm_keys is None:
        return []
    keys = llm_keys()
    if keys is None:
        return [Issue("llm_unavailable",
                      f"The LLM service is not available: cannot run with {spec['label']}.", node.id)]
    if not keys.get(provider):
        return [Issue("provider_without_key", f"The provider {spec['label']} has no key configured.", node.id)]
    return []


def _prompt(node: PromptNode, graph: Graph, llm_keys: LlmKeys | None = None) -> list[Issue]:
    cfg = node.config
    template = (cfg.template or "").strip()
    missing = _missing([("template", bool(template)), ("model", cfg.model is not None),
                        ("temperature", cfg.temperature is not None), ("output format", cfg.output is not None)])
    issues = [Issue("node_unconfigured", f"Not configured: missing {', '.join(missing)}.", node.id)] if missing else []
    if template:
        used = template_variables(template)
        unknown = sorted({v for v in used if v not in catalog.VARIABLES})
        if unknown:
            issues.append(Issue("unknown_variable", f"Unknown variable: {', '.join('{{' + v + '}}' for v in unknown)}.", node.id))
        if not any(v in catalog.VARIABLES for v in used):
            issues.append(Issue("prompt_without_variables",
                                "The prompt uses no variable: all conversations would receive the same text.", node.id))
        pending = sorted({v for v in used if v in PENDING_VARIABLES})
        if pending and active_origin() == "real":
            issues.append(Issue(
                "analysis_pending",
                f"The real conversations do not have analysis yet: {', '.join('{{' + v + '}}' for v in pending)} "
                "will reach the prompt empty.", node.id, "warning"))
        chained = any(isinstance(graph.node(source), PromptNode) for source in graph.inputs(node.id))
        if catalog.PREVIOUS_RESULT in used and not chained:
            issues.append(Issue("previous_result_without_chain",
                                "{{resultado_anterior}} is only available in a prompt connected to another prompt.", node.id))
    return issues + _provider(node, llm_keys) + _output_format(node)


# Qué campo del JSON necesita cada destino del análisis completo (FE014, criterio 6): tipo, si exige valores permitidos
# y cómo se dice en el mensaje. Summary y main topic siguen con sus reglas de FE013.
_CHECK_RULE = ("texto", True, "a text field with allowed values cumple, no_cumple and no_aplica")
_TARGET_RULES = {
    "resolution": ("texto", True, "a text field with allowed values resuelta, no_resuelta and escalada"),
    "churn_risk": ("texto", True, "a text field with allowed values bajo, medio and alto"),
    "csat": ("numero", False, "a numeric field"),
    "effort": ("numero", False, "a numeric field"),
    "sentiment": ("numero", False, "a numeric field"),
    "secondary_topics": ("lista", True, "a list with allowed values that are active secondary topics"),
    "keywords": ("lista", False, "a list"),
}
_ENTITY_RULE = ("texto", False, "a text field")


def _target_rule(target: str) -> tuple[str, bool, str]:
    if catalog.check_code(target):
        return _CHECK_RULE
    if target.startswith(catalog.ENTITY_PREFIX):
        return _ENTITY_RULE
    return _TARGET_RULES[target]


def _analysis_mapping(node: OutputNode, mapping, fmt, label: str) -> list[Issue]:
    field_type, needs_options, wanted = _target_rule(mapping.target)
    if fmt.type != "json":
        return [Issue("invalid_mapping", f"{label}: a text or label Prompt can only save Summary or Main "
                                         "topic; use a JSON Prompt.", node.id)]
    field = next((f for f in fmt.fields or [] if f.name == mapping.source), None)
    unknown = [o for o in (field.options or []) if not accepts_option(mapping.target, o)] if field else []
    if field is None or field.type != field_type or (needs_options and not field.options) or unknown:
        detail = f" Not allowed: {', '.join(unknown)}." if unknown else ""
        return [Issue("invalid_mapping", f"{label}: choose {wanted} from the Prompt JSON.{detail}", node.id)]
    return []


def _mapping(node: OutputNode, mapping, prompt: PromptNode) -> list[Issue]:
    """Una asignación de un Output `campo` frente al formato del Prompt de entrada (FE013, criterio 17)."""
    fmt = prompt.config.output
    label = catalog.target_label(mapping.target, get_config().checks)
    if mapping.target not in ("summary", "main_topic"):
        return _analysis_mapping(node, mapping, fmt, label)
    if fmt.type == "json":
        field = next((f for f in fmt.fields or [] if f.name == mapping.source), None)
        if field is None or field.type != "texto":
            return [Issue("invalid_mapping", f"{label}: choose a text field from the Prompt JSON.", node.id)]
        free_text, values = field.options is None, field.options
    else:
        if mapping.source is not None:
            return [Issue("invalid_mapping", f"{label}: the Prompt does not return JSON, so there is no source field.",
                          node.id)]
        free_text, values = fmt.type == "texto", fmt.labels if fmt.type == "etiqueta" else None
    if mapping.target == "summary" and not free_text:
        return [Issue("summary_requires_text", "Summary needs free text: a text Prompt or a text field "
                                               "with no allowed values.", node.id)]
    if mapping.target == "main_topic":
        unknown = [v for v in values or [] if topic_code(v) is None]
        if not values or unknown:
            detail = f" Not allowed: {', '.join(unknown)}." if unknown else ""
            return [Issue("main_topic_requires_taxonomy", "Main topic needs labels or allowed values that are "
                                                          f"active main topics of the taxonomy.{detail}", node.id)]
    return []


def _unknown_checks(node: OutputNode) -> set[str]:
    """Checks asignados que ya no existen o están desactivados (FE014, criterio 7)."""
    checks = get_config().checks
    codes = {catalog.check_code(m.target) for m in node.config.mappings or []} - {None}
    return {code for code in codes if code not in checks or not checks[code].active}


def _fields_output(node: OutputNode, graph: Graph) -> list[Issue]:
    cfg = node.config
    if not cfg.mappings:
        return [Issue("node_unconfigured", "Not configured: at least one target field is missing.", node.id)]
    issues = []
    if active_origin() != "real":
        issues.append(Issue("field_output_requires_real_data", "Saving to fields only works with real data.",
                            node.id))
    targets = [m.target for m in cfg.mappings]
    if len(set(targets)) != len(targets):
        issues.append(Issue("duplicate_target", "A target field can only appear once.", node.id))
    unknown = _unknown_checks(node)
    issues += [Issue("unknown_check", f"The check “{code}” does not exist or is disabled: remove its mapping.", node.id)
               for code in sorted(unknown)]
    prompt = next((graph.node(s) for s in graph.inputs(node.id) if isinstance(graph.node(s), PromptNode)), None)
    if prompt is None or prompt.config.output is None:
        return issues
    if (prompt.config.provider or catalog.SIMULATED) == catalog.SIMULATED:
        issues.append(Issue("simulated_values_to_real_data",
                            "The Prompt uses the Simulated provider: simulated results will be saved in real "
                            "conversations.", node.id, "warning"))
    if prompt.config.output.type != "json" and len(cfg.mappings) > 1:
        issues.append(Issue("invalid_mapping", "A text or label Prompt gives a single value: use a single "
                                               "mapping, or a JSON Prompt for several fields.", node.id))
        return issues
    for mapping in cfg.mappings:
        if catalog.check_code(mapping.target) not in unknown:
            issues += _mapping(node, mapping, prompt)
    return issues


def _output(node: OutputNode, graph: Graph) -> list[Issue]:
    cfg = node.config
    if cfg.kind == "campo":
        return _fields_output(node, graph)
    missing = _missing([("type", cfg.kind is not None), ("destination name", bool((cfg.destination or "").strip())),
                        ("aggregation", cfg.kind != "metrica" or cfg.aggregation is not None)])
    issues = [Issue("node_unconfigured", f"Not configured: missing {', '.join(missing)}.", node.id)] if missing else []
    if cfg.kind == "metrica":
        for source in graph.inputs(node.id):
            prompt = graph.node(source)
            fmt = prompt.config.output if isinstance(prompt, PromptNode) else None
            if fmt is not None and fmt.type != "etiqueta":
                issues.append(Issue("metric_requires_labels",
                                    "An aggregated metric needs a prompt with the \"etiqueta\" format.", node.id))
    return issues


def _disconnected(node, graph: Graph) -> Issue | None:
    has_input, has_output = bool(graph.inputs(node.id)), bool(graph.outputs(node.id))
    loose = {"sampling": not has_output, "prompt": not (has_input and has_output), "output": not has_input}[node.type]
    if not loose:
        return None
    needs = {"sampling": "connect it to a Prompt", "prompt": "it needs one input and at least one output",
             "output": "connect a Prompt to it"}[node.type]
    return Issue("disconnected_node", f"Loose node: {needs}.", node.id)


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
        issues.append(Issue("missing_sampling", "The flow needs a Sampling node."))
    if "output" not in types:
        issues.append(Issue("missing_output", "The flow needs at least one Output node."))
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
                    issues.append(Issue("duplicate_target", f"Another Output already saves to: {names}.", node.id))
                targets |= own
            else:
                destination = _normalized(node.config.destination or "")
                if destination and destination in destinations:
                    issues.append(Issue("duplicate_destination",
                                        f"There is already another Output with the destination “{node.config.destination.strip()}”.",
                                        node.id))
                destinations.add(destination)
        loose = _disconnected(node, graph)
        if loose:
            issues.append(loose)
    return issues
