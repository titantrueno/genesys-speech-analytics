"""Modelo del flujo, integridad del grafo, reglas de conexión y validación (FE004, criterios 2, 3 y 4)."""
import copy
import json
import math
import random
from collections import defaultdict
from pathlib import Path

import pytest

from app import ids
from app.flows.model import GraphError, parse_graph
from app.flows.rules import can_connect, validate
from tests.flow_fixtures import (
    OUTPUT_METRIC, OUTPUT_REPORT, OUTPUT_TABLE, PROMPT_LABEL, PROMPT_TEXT, SAMPLING, chained_graph, complete_graph, days_ago, edge,
    graph, node,
)

CASES = json.loads((Path(__file__).parents[2] / "frontend/src/flows/rules.cases.json").read_text())


def _errors(payload: dict) -> list[dict]:
    with pytest.raises(GraphError) as exc:
        parse_graph(payload)
    return exc.value.errors


def _codes(payload: dict) -> list[tuple[str, str | None]]:
    return [(issue.code, issue.node_id) for issue in validate(parse_graph(payload))]


# --- Reglas de conexión (casos compartidos con el front) ---

@pytest.mark.parametrize("case", CASES["cases"], ids=[c["name"] for c in CASES["cases"]])
def test_connection_rules_match_the_shared_cases(case):
    nodes = [node(n["id"], n["type"]) for n in CASES["nodes"]]
    parsed = parse_graph(graph(nodes, [edge(s, t) for s, t in case["edges"]]))
    rejection = can_connect(parsed, *case["connect"])
    assert (rejection.code if rejection else None) == case["expected"]
    if rejection:
        assert rejection.message


def test_shared_cases_cover_every_rejection_code():
    assert {c["expected"] for c in CASES["cases"]} == {
        None, "invalid_pair", "self_loop", "duplicate", "input_taken", "output_taken", "cycle", "unknown_node"}


# --- Integridad al guardar ---

def test_complete_graph_parses_and_dumps_the_same_json():
    payload = chained_graph()
    parsed = parse_graph(payload)
    assert parsed.dump() == payload


def test_accepts_entity_and_temporary_node_ids():
    node_id = ids.new_id(ids.NODE, random.Random(1))
    parsed = parse_graph(graph([node(node_id, "sampling"), node("tmp-a_1", "prompt")], [edge(node_id, "tmp-a_1")]))
    assert [n.id for n in parsed.nodes] == [node_id, "tmp-a_1"]


def test_incomplete_configuration_is_allowed_when_saving():
    parsed = parse_graph(graph([node("tmp-s", "sampling", {"method": "aleatorio"}), node("tmp-p", "prompt"),
                                node("tmp-o", "output", {"destination": ""})], []))
    assert len(parsed.nodes) == 3


@pytest.mark.parametrize("bad_id", ["abc", "1FL-4B2E9A7F-3D1C-4A9B-8E5D-8F0A6C3E71AB", "tmp-", "tmp-ñ", "tmp-" + "a" * 41, ""])
def test_rejects_node_ids_that_are_neither_nodes_nor_temporary(bad_id):
    errors = _errors(graph([node(bad_id, "sampling")], []))
    assert errors[0]["path"] == "nodes[0].id"


def test_rejects_duplicate_node_ids():
    errors = _errors(graph([node("tmp-a", "sampling"), node("tmp-a", "prompt")], []))
    assert errors == [{"path": "nodes[1].id", "node_id": "tmp-a", "message": "Repeated node identifier: tmp-a"}]


