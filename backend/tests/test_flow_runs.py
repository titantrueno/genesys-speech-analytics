"""Ejecuciones simuladas: API, progreso, errores e historial (FE004, criterios 5, 6, 7 y 9)."""
import random
import threading
import time

import pytest

from app import auth, ids
from app.flows.model import parse_graph
from app.flows.prompting import MockPromptRunner
from app.flows.runs import FlowExecutor, get_run_store, step_delay_seconds
from app.flows.store import get_flow_store
from app.routers.flows import get_prompt_runner
from app.main import app
from tests.flow_fixtures import chained_graph, complete_graph

STATUS_ORDER = {"pendiente": 0, "en_curso": 1, "ok": 2, "error": 2}


def flow_with(api, payload: dict) -> dict:
    flow = api.post("/api/flows", json={"name": "Flujo de prueba"}).json()
    response = api.put(f"/api/flows/{flow['id']}/graph", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def run(api, flow: dict) -> dict:
    response = api.post(f"/api/flows/{flow['id']}/runs")
    assert response.status_code == 202, response.text
    return response.json()


def detail(api, flow: dict, run_id: str) -> dict:
    response = api.get(f"/api/flows/{flow['id']}/runs/{run_id}")
    assert response.status_code == 200, response.text
    return response.json()


def by_type(flow: dict) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for n in flow["graph"]["nodes"]:
        result.setdefault(n["type"], []).append(n["id"])
    return result


# --- Ejecución completa ---

def test_run_starts_pending_and_finishes_with_every_output(api):
    flow = flow_with(api, chained_graph())
    started = run(api, flow)
    assert ids.is_valid(started["id"], ids.RUN)
    assert started["status"] == "pendiente"
    assert set(next(iter(started["nodes"].values()))) == {"status", "processed", "total", "message"}
    assert all(state["status"] == "pendiente" for state in started["nodes"].values())

    final = detail(api, flow, started["id"])
    assert final["status"] == "ok"
    assert final["sample_size"] == 40
    assert final["user"] == {"id": ids.stable_id(ids.USER, "admin@bancohorizonte.demo"), "name": "Admin Demo"}
    assert final["duration_ms"] >= 0 and final["finished_at"] >= final["started_at"]
    assert all(state["status"] == "ok" and state["processed"] == state["total"] == 40 for state in final["nodes"].values())

    nodes = {n["id"]: n for n in flow["graph"]["nodes"]}
    outputs = final["outputs"]
    assert set(outputs) == set(by_type(flow)["output"])
    for node_id, output in outputs.items():
        config = nodes[node_id]["config"]
        assert output["kind"] == config["kind"] and output["destination"] == config["destination"]
    metric = next(o for o in outputs.values() if o["kind"] == "metrica")["result"]
    assert [i["label"] for i in metric["items"]] == ["Positivo", "Neutro", "Negativo"]
    assert sum(i["count"] for i in metric["items"]) == 40
    table = next(o for o in outputs.values() if o["kind"] == "tabla")["result"]
    assert len(table["rows"]) == 40 and all(row["result"].startswith("A partir de «") for row in table["rows"])
    report = next(o for o in outputs.values() if o["kind"] == "informe")["result"]
    assert "40 conversaciones" in report["text"]


def test_the_sample_is_reproducible_with_the_seed_of_the_run(api):
    flow = flow_with(api, complete_graph())
    first = detail(api, flow, run(api, flow)["id"])
    graph = parse_graph(first["graph"])
    replay = get_run_store().create(get_flow_store().get(flow["id"]), auth.get_store().find_by_email("admin@bancohorizonte.demo"),
                                    seed=first["seed"])
    FlowExecutor(MockPromptRunner(), delay_s=0).execute(replay)
    assert replay.snapshot()["outputs"] == first["outputs"]
    assert graph.dump() == first["graph"]


def test_invalid_saved_flows_are_not_run(api):
    incomplete = complete_graph()
    incomplete["nodes"][1]["config"]["template"] = "Sin variables"
    flow = flow_with(api, incomplete)
    response = api.post(f"/api/flows/{flow['id']}/runs")
    assert response.status_code == 422
    assert [issue["code"] for issue in response.json()["detail"]] == ["prompt_without_variables"]
    assert api.get(f"/api/flows/{flow['id']}/runs").json()["items"] == []


def test_a_second_run_while_one_is_in_progress_returns_409(api):
    flow = flow_with(api, complete_graph())
    user = auth.get_store().find_by_email("admin@bancohorizonte.demo")
    in_progress = get_run_store().create(get_flow_store().get(flow["id"]), user, seed=1)
    assert api.post(f"/api/flows/{flow['id']}/runs").status_code == 409
    FlowExecutor(MockPromptRunner(), delay_s=0).execute(in_progress)
    assert api.post(f"/api/flows/{flow['id']}/runs").status_code == 202


# --- Progreso (criterio 6) ---

def _states(snapshot: dict) -> dict[str, tuple[int, int]]:
    return {node_id: (STATUS_ORDER[s["status"]], s["processed"]) for node_id, s in snapshot["nodes"].items()}


def test_progress_is_observable_step_by_step_and_never_goes_back(api):
    flow = flow_with(api, chained_graph())
    user = auth.get_store().find_by_email("admin@bancohorizonte.demo")
    target = get_run_store().create(get_flow_store().get(flow["id"]), user, seed=3)
    snapshots = []
    FlowExecutor(MockPromptRunner(), delay_s=0, on_step=lambda r: snapshots.append(r.snapshot())).execute(target)
    assert len(snapshots) > 80
    prompts = by_type(flow)["prompt"]
    partial = [s for s in snapshots if s["nodes"][prompts[0]]["status"] == "en_curso" and 0 < s["nodes"][prompts[0]]["processed"] < 40]
    assert partial and partial[0]["status"] == "en_curso"
    assert all(s["nodes"][prompts[1]]["status"] == "pendiente" for s in partial)
    for before, after in zip(snapshots, snapshots[1:]):
        for node_id, (status, processed) in _states(before).items():
            new_status, new_processed = _states(after)[node_id]
            assert new_status >= status and new_processed >= processed
    assert target.snapshot()["status"] == "ok"


def test_reading_while_a_run_executes_in_another_thread_is_safe(api):
    flow = flow_with(api, chained_graph())
    user = auth.get_store().find_by_email("admin@bancohorizonte.demo")
    target = get_run_store().create(get_flow_store().get(flow["id"]), user, seed=3)
    worker = threading.Thread(target=FlowExecutor(MockPromptRunner(), delay_s=0.0005).execute, args=(target,))
    worker.start()
    seen, previous = set(), None
    while worker.is_alive():
        snapshot = api.get(f"/api/flows/{flow['id']}/runs/{target.id}").json()
        seen.add(snapshot["status"])
        if previous:
            assert all(_states(snapshot)[n][1] >= p for n, (_, p) in _states(previous).items())
        previous = snapshot
    worker.join()
    assert "en_curso" in seen
    assert detail(api, flow, target.id)["status"] == "ok"


# --- Errores ---

def test_an_empty_sample_fails_the_sampling_and_leaves_its_dependants_pending(api):
    payload = complete_graph()
    payload["nodes"][0]["config"]["query"]["root"]["conditions"] = [{"field": "csat", "operator": "gt", "value": 5}]
    flow = flow_with(api, payload)
    final = detail(api, flow, run(api, flow)["id"])
    sampling, prompt, output = (by_type(flow)[t][0] for t in ("sampling", "prompt", "output"))
    assert final["status"] == "error"
    assert final["nodes"][sampling]["status"] == "error"
    assert "vacía" in final["nodes"][sampling]["message"]
    assert final["nodes"][prompt]["status"] == final["nodes"][output]["status"] == "pendiente"
    assert final["outputs"] == {} and final["sample_size"] == 0


class FailingOnChain(MockPromptRunner):
    """Falla en la tercera conversación de un prompt encadenado."""

    def __init__(self):
        self.calls = 0

    def run(self, config, conversation, previous):
        if previous is not None:
            self.calls += 1
            if self.calls == 3:
                raise RuntimeError("el proveedor no responde")
        return super().run(config, conversation, previous)


def test_a_failing_prompt_fails_only_its_branch(api):
    flow = flow_with(api, chained_graph())
    app.dependency_overrides[get_prompt_runner] = FailingOnChain
    try:
        final = detail(api, flow, run(api, flow)["id"])
    finally:
        app.dependency_overrides.clear()
    nodes = {n["id"]: n for n in flow["graph"]["nodes"]}
    first, chained = by_type(flow)["prompt"]
    assert final["status"] == "error"
    assert final["nodes"][chained] == {"status": "error", "processed": 2, "total": 40,
                                       "message": "Error al ejecutar el prompt: el proveedor no responde"}
    assert final["nodes"][first]["status"] == "ok"
    for node_id in by_type(flow)["output"]:
        upstream = next(e["source"] for e in flow["graph"]["edges"] if e["target"] == node_id)
        expected = "ok" if upstream == first else "pendiente"
        assert final["nodes"][node_id]["status"] == expected, nodes[node_id]["config"]["kind"]
    assert [o["kind"] for o in final["outputs"].values()] == ["metrica"]


def test_the_prompt_runner_can_be_replaced_without_changing_the_api(api):
    class Constant:
        def run(self, config, conversation, previous):
            return config.output.labels[-1] if config.output.type == "etiqueta" else "constante"

    flow = flow_with(api, complete_graph())
    app.dependency_overrides[get_prompt_runner] = Constant
    try:
        final = detail(api, flow, run(api, flow)["id"])
    finally:
        app.dependency_overrides.clear()
    metric = next(iter(final["outputs"].values()))["result"]
    assert [(i["label"], i["count"]) for i in metric["items"]] == [("Positivo", 0), ("Neutro", 0), ("Negativo", 40)]


def test_an_unexpected_failure_never_leaves_the_run_in_progress(api):
    class Unhashable:
        def run(self, config, conversation, previous):
            return {"no": "es una etiqueta"}

    flow = flow_with(api, complete_graph())
    app.dependency_overrides[get_prompt_runner] = Unhashable
    try:
        final = detail(api, flow, run(api, flow)["id"])
    finally:
        app.dependency_overrides.clear()
    output = by_type(flow)["output"][0]
    assert final["status"] == "error"
    assert final["nodes"][output]["status"] == "error"
    assert final["nodes"][output]["message"].startswith("Error inesperado")
    assert api.post(f"/api/flows/{flow['id']}/runs").status_code == 202


def test_concurrent_starts_create_a_single_run(api, monkeypatch):
    flow = flow_with(api, complete_graph())
    user = auth.get_store().find_by_email("admin@bancohorizonte.demo")
    target = get_flow_store().get(flow["id"])
    store = get_run_store()
    check = store.active

    def slow_check(flow_id):  # ensancha la ventana entre comprobar y crear para que una carrera sea segura
        found = check(flow_id)
        time.sleep(0.02)
        return found

    monkeypatch.setattr(store, "active", slow_check)
    barrier = threading.Barrier(8)
    started = []

    def start():
        barrier.wait()
        started.append(get_run_store().start(target, user))

    workers = [threading.Thread(target=start) for _ in range(8)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert sum(r is not None for r in started) == 1


# --- Historial (criterio 7) ---

def test_history_lists_runs_newest_first_with_their_summary(api):
    flow = flow_with(api, complete_graph())
    first = run(api, flow)
    analyst = auth.get_store().find_by_email("analista@bancohorizonte.demo")
    second = api.post(f"/api/flows/{flow['id']}/runs", headers={"Authorization": f"Bearer {auth.create_token(analyst)}"}).json()
    items = api.get(f"/api/flows/{flow['id']}/runs").json()["items"]
    assert [i["id"] for i in items] == [second["id"], first["id"]]
    assert set(items[0]) == {"id", "created_at", "started_at", "finished_at", "duration_ms", "status", "sample_size", "user"}
    assert items[0]["user"]["name"] == "Analista Demo" and items[1]["user"]["name"] == "Admin Demo"
    assert all(i["status"] == "ok" and i["sample_size"] == 40 for i in items)
    listed = api.get("/api/flows").json()["items"][0]["last_run"]
    assert listed == {"id": second["id"], "created_at": items[0]["created_at"], "status": "ok"}


def test_editing_the_flow_later_does_not_change_a_past_run(api):
    flow = flow_with(api, complete_graph())
    past = run(api, flow)
    before = detail(api, flow, past["id"])
    edited = flow["graph"]
    edited["nodes"][1]["config"]["template"] = "Otro texto con {{metadatos}}"
    edited["nodes"][1]["position"] = {"x": 999, "y": 999}
    assert api.put(f"/api/flows/{flow['id']}/graph", json=edited).status_code == 200
    after = detail(api, flow, past["id"])
    assert after["graph"] == before["graph"] != edited
    assert after["outputs"] == before["outputs"]


def test_deleting_the_flow_deletes_its_runs(api):
    flow = flow_with(api, complete_graph())
    past = run(api, flow)
    api.delete(f"/api/flows/{flow['id']}")
    assert api.get(f"/api/flows/{flow['id']}/runs").status_code == 404
    assert api.get(f"/api/flows/{flow['id']}/runs/{past['id']}").status_code == 404
    assert get_run_store().list(flow["id"]) == []  # sin fugas: la API ya da 404 al no existir el flujo


def test_unknown_or_foreign_runs_return_404(api):
    flow = flow_with(api, complete_graph())
    other = flow_with(api, complete_graph())
    past = run(api, flow)
    assert api.get(f"/api/flows/{other['id']}/runs/{past['id']}").status_code == 404
    assert api.get(f"/api/flows/{flow['id']}/runs/{ids.new_id(ids.RUN, random.Random(2))}").status_code == 404
    assert api.get(f"/api/flows/{flow['id']}/runs/{flow['id']}").status_code == 404
    assert api.post(f"/api/flows/{ids.new_id(ids.FLOW, random.Random(2))}/runs").status_code == 404


def test_running_requires_flows_edit_and_reading_runs_flows_view(api):
    flow = flow_with(api, complete_graph())
    past = run(api, flow)
    store = auth.get_store()
    store.roles["lector_flujos"] = {"flows:view"}
    reader = auth.User(ids.stable_id(ids.USER, "lector@bancohorizonte.demo"), "Lector", "lector@bancohorizonte.demo", "lector_flujos")
    store.users[reader.id] = reader
    headers = {"Authorization": f"Bearer {auth.create_token(reader)}"}
    assert api.post(f"/api/flows/{flow['id']}/runs", headers=headers).status_code == 403
    assert api.get(f"/api/flows/{flow['id']}/runs", headers=headers).status_code == 200
    assert api.get(f"/api/flows/{flow['id']}/runs/{past['id']}", headers=headers).status_code == 200


@pytest.mark.parametrize("configured, expected", [(None, 0.015), ("0", 0), ("40", 0.04), ("-5", 0), ("abc", 0.015)])
def test_the_step_delay_is_configurable(monkeypatch, configured, expected):
    """El retardo por elemento hace visible el progreso en la demo; los tests lo ponen a 0."""
    if configured is None:
        monkeypatch.delenv("FLOW_RUN_STEP_DELAY_MS", raising=False)
    else:
        monkeypatch.setenv("FLOW_RUN_STEP_DELAY_MS", configured)
    assert step_delay_seconds() == expected


def test_history_keeps_the_latest_runs_and_never_drops_an_active_one(api, monkeypatch):
    """Las ejecuciones viven en memoria: se conservan las últimas `MAX_RUNS_PER_FLOW` (hallazgo de la revisión)."""
    from app.flows import runs as runs_module
    monkeypatch.setattr(runs_module, "MAX_RUNS_PER_FLOW", 3)
    flow = flow_with(api, complete_graph())
    user = auth.get_store().find_by_email("admin@bancohorizonte.demo")
    store, target = get_run_store(), get_flow_store().get(flow["id"])
    active = store.create(target, user, seed=0)  # queda «pendiente»: no se puede descartar
    finished = []
    for seed in range(1, 6):
        created = store.create(target, user, seed=seed)
        FlowExecutor(MockPromptRunner(), delay_s=0).execute(created)
        finished.append(created.id)
    kept = [r.id for r in store.list(flow["id"])]
    assert kept == finished[::-1][:3] + [active.id]
