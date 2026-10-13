"""Formato JSON de un flujo de insights e integridad del grafo (FE004, criterios 2 y 3).

La integridad se exige siempre al guardar: un borrador puede estar incompleto (la completitud la comprueba
`app/flows/rules.validate`), pero nunca tener tipos, rangos o conexiones imposibles.
"""
import re
from typing import Annotated, Any, Literal, Union

from pydantic import (BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, ValidationError, field_validator,
                      model_validator)

from app import ids
from app.flows import catalog
from app.flows.connections import connection_rejection

TEMPORARY_ID = re.compile(r"^tmp-[A-Za-z0-9_-]{1,40}$")

NodeType = Literal["sampling", "prompt", "output"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Position(_Strict):
    x: float
    y: float


class SamplingConfig(_Strict):
    query: dict[str, Any] | None = None
    method: Literal[tuple(catalog.SAMPLING_METHODS)] | None = None
    stratify_by: Literal[tuple(catalog.STRATA)] | None = None
    order_by: Literal[tuple(catalog.ORDER_KEYS)] | None = None
    order: Literal[tuple(catalog.ORDERS)] | None = None
    size: int | None = Field(None, ge=1, le=catalog.MAX_SAMPLE_SIZE)


Label = Annotated[str, StringConstraints(max_length=catalog.MAX_LABEL)]


class SchemaField(_Strict):
    name: str = Field(max_length=catalog.MAX_FIELD_NAME)
    type: Literal[tuple(catalog.FIELD_TYPES)]
    # Valores permitidos de un campo de texto (FE013) o de cada elemento de una lista (FE014): el LLM los recibe como
    # `enum` y otro valor se rechaza.
    options: list[Label] | None = Field(None, max_length=catalog.MAX_OPTIONS)

    @model_validator(mode="after")
    def _options_only_for_text(self) -> "SchemaField":
        if self.options is not None and self.type not in ("texto", "lista"):
            raise ValueError("Solo un campo de texto o de lista puede tener valores permitidos")
        return self


class OutputFormat(_Strict):
    type: Literal[tuple(catalog.OUTPUT_FORMATS)]
    labels: list[Label] | None = Field(None, max_length=catalog.MAX_LABELS)
    fields: list[SchemaField] | None = Field(None, max_length=catalog.MAX_FIELDS)


class PromptConfig(_Strict):
    template: str | None = Field(None, max_length=catalog.MAX_TEMPLATE)
    # Sin proveedor, el nodo es simulado: así se leen los flujos guardados antes de FE013.
    provider: Literal[tuple(catalog.PROVIDERS)] | None = None
    model: Literal[tuple(catalog.MODELS)] | None = None
    temperature: float | None = Field(None, ge=0, le=1)
    output: OutputFormat | None = None


class FieldMapping(_Strict):
    """Un campo destino y de dónde sale: la respuesta entera (`None`) o un campo del JSON del Prompt (FE013)."""
    target: str = Field(max_length=catalog.MAX_FIELD_NAME + len(catalog.CHECK_PREFIX))
    source: str | None = Field(None, max_length=catalog.MAX_FIELD_NAME)

    @field_validator("target")
    @classmethod
    def _known_target(cls, target: str) -> str:
        if not catalog.is_target(target):
            raise ValueError(f"Campo destino desconocido: {target!r}")
        return target


class OutputConfig(_Strict):
    kind: Literal[tuple(catalog.OUTPUT_KINDS)] | None = None
    aggregation: Literal[tuple(catalog.AGGREGATIONS)] | None = None
    destination: str | None = Field(None, max_length=catalog.MAX_DESTINATION)
    # Solo en `campo` (FE013): asignaciones y si se sustituyen los valores que ya tiene la conversación.
    mappings: list[FieldMapping] | None = Field(None, max_length=catalog.MAX_MAPPINGS)
    overwrite: bool | None = None


class _Node(_Strict):
    id: str
    position: Position


class SamplingNode(_Node):
    type: Literal["sampling"]
    config: SamplingConfig = SamplingConfig()


class PromptNode(_Node):
    type: Literal["prompt"]
    config: PromptConfig = PromptConfig()


class OutputNode(_Node):
    type: Literal["output"]
    config: OutputConfig = OutputConfig()


Node = Annotated[Union[SamplingNode, PromptNode, OutputNode], Field(discriminator="type")]
_node_adapter = TypeAdapter(Node)


class Edge(_Strict):
    source: str
    target: str


class Graph(_Strict):
    version: Literal[1] = 1
    nodes: list[Node] = []
    edges: list[Edge] = []

    def dump(self) -> dict:
        return self.model_dump(mode="json", exclude_none=True)

    def node(self, node_id: str) -> SamplingNode | PromptNode | OutputNode | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    def inputs(self, node_id: str) -> list[str]:
        return [e.source for e in self.edges if e.target == node_id]

    def outputs(self, node_id: str) -> list[str]:
        return [e.target for e in self.edges if e.source == node_id]


class _Envelope(_Strict):
    version: Literal[1] = 1
    nodes: list[dict[str, Any]] = Field([], max_length=catalog.MAX_NODES)
    edges: list[Edge] = Field([], max_length=catalog.MAX_EDGES)


class GraphError(Exception):
    def __init__(self, errors: list[dict]):
        super().__init__("grafo no válido")
        self.errors = errors


def is_node_id(value: str) -> bool:
    return ids.is_valid(value, ids.NODE) or bool(TEMPORARY_ID.match(value))


def _path(prefix: str, loc: tuple, skip_tag: bool) -> str:
    path = prefix
    for i, part in enumerate(loc):
        if skip_tag and i == 0 and part in catalog.NODE_TYPES:
            continue
        path += f"[{part}]" if isinstance(part, int) else (f".{part}" if path else str(part))
    return path


def _pydantic_errors(exc: ValidationError, prefix: str = "", node_id: str | None = None, skip_tag: bool = False) -> list[dict]:
    return [{"path": _path(prefix, tuple(err["loc"]), skip_tag), "node_id": node_id, "message": err["msg"]}
            for err in exc.errors()]


def parse_graph(payload: Any) -> Graph:
    """Valida la integridad del grafo y devuelve **todos** los errores con su ruta (`nodes[1].config.size`, `edges[0]`)."""
    try:
        envelope = _Envelope.model_validate(payload)
    except ValidationError as exc:
        raise GraphError(_pydantic_errors(exc)) from None

    errors: list[dict] = []
    nodes, types, seen = [], {}, set()
    for i, raw in enumerate(envelope.nodes):
        raw_id = raw.get("id") if isinstance(raw.get("id"), str) else None
        try:
            parsed = _node_adapter.validate_python(raw)
        except ValidationError as exc:
            errors += _pydantic_errors(exc, f"nodes[{i}]", raw_id, skip_tag=True)
            parsed = None
        if raw_id is None:
            continue
        if not is_node_id(raw_id):
            errors.append({"path": f"nodes[{i}].id", "node_id": raw_id,
                           "message": f"Identificador de nodo no válido: {raw_id!r} (se espera {ids.NODE}-UUID o tmp-…)"})
        elif raw_id in seen:
            errors.append({"path": f"nodes[{i}].id", "node_id": raw_id, "message": f"Identificador de nodo repetido: {raw_id}"})
        seen.add(raw_id)
        if isinstance(raw.get("type"), str) and raw["type"] in catalog.NODE_TYPES:
            types.setdefault(raw_id, raw["type"])
        if parsed is not None:
            nodes.append(parsed)

    accepted: list[tuple[str, str]] = []
    for j, edge in enumerate(envelope.edges):
        rejection = connection_rejection(types, accepted, edge.source, edge.target)
        if rejection:
            errors.append({"path": f"edges[{j}]", "node_id": edge.target if edge.target in types else None,
                           "message": f"{edge.source} → {edge.target}: {rejection.message}"})
        else:
            accepted.append((edge.source, edge.target))

    if errors:
        raise GraphError(errors)
    return Graph(version=envelope.version, nodes=nodes, edges=envelope.edges)