@pytest.mark.parametrize("payload, path", [
    (graph([{"id": "tmp-a", "type": "filtro", "position": {"x": 0, "y": 0}, "config": {}}], []), "nodes[0]"),
    (graph([node("tmp-a", "sampling", {"size": 0})], []), "nodes[0].config.size"),
    (graph([node("tmp-a", "sampling", {"size": 1001})], []), "nodes[0].config.size"),
    (graph([node("tmp-a", "sampling", {"method": "sistematico"})], []), "nodes[0].config.method"),
    (graph([node("tmp-a", "sampling", {"stratify_by": "agente"})], []), "nodes[0].config.stratify_by"),
    (graph([node("tmp-a", "sampling", {"order_by": "nombre"})], []), "nodes[0].config.order_by"),
    (graph([node("tmp-a", "sampling", {"query": "canal = voz"})], []), "nodes[0].config.query"),
    (graph([node("tmp-a", "prompt", {"temperature": -0.1})], []), "nodes[0].config.temperature"),
    (graph([node("tmp-a", "prompt", {"temperature": 1.5})], []), "nodes[0].config.temperature"),
    (graph([node("tmp-a", "prompt", {"template": "x" * 4001})], []), "nodes[0].config.template"),
    (graph([node("tmp-a", "prompt", {"model": "gpt-real"})], []), "nodes[0].config.model"),
    (graph([node("tmp-a", "prompt", {"output": {"type": "xml"}})], []), "nodes[0].config.output.type"),
    (graph([node("tmp-a", "prompt", {"output": {"type": "etiqueta", "labels": ["a"] * 21}})], []),
     "nodes[0].config.output.labels"),
    (graph([node("tmp-a", "prompt", {"output": {"type": "etiqueta", "labels": ["x" * 61]}})], []),
     "nodes[0].config.output.labels[0]"),
    (graph([node("tmp-a", "prompt", {"output": {"type": "json", "fields": [{"name": "a", "type": "fecha"}]}})], []),
     "nodes[0].config.output.fields[0].type"),
    (graph([node("tmp-a", "output", {"kind": "grafico"})], []), "nodes[0].config.kind"),
    (graph([node("tmp-a", "output", {"aggregation": "media"})], []), "nodes[0].config.aggregation"),
    (graph([node("tmp-a", "output", {"destination": "x" * 81})], []), "nodes[0].config.destination"),
    (graph([node("tmp-a", "output", {"formato": "csv"})], []), "nodes[0].config.formato"),
    (graph([node("tmp-a", "sampling", x=math.inf)], []), "nodes[0].position.x"),
    ({**graph([], []), "version": 2}, "version"),
    ({**graph([], []), "extra": True}, "extra"),
])
def test_rejects_invalid_structure_and_configuration_ranges(payload, path):
    assert path in [e["path"] for e in _errors(payload)]


def test_rejects_edges_to_unknown_nodes_and_rule_violations_with_their_edge_path():
    nodes = [node("tmp-s", "sampling"), node("tmp-p1", "prompt"), node("tmp-p2", "prompt"), node("tmp-o", "output")]
    errors = _errors(graph(nodes, [
        edge("tmp-s", "tmp-p1"),
        edge("tmp-s", "tmp-o"),      # par no admitido
        edge("tmp-s", "tmp-x"),      # nodo inexistente
        edge("tmp-s", "tmp-p1"),     # duplicada
        edge("tmp-p1", "tmp-p2"),
        edge("tmp-p2", "tmp-p1"),    # entrada ocupada (y ciclo)
    ]))
    assert [e["path"] for e in errors] == ["edges[1]", "edges[2]", "edges[3]", "edges[5]"]


def test_rejects_cycles_even_if_each_edge_is_admissible_on_its_own():
    nodes = [node("tmp-p1", "prompt"), node("tmp-p2", "prompt"), node("tmp-p3", "prompt")]
    errors = _errors(graph(nodes, [edge("tmp-p1", "tmp-p2"), edge("tmp-p2", "tmp-p3"), edge("tmp-p3", "tmp-p1")]))
    assert errors[-1]["path"] == "edges[2]"
    assert "cycle" in errors[-1]["message"]


def test_rejects_more_than_50_nodes_or_100_edges():
    many_nodes = graph([node(f"tmp-{i}", "prompt") for i in range(51)], [])
    assert "nodes" in [e["path"] for e in _errors(many_nodes)]
    many_edges = graph([node("tmp-p", "prompt"), node("tmp-o", "output")], [edge("tmp-p", "tmp-o")] * 101)
    assert "edges" in [e["path"] for e in _errors(many_edges)]


def test_reports_every_integrity_error_at_once():
    errors = _errors(graph([node("tmp-a", "sampling", {"size": 0}), node("tmp-a", "prompt", {"temperature": 3})],
                           [edge("tmp-a", "tmp-z")]))
    assert len(errors) >= 3


# --- Validación de completitud (criterio 4) ---

def test_complete_and_chained_graphs_are_valid():
    assert _codes(complete_graph()) == []
    assert _codes(chained_graph()) == []


def test_empty_flow_is_invalid():
    assert _codes(graph([], [])) == [("missing_sampling", None), ("missing_output", None)]


def test_missing_output_and_missing_sampling():
    payload = graph([node("tmp-s", "sampling", SAMPLING), node("tmp-p", "prompt", PROMPT_TEXT)], [edge("tmp-s", "tmp-p")])
    assert ("missing_output", None) in _codes(payload)
    payload = graph([node("tmp-p", "prompt", PROMPT_TEXT), node("tmp-o", "output", OUTPUT_TABLE)], [edge("tmp-p", "tmp-o")])
    assert ("missing_sampling", None) in _codes(payload)


