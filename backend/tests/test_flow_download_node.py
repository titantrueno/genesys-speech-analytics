"""Caja «Genesys download» en el grafo de un flujo de insights (FE017, T2; criterios 1, 2, 3 y 11).

La caja es el inicio del flujo: guarda la configuración de una descarga de FE011 (intervalo, canales, «Sobrescribir»,
programación y activo), solo se conecta a un Sampling y un flujo tiene como mucho una.
"""
from datetime import date, timedelta

import pytest

from app.flows import rules
from app.flows.model import GraphError, parse_graph
from app.flows.rules import blocking, validate
from tests.flow_fixtures import OUTPUT_TABLE, PROMPT_TEXT, SAMPLING, edge, graph, node

DOWNLOAD = {"interval": {"type": "relativo", "unit": "hoy"}, "channels": ["voz", "chat"], "overwrite": False,
            "schedule": {"type": "cada_horas", "hours": 1}, "active": True}
SAMPLING_AFTER_DOWNLOAD = {"method": "aleatorio", "size": 10}


def _end_to_end(download: dict | None = None, sampling: dict | None = None) -> dict:
    return graph(
        [node("tmp-d", "descarga", DOWNLOAD if download is None else download),
         node("tmp-s", "sampling", SAMPLING_AFTER_DOWNLOAD if sampling is None else sampling, x=300),
         node("tmp-p", "prompt", PROMPT_TEXT, x=600), node("tmp-o", "output", OUTPUT_TABLE, x=900)],
        [edge("tmp-d", "tmp-s"), edge("tmp-s", "tmp-p"), edge("tmp-p", "tmp-o")])


def _errors(payload: dict) -> list[dict]:
    with pytest.raises(GraphError) as exc:
        parse_graph(payload)
    return exc.value.errors


def _issues(payload: dict) -> list[tuple[str, str | None]]:
    return [(issue.code, issue.node_id) for issue in validate(parse_graph(payload))]


@pytest.fixture
def real_origin(monkeypatch):
    monkeypatch.setattr(rules, "active_origin", lambda: "real")


# --- Integridad al guardar (criterio 1) ---

@pytest.mark.parametrize("download", [
    DOWNLOAD,
    {"interval": {"type": "relativo", "unit": "horas", "amount": 6}, "channels": ["chat"],
     "schedule": {"type": "diaria", "time": "07:30"}, "active": False, "overwrite": True},
    {"interval": {"type": "especifico", "from": "2026-10-01T00:00:00", "to": "2026-10-02T00:00:00"},
     "channels": ["voz"], "schedule": {"type": "desactivada"}},
    {},
])
def test_the_box_round_trips(download):
    payload = _end_to_end(download)
    assert parse_graph(payload).dump() == payload


@pytest.mark.parametrize("config, path, message", [
    ({"interval": {"type": "relativo", "unit": "horas", "amount": 0}}, "nodes[0].config.interval",
     "The number of hours must be between 1 and 720"),
    ({"interval": {"type": "relativo", "unit": "dias", "amount": 91}}, "nodes[0].config.interval",
     "The number of days must be between 1 and 90"),
    ({"interval": {"type": "especifico", "from": "2026-10-02T00:00:00", "to": "2026-10-01T00:00:00"}},
     "nodes[0].config.interval", "“From” must be before “to”"),
    ({"interval": {"type": "especifico", "from": "2026-01-01T00:00:00", "to": "2026-10-01T00:00:00"}},
     "nodes[0].config.interval", "The interval cannot exceed 90 days"),
    ({"channels": []}, "nodes[0].config.channels", "Choose at least one channel"),
    ({"channels": ["email"]}, "nodes[0].config.channels", None),
    ({"schedule": {"type": "cada_horas", "hours": 25}}, "nodes[0].config.schedule", "The hours must be between 1 and 24"),
    ({"schedule": {"type": "diaria", "time": "25:00"}}, "nodes[0].config.schedule", "The time must have the format HH:MM"),
    ({"interval": {"type": "especifico", "from": "2026-10-01T00:00:00", "to": "2026-10-02T00:00:00"},
      "schedule": {"type": "diaria", "time": "08:00"}}, "nodes[0].config", "A scheduled download needs a relative interval"),
    ({"timezone": "Europe/Madrid"}, "nodes[0].config.timezone", None),
])
def test_invalid_box_values_are_rejected_with_their_path(config, path, message):
    errors = _errors(_end_to_end(config))
    assert any(e["path"].startswith(path) and e["node_id"] == "tmp-d" and (message is None or message in e["message"])
               for e in errors), errors


