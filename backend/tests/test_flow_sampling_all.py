"""Sampling «All conversations» (FE017, T3; criterios 10 y 11): todas las conversaciones que cumplen los filtros, sin
método ni tamaño, con un aviso `large_sample` si son muchas."""
import copy

import pytest

from app.data.store import get_dataset
from app.flows import catalog, rules
from app.flows.model import GraphError, SamplingConfig, parse_graph
from app.flows.rules import blocking, validate
from app.flows.sampling import candidates, draw_sample
from app.query.engine import run_query
from app.query.model import parse_query
from tests.flow_fixtures import OUTPUT_TABLE, PROMPT_TEXT, SAMPLING, complete_graph, days_ago, edge, graph, node
from tests.test_flow_runs import detail, flow_with, run

QUERY = {"from": days_ago(26), "to": days_ago(1),
         "root": {"op": "and", "conditions": [{"field": "channel", "operator": "is", "value": "chat"}]}}
ALL = {"query": QUERY, "size": "all"}


def _expected(query: dict = QUERY) -> list[str]:
    return [c.id for c in run_query(parse_query(copy.deepcopy(query)), get_dataset())]


def _graph(sampling: dict, prompt: dict = PROMPT_TEXT) -> dict:
    return graph([node("tmp-s", "sampling", sampling), node("tmp-p", "prompt", prompt, x=300),
                  node("tmp-o", "output", OUTPUT_TABLE, x=600)],
                 [edge("tmp-s", "tmp-p"), edge("tmp-p", "tmp-o")])


def test_all_round_trips_and_needs_no_method():
    payload = _graph(ALL)
    assert parse_graph(payload).dump() == payload
    assert blocking(validate(parse_graph(payload))) == []


@pytest.mark.parametrize("size", ["todas", 0, 1001, "ALL"])
def test_other_sizes_are_still_rejected(size):
    with pytest.raises(GraphError):
        parse_graph(_graph({**ALL, "size": size}))


def test_all_draws_every_candidate_in_chronological_order():
    config = SamplingConfig(**ALL)
    available = candidates(config)
    drawn = draw_sample(available, config, seed=1)
    assert sorted(c.id for c in drawn) == sorted(_expected())
    assert [(c.started_at, c.id) for c in drawn] == sorted((c.started_at, c.id) for c in drawn)
    assert drawn


def test_a_run_with_all_processes_every_matching_conversation(api):
    flow = flow_with(api, _graph(ALL))
    final = detail(api, flow, run(api, flow)["id"])
    assert final["status"] == "ok"
    assert final["sample_size"] == len(_expected())
    table = next(iter(final["outputs"].values()))["result"]
    assert sorted(row["conversation"]["id"] for row in table["rows"]) == sorted(_expected())


def test_a_saved_sized_graph_still_draws_the_same_sample():
    config = SamplingConfig(**SAMPLING)
    available = candidates(config)
    assert [c.id for c in draw_sample(available, config, 7)] == [c.id for c in draw_sample(available, config, 7)]
    assert len(draw_sample(available, config, 7)) == SAMPLING["size"]
    assert parse_graph(complete_graph()).dump() == complete_graph()


# --- Aviso `large_sample` ---

def _large(payload: dict) -> list:
    return [i for i in validate(parse_graph(payload)) if i.code == "large_sample"]


def test_large_sample_warns_above_the_threshold_without_blocking(monkeypatch):
    count = len(_expected())
    monkeypatch.setattr(catalog, "LARGE_SAMPLE", count - 1)
    issues = _large(_graph(ALL))
    assert [(i.node_id, i.severity) for i in issues] == [("tmp-s", "warning")]
    assert f"{count} conversations" in issues[0].message
    assert "LLM" not in issues[0].message  # el Prompt es simulado
    assert blocking(validate(parse_graph(_graph(ALL)))) == []


def test_large_sample_mentions_the_cost_of_a_real_llm(monkeypatch):
    monkeypatch.setattr(catalog, "LARGE_SAMPLE", len(_expected()) - 1)
    real = {**PROMPT_TEXT, "provider": "gemini", "model": "gemini-3.5-flash-lite"}
    issues = _large(_graph(ALL, real))
    assert len(issues) == 1 and "one LLM call per conversation" in issues[0].message


def test_no_large_sample_at_or_below_the_threshold_or_with_a_size(monkeypatch):
    monkeypatch.setattr(catalog, "LARGE_SAMPLE", len(_expected()))
    assert _large(_graph(ALL)) == []
    monkeypatch.setattr(catalog, "LARGE_SAMPLE", 0)
    assert _large(_graph({**ALL, "size": 10, "method": "aleatorio"})) == []


def test_no_large_sample_behind_a_download_box(monkeypatch):
    monkeypatch.setattr(rules, "active_origin", lambda: "real")
    monkeypatch.setattr(catalog, "LARGE_SAMPLE", 0)
    payload = _graph({"size": "all"})
    payload["nodes"].insert(0, node("tmp-d", "descarga", {"interval": {"type": "relativo", "unit": "hoy"},
                                                          "channels": ["voz"]}))
    payload["edges"].insert(0, edge("tmp-d", "tmp-s"))
    assert _large(payload) == []


def test_the_threshold_is_one_thousand():
    assert catalog.LARGE_SAMPLE == 1000


# --- Estimación ---

def test_estimate_with_all_gives_every_available_conversation(api):
    body = api.post("/api/flows/sampling/estimate", json={"query": QUERY, "size": "all"}).json()
    assert body == {"available": len(_expected()), "sample_size": len(_expected()),
                    "period": {"from": QUERY["from"], "to": QUERY["to"]}}


def test_estimate_behind_a_download_depends_on_it(api):
    body = api.post("/api/flows/sampling/estimate", json={"after_download": True, "size": "all"}).json()
    assert body == {"available": None, "sample_size": None, "period": None, "depends_on_download": True}


def test_estimate_still_needs_a_query_without_a_download(api):
    assert api.post("/api/flows/sampling/estimate", json={"size": "all"}).status_code == 422