@pytest.mark.parametrize("node_id, config", [
    ("tmp-s", {}),
    ("tmp-s", {**SAMPLING, "size": None}),
    ("tmp-s", {**SAMPLING, "method": "estratificado"}),
    ("tmp-s", {**SAMPLING, "method": "primeros_n", "order_by": "fecha"}),
    ("tmp-p", {**PROMPT_LABEL, "model": None}),
    ("tmp-p", {**PROMPT_LABEL, "temperature": None}),
    ("tmp-p", {**PROMPT_LABEL, "output": None}),
    ("tmp-p", {**PROMPT_LABEL, "template": "   "}),
    ("tmp-o", {**OUTPUT_METRIC, "aggregation": None}),
    ("tmp-o", {**OUTPUT_METRIC, "destination": " "}),
    ("tmp-o", {}),
])
def test_unconfigured_nodes(node_id, config):
    payload = complete_graph()
    target = next(n for n in payload["nodes"] if n["id"] == node_id)
    target["config"] = {k: v for k, v in config.items() if v is not None}
    assert ("node_unconfigured", node_id) in _codes(payload)


@pytest.mark.parametrize("node_id, config", [
    ("tmp-s", {**SAMPLING, "query": {"root": {"op": "and", "conditions": [{"field": "canal", "operator": "is", "value": "fax"}]}}}),
    ("tmp-s", {**SAMPLING, "query": {"from": days_ago(7), "to": days_ago(26), "root": {"op": "and", "conditions": []}}}),
    ("tmp-p", {**PROMPT_LABEL, "output": {"type": "etiqueta", "labels": ["Solo una"]}}),
    ("tmp-p", {**PROMPT_LABEL, "output": {"type": "etiqueta", "labels": ["Sí", "sí "]}}),
    ("tmp-p", {**PROMPT_LABEL, "output": {"type": "etiqueta", "labels": ["Sí", " "]}}),
])
def test_invalid_configuration_values(node_id, config):
    payload = complete_graph()
    next(n for n in payload["nodes"] if n["id"] == node_id)["config"] = config
    assert ("invalid_config", node_id) in _codes(payload)


@pytest.mark.parametrize("fields", [
    [],
    [{"name": "motivo", "type": "texto"}, {"name": "motivo", "type": "numero"}],
    [{"name": "2motivo", "type": "texto"}],
    [{"name": "con espacio", "type": "texto"}],
])
def test_invalid_json_schemas(fields):
    payload = complete_graph()
    payload["nodes"][1]["config"]["output"] = {"type": "json", "fields": fields}
    payload["nodes"][2]["config"] = OUTPUT_TABLE
    assert ("invalid_config", "tmp-p") in _codes(payload)


def test_prompt_without_variables_and_unknown_variables():
    payload = complete_graph()
    payload["nodes"][1]["config"]["template"] = "Clasifica la conversación"
    assert ("prompt_without_variables", "tmp-p") in _codes(payload)
    payload["nodes"][1]["config"]["template"] = "Clasifica {{summary}} y {{ agente }}"
    assert ("unknown_variable", "tmp-p") in _codes(payload)
    payload["nodes"][1]["config"]["template"] = "Clasifica {{ summary }}"
    assert _codes(payload) == []


def test_previous_result_is_only_available_in_a_chained_prompt():
    payload = complete_graph()
    payload["nodes"][1]["config"]["template"] = "Revisa {{resultado_anterior}}"
    assert ("previous_result_without_chain", "tmp-p") in _codes(payload)
    assert _codes(chained_graph()) == []


def test_disconnected_nodes():
    base = complete_graph()
    lonely = [node("tmp-s2", "sampling", SAMPLING), node("tmp-p2", "prompt", PROMPT_TEXT), node("tmp-o2", "output", OUTPUT_TABLE)]
    codes = _codes(graph(base["nodes"] + lonely, base["edges"]))
    assert {("disconnected_node", "tmp-s2"), ("disconnected_node", "tmp-p2"), ("disconnected_node", "tmp-o2")} <= set(codes)
    # Un prompt con entrada pero sin salida también está suelto.
    codes = _codes(graph(base["nodes"] + [lonely[1]], base["edges"] + [edge("tmp-s", "tmp-p2")]))
    assert ("disconnected_node", "tmp-p2") in codes


def test_metric_requires_a_prompt_that_produces_labels():
    payload = complete_graph()
    payload["nodes"][1]["config"] = PROMPT_TEXT
    assert ("metric_requires_labels", "tmp-o") in _codes(payload)
    payload["nodes"][2]["config"] = OUTPUT_REPORT
    assert _codes(payload) == []


def test_duplicate_destination_names():
    payload = chained_graph()
    payload["nodes"][5]["config"] = {**OUTPUT_REPORT, "destination": " Insights_por_conversacion"}
    assert ("duplicate_destination", "tmp-o3") in _codes(payload)


def test_every_issue_has_a_message():
    issues = validate(parse_graph(graph([node("tmp-p", "prompt", {"template": "hola"})], [])))
    assert issues and all(issue.message for issue in issues)


# --- Propiedad: grafos aleatorios ---