def test_a_flow_has_at_most_one_box():
    payload = _end_to_end()
    payload["nodes"].append(node("tmp-d2", "descarga", DOWNLOAD))
    errors = _errors(payload)
    assert [e["node_id"] for e in errors] == ["tmp-d2"]
    assert "only one Genesys download" in errors[0]["message"]


def test_the_box_only_feeds_a_sampling_when_saving():
    payload = _end_to_end()
    payload["edges"].append(edge("tmp-d", "tmp-p"))
    assert any(e["path"] == "edges[3]" for e in _errors(payload))


# --- Validación (criterio 3) ---

def test_a_complete_end_to_end_flow_validates_with_real_data(real_origin):
    assert blocking(validate(parse_graph(_end_to_end()))) == []


def test_the_sampling_behind_a_box_does_not_need_filters(real_origin):
    assert ("node_unconfigured", "tmp-s") not in _issues(_end_to_end())
    # Sin caja, los filtros siguen siendo obligatorios (FE004).
    standalone = _end_to_end()
    standalone["nodes"].pop(0)
    standalone["edges"].pop(0)
    assert ("node_unconfigured", "tmp-s") in _issues(standalone)


def test_the_box_needs_the_real_origin(monkeypatch):
    monkeypatch.setattr(rules, "active_origin", lambda: "sintetico")
    issues = validate(parse_graph(_end_to_end()))
    needs_real = [i for i in issues if i.code == "download_needs_real_origin"]
    assert [(i.node_id, i.severity) for i in needs_real] == [("tmp-d", "error")]
    assert needs_real[0].message == "A Genesys download needs the real data origin."


@pytest.mark.parametrize("config, missing", [
    ({}, "interval, channels"),
    ({"interval": {"type": "relativo", "unit": "hoy"}}, "channels"),
    ({"channels": ["voz"]}, "interval"),
])
def test_an_incomplete_box_is_not_configured(real_origin, config, missing):
    issues = [i for i in validate(parse_graph(_end_to_end(config))) if i.node_id == "tmp-d"]
    assert [(i.code, i.message) for i in issues] == [("node_unconfigured", f"Not configured: missing {missing}.")]


def test_a_box_without_output_is_loose(real_origin):
    payload = _end_to_end()
    payload["edges"].pop(0)
    assert ("disconnected_node", "tmp-d") in _issues(payload)
    issue = next(i for i in validate(parse_graph(payload)) if i.node_id == "tmp-d")
    assert issue.message == "Loose node: connect it to a Sampling."


def test_a_specific_interval_in_the_future_is_not_valid(real_origin):
    today = date.today()  # el reloj real, no la fecha de referencia del dataset
    future = {"type": "especifico", "from": f"{today - timedelta(days=1)}T00:00:00",
              "to": f"{today + timedelta(days=2)}T00:00:00"}
    issues = [i for i in validate(parse_graph(_end_to_end({**DOWNLOAD, "interval": future,
                                                             "schedule": {"type": "desactivada"}})))
              if i.node_id == "tmp-d"]
    assert [(i.code, i.message) for i in issues] == [("invalid_config", "The interval cannot end in the future.")]


def test_flows_without_a_box_validate_as_before(real_origin):
    payload = graph([node("tmp-s", "sampling", SAMPLING), node("tmp-p", "prompt", PROMPT_TEXT, x=300),
                     node("tmp-o", "output", OUTPUT_TABLE, x=600)],
                    [edge("tmp-s", "tmp-p"), edge("tmp-p", "tmp-o")])
    assert blocking(validate(parse_graph(payload))) == []


def test_the_catalog_offers_the_box(api):
    types = {o["value"]: o["label"] for o in api.get("/api/flows/catalog").json()["node_types"]}
    assert types["descarga"] == "Genesys download"
