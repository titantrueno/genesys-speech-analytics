"""API de flujos de insights: CRUD, ida y vuelta, catálogo, estimación, validación y permisos (FE004, criterios 1, 3, 8 y 9)."""
import copy
import random

import pytest

from app import auth, ids
from app.data.store import get_dataset
from app.query.engine import run_query
from app.query.model import parse_query
from tests.roles import add_role
from tests.flow_fixtures import SAMPLING, days_ago, chained_graph, complete_graph, edge, graph, node

EMPTY_GRAPH = {"version": 1, "nodes": [], "edges": []}


def create(api, name="Motivos de fraude") -> dict:
    response = api.post("/api/flows", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def save(api, flow_id: str, payload: dict) -> dict:
    response = api.put(f"/api/flows/{flow_id}/graph", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def with_entity_ids(payload: dict) -> dict:
    """Sustituye las claves temporales por identificadores `1ND` generados con `app/ids.py`."""
    rng = random.Random(7)
    mapping = {n["id"]: ids.new_id(ids.NODE, rng) for n in payload["nodes"]}
    result = copy.deepcopy(payload)
    for n in result["nodes"]:
        n["id"] = mapping[n["id"]]
    for e in result["edges"]:
        e["source"], e["target"] = mapping[e["source"]], mapping[e["target"]]
    return result


# --- CRUD ---

def test_create_returns_an_empty_flow_with_author_and_dates(api):
    flow = create(api)
    assert ids.is_valid(flow["id"], ids.FLOW)
    assert flow["name"] == "Motivos de fraude"
    assert flow["author"] == {"id": ids.stable_id(ids.USER, "admin@bancohorizonte.demo"), "name": "Admin Demo"}
    assert flow["graph"] == EMPTY_GRAPH
    assert flow["status"] == "con_errores"
    assert flow["created_at"] == flow["updated_at"]


def test_list_shows_the_columns_ordered_by_last_modification(api):
    first = create(api, "Primero")
    second = create(api, "Segundo")
    assert [f["name"] for f in api.get("/api/flows").json()["items"]] == ["Segundo", "Primero"]
    api.patch(f"/api/flows/{first['id']}", json={"name": "Primero renombrado"})
    items = api.get("/api/flows").json()["items"]
    assert [f["id"] for f in items] == [first["id"], second["id"]]
    assert set(items[0]) == {"id", "name", "author", "created_at", "updated_at", "last_run", "status"}
    assert items[0]["last_run"] is None


def test_get_returns_the_flow_with_its_graph(api):
    flow = create(api)
    response = api.get(f"/api/flows/{flow['id'].lower()}")
    assert response.status_code == 200
    assert response.json()["graph"] == EMPTY_GRAPH


def test_rename_trims_and_updates_the_modification_date(api):
    flow = create(api)
    renamed = api.patch(f"/api/flows/{flow['id']}", json={"name": "  Nuevo nombre  "}).json()
    assert renamed["name"] == "Nuevo nombre"
    assert renamed["updated_at"] > flow["updated_at"]
    assert renamed["created_at"] == flow["created_at"]


@pytest.mark.parametrize("name", ["", "   ", "x" * 81])
def test_invalid_names_return_422(api, name):
    assert api.post("/api/flows", json={"name": name}).status_code == 422
    flow = create(api)
    assert api.patch(f"/api/flows/{flow['id']}", json={"name": name}).status_code == 422


def test_delete_removes_the_flow(api):
    flow = create(api)
    assert api.delete(f"/api/flows/{flow['id']}").status_code == 204
    assert api.get(f"/api/flows/{flow['id']}").status_code == 404
    assert api.get("/api/flows").json()["items"] == []


@pytest.mark.parametrize("flow_id", [
    ids.new_id(ids.FLOW, random.Random(1)),
    "no-es-un-id",
    ids.new_id(ids.RUN, random.Random(1)),
])
def test_unknown_malformed_or_foreign_ids_return_404(api, flow_id):
    create(api)
    assert api.get(f"/api/flows/{flow_id}").status_code == 404
    assert api.patch(f"/api/flows/{flow_id}", json={"name": "x"}).status_code == 404
    assert api.put(f"/api/flows/{flow_id}/graph", json=EMPTY_GRAPH).status_code == 404
    assert api.post(f"/api/flows/{flow_id}/duplicate").status_code == 404
    assert api.delete(f"/api/flows/{flow_id}").status_code == 404


# --- Guardar e ida y vuelta (criterio 8) ---

def test_saving_and_reading_returns_exactly_the_same_json(api):
    flow = create(api)
    payload = with_entity_ids(chained_graph())
    saved = save(api, flow["id"], payload)
    assert saved["graph"] == payload
    assert saved["id_map"] == {}
    assert api.get(f"/api/flows/{flow['id']}").json()["graph"] == payload


def test_temporary_keys_become_node_ids_and_edges_are_rewritten(api):
    flow = create(api)
    payload = chained_graph()
    saved = save(api, flow["id"], payload)
    id_map = saved["id_map"]
    assert set(id_map) == {n["id"] for n in payload["nodes"]}
    assert all(ids.is_valid(value, ids.NODE) for value in id_map.values())
    assert len(set(id_map.values())) == len(id_map)
    expected = copy.deepcopy(payload)
    for n in expected["nodes"]:
        n["id"] = id_map[n["id"]]
    for e in expected["edges"]:
        e["source"], e["target"] = id_map[e["source"]], id_map[e["target"]]
    assert saved["graph"] == expected
    # Guardar de nuevo lo que devolvió el backend no cambia nada.
    again = save(api, flow["id"], saved["graph"])
    assert again["graph"] == expected and again["id_map"] == {}
    assert api.get(f"/api/flows/{flow['id']}").json()["graph"] == expected


def test_saving_a_complete_graph_makes_the_flow_valid(api):
    flow = create(api)
    assert save(api, flow["id"], complete_graph())["status"] == "valido"
    assert api.get("/api/flows").json()["items"][0]["status"] == "valido"


def test_incomplete_drafts_can_be_saved(api):
    flow = create(api)
    draft = graph([node("tmp-s", "sampling", {"method": "aleatorio"}), node("tmp-p", "prompt")], [edge("tmp-s", "tmp-p")])
    assert save(api, flow["id"], draft)["status"] == "con_errores"


def test_saving_an_impossible_graph_returns_422_and_keeps_the_previous_version(api):
    flow = create(api)
    saved = save(api, flow["id"], complete_graph())
    broken = graph([node("tmp-s", "sampling"), node("tmp-o", "output")], [edge("tmp-s", "tmp-o")])
    response = api.put(f"/api/flows/{flow['id']}/graph", json=broken)
    assert response.status_code == 422
    assert response.json()["detail"][0]["path"] == "edges[0]"
    assert api.get(f"/api/flows/{flow['id']}").json()["graph"] == saved["graph"]


def test_saving_updates_the_modification_date(api):
    flow = create(api)
    assert save(api, flow["id"], complete_graph())["updated_at"] > flow["updated_at"]


# --- Duplicar ---

def test_duplicate_copies_the_graph_with_new_nodes_and_rewritten_edges(api):
    flow = create(api)
    original = save(api, flow["id"], chained_graph())["graph"]
    response = api.post(f"/api/flows/{flow['id']}/duplicate")
    assert response.status_code == 201
    copy_ = response.json()
    assert copy_["id"] != flow["id"] and ids.is_valid(copy_["id"], ids.FLOW)
    assert copy_["name"] == "Copia de Motivos de fraude"
    new_ids = [n["id"] for n in copy_["graph"]["nodes"]]
    assert all(ids.is_valid(i, ids.NODE) for i in new_ids)
    assert not set(new_ids) & {n["id"] for n in original["nodes"]}
    mapping = dict(zip([n["id"] for n in original["nodes"]], new_ids))
    assert copy_["graph"]["edges"] == [{"source": mapping[e["source"]], "target": mapping[e["target"]]} for e in original["edges"]]
    assert [(n["type"], n["position"], n["config"]) for n in copy_["graph"]["nodes"]] == \
        [(n["type"], n["position"], n["config"]) for n in original["nodes"]]
    assert api.get(f"/api/flows/{flow['id']}").json()["graph"] == original


def test_duplicate_name_never_exceeds_80_characters(api):
    flow = create(api, "x" * 80)
    assert len(api.post(f"/api/flows/{flow['id']}/duplicate").json()["name"]) == 80


def test_duplicate_is_authored_by_whoever_duplicates(api):
    flow = create(api)
    analyst = auth.get_store().find_by_email("analista@bancohorizonte.demo")
    response = api.post(f"/api/flows/{flow['id']}/duplicate", headers={"Authorization": f"Bearer {auth.create_token(analyst)}"})
    assert response.json()["author"]["name"] == "Analista Demo"


# --- Catálogo, validación y estimación ---

def test_catalog_lists_the_configuration_options(api):
    body = api.get("/api/flows/catalog").json()
    values = lambda key: [o["value"] for o in body[key]]  # noqa: E731
    assert values("sampling_methods") == ["aleatorio", "estratificado", "primeros_n"]
    assert values("strata") == ["canal", "cola", "main_topic"]
    assert values("variables") == ["transcripcion", "summary", "main_topic", "metadatos", "resultado_anterior"]
    assert values("output_formats") == ["texto", "etiqueta", "json"]
    assert values("output_kinds") == ["tabla", "metrica", "informe"]
    assert values("models") and values("order_keys") and values("aggregations") and values("field_types")
    assert body["limits"]["max_sample_size"] == 1000


def test_validate_returns_the_issues_of_an_unsaved_graph(api):
    assert api.post("/api/flows/validate", json=complete_graph()).json() == {"valid": True, "issues": []}
    body = api.post("/api/flows/validate", json=graph([node("tmp-p", "prompt", {"template": "Hola"})], [])).json()
    assert body["valid"] is False
    issue = next(i for i in body["issues"] if i["code"] == "prompt_without_variables")
    assert set(issue) == {"code", "message", "node_id"} and issue["node_id"] == "tmp-p" and issue["message"]
    assert {i["code"] for i in body["issues"]} >= {"missing_sampling", "missing_output", "node_unconfigured", "disconnected_node"}


def test_validate_rejects_an_impossible_graph_with_422(api):
    response = api.post("/api/flows/validate", json=graph([node("tmp-a", "sampling"), node("tmp-a", "prompt")], []))
    assert response.status_code == 422
    assert response.json()["detail"][0]["path"] == "nodes[1].id"


def test_estimate_counts_the_conversations_that_match_the_filters(api):
    query = {"from": days_ago(26), "to": days_ago(1),
             "root": {"op": "and", "conditions": [{"field": "channel", "operator": "is", "value": "voz"}]}}
    expected = len(run_query(parse_query(copy.deepcopy(query)), get_dataset()))
    body = api.post("/api/flows/sampling/estimate", json={"query": query, "size": 50}).json()
    assert body == {"available": expected, "sample_size": min(50, expected), "period": {"from": days_ago(26), "to": days_ago(1)}}
    assert 50 < expected
    big = api.post("/api/flows/sampling/estimate", json={"query": query, "size": 1000}).json()
    assert big["sample_size"] == expected
    no_size = api.post("/api/flows/sampling/estimate", json={"query": SAMPLING["query"]}).json()
    assert no_size["sample_size"] is None and no_size["available"] > 0


@pytest.mark.parametrize("body", [
    {"query": {"root": {"op": "and", "conditions": [{"field": "canal", "operator": "is", "value": "voz"}]}}},
    {"query": {"from": days_ago(7), "to": days_ago(26), "root": {"op": "and", "conditions": []}}},
    {"query": SAMPLING["query"], "size": 0},
    {"query": SAMPLING["query"], "size": 1001},
    {},
])
def test_estimate_rejects_invalid_filters_or_sizes(api, body):
    assert api.post("/api/flows/sampling/estimate", json=body).status_code == 422


# --- Permisos (criterio 9) ---

@pytest.fixture
def reader(api):
    """Cliente con un rol que solo tiene `flows:view` (FE006 permitirá crearlo desde la UI)."""
    store = auth.get_store()
    add_role("lector_flujos", {"flows:view"})
    user = auth.User(ids.stable_id(ids.USER, "lector@bancohorizonte.demo"), "Lector", "lector@bancohorizonte.demo", "lector_flujos")
    store.users[user.id] = user
    return {"Authorization": f"Bearer {auth.create_token(user)}"}


def test_a_view_only_role_can_read_everything(api, reader):
    flow = create(api)
    save(api, flow["id"], complete_graph())
    for method, url, body in [
        ("GET", "/api/flows", None),
        ("GET", f"/api/flows/{flow['id']}", None),
        ("GET", "/api/flows/catalog", None),
        ("POST", "/api/flows/validate", complete_graph()),
        ("POST", "/api/flows/sampling/estimate", {"query": SAMPLING["query"]}),
        ("GET", "/api/query/schema", None),
        ("GET", "/api/query/suggest?field=queue", None),
    ]:
        response = api.request(method, url, json=body, headers=reader)
        assert response.status_code == 200, (method, url, response.status_code)


def test_a_view_only_role_cannot_write(api, reader):
    flow = create(api)
    for method, url, body in [
        ("POST", "/api/flows", {"name": "x"}),
        ("PATCH", f"/api/flows/{flow['id']}", {"name": "x"}),
        ("PUT", f"/api/flows/{flow['id']}/graph", complete_graph()),
        ("POST", f"/api/flows/{flow['id']}/duplicate", None),
        ("DELETE", f"/api/flows/{flow['id']}", None),
        ("POST", "/api/query/run", {"root": {"op": "and", "conditions": []}}),
    ]:
        response = api.request(method, url, json=body, headers=reader)
        assert response.status_code == 403, (method, url, response.status_code)
    assert api.get(f"/api/flows/{flow['id']}").json()["name"] == "Motivos de fraude"


def test_viewer_cannot_see_flows(api):
    viewer = auth.get_store().find_by_email("viewer@bancohorizonte.demo")
    headers = {"Authorization": f"Bearer {auth.create_token(viewer)}"}
    assert api.get("/api/flows", headers=headers).status_code == 403
    assert api.get("/api/query/schema", headers=headers).status_code == 403