TYPES = ["sampling", "prompt", "output"]
CONFIG_VALUES = {
    "sampling": [SAMPLING, {}, {**SAMPLING, "method": "estratificado", "stratify_by": "cola"},
                 {**SAMPLING, "method": "primeros_n", "order_by": "csat", "order": "asc"}, {"size": 0}, {"method": 7}],
    "prompt": [PROMPT_LABEL, PROMPT_TEXT, {}, {"template": "sin variables"}, {"temperature": 9},
               {**PROMPT_TEXT, "template": "{{resultado_anterior}}"}, {"output": {"type": "json", "fields": "x"}}],
    "output": [OUTPUT_METRIC, OUTPUT_TABLE, OUTPUT_REPORT, {}, {"kind": None}, {"destination": 5}],
}


def _random_graph(rng: random.Random) -> dict:
    if rng.random() < 0.5:
        payload = copy.deepcopy(rng.choice([complete_graph, chained_graph])())
        for _ in range(rng.randint(0, 3)):
            mutation = rng.randrange(4)
            if mutation == 0 and payload["edges"]:
                payload["edges"].pop(rng.randrange(len(payload["edges"])))
            elif mutation == 1:
                ids_ = [n["id"] for n in payload["nodes"]] + ["tmp-zz"]
                payload["edges"].append(edge(rng.choice(ids_), rng.choice(ids_)))
            elif mutation == 2 and payload["nodes"]:
                target = rng.choice(payload["nodes"])
                target["config"] = copy.deepcopy(rng.choice(CONFIG_VALUES[target["type"]]))
            else:
                node_type = rng.choice(TYPES)
                payload["nodes"].append(node(f"tmp-n{rng.randrange(99)}", node_type,
                                             rng.choice(CONFIG_VALUES[node_type])))
        return payload
    count = rng.randint(0, 8)
    nodes = []
    for i in range(count):
        node_type = rng.choice(TYPES + ["otro"]) if rng.random() < 0.05 else rng.choice(TYPES)
        nodes.append(node(f"tmp-{i}", node_type, rng.choice(CONFIG_VALUES.get(node_type, [{}]))))
    node_ids = [n["id"] for n in nodes] + ["tmp-fantasma"]
    edges = [edge(rng.choice(node_ids), rng.choice(node_ids)) for _ in range(rng.randint(0, 12))]
    return graph(nodes, edges)


def _is_acyclic(node_ids: list[str], edges: list[tuple[str, str]]) -> bool:
    indegree = {n: 0 for n in node_ids}
    children = defaultdict(list)
    for source, target in edges:
        children[source].append(target)
        indegree[target] += 1
    ready = [n for n, d in indegree.items() if d == 0]
    seen = 0
    while ready:
        current = ready.pop()
        seen += 1
        for child in children[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    return seen == len(node_ids)


def test_random_graphs_never_crash_and_keep_the_invariants():
    rng = random.Random(4)
    valid_flows = saved_graphs = 0
    for _ in range(500):
        payload = _random_graph(rng)
        try:
            parsed = parse_graph(payload)
        except GraphError as exc:
            assert exc.errors and all(e["path"] and e["message"] for e in exc.errors)
            continue
        saved_graphs += 1
        types = {n.id: n.type for n in parsed.nodes}
        pairs = [(e.source, e.target) for e in parsed.edges]
        assert _is_acyclic(list(types), pairs)
        assert len(set(pairs)) == len(pairs)
        for source, target in pairs:
            assert (types[source], types[target]) in {("sampling", "prompt"), ("prompt", "prompt"), ("prompt", "output")}
        assert all(sum(1 for _, t in pairs if t == n) <= 1 for n, kind in types.items() if kind != "sampling")
        issues = validate(parsed)
        if not issues:
            valid_flows += 1
            reachable = {s for s, kind in types.items() if kind == "sampling"}
            changed = True
            while changed:
                changed = False
                for source, target in pairs:
                    if source in reachable and target not in reachable:
                        reachable.add(target)
                        changed = True
            assert "output" in types.values() and set(types) == reachable
    assert saved_graphs >= 100 and valid_flows >= 40, (saved_graphs, valid_flows)


@pytest.mark.parametrize("bad_type", [[], {}, ["sampling"], 3, None])
def test_non_string_node_types_are_integrity_errors_not_crashes(bad_type):
    """Regresión de la verificación: un `type` no hashable lanzaba `TypeError` (500 en la API)."""
    errors = _errors(graph([{"id": "tmp-a", "type": bad_type, "position": {"x": 0, "y": 0}, "config": {}}], []))
    assert errors[0]["path"].startswith("nodes[0]")


def test_non_string_ids_and_edge_endpoints_are_integrity_errors():
    errors = _errors(graph([{"id": ["x"], "type": "prompt", "position": {"x": 0, "y": 0}}], [{"source": [], "target": {}}]))
    assert errors
