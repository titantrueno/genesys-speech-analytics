"""Programador de los flujos de insights con caja «Genesys download» (FE017, T5; criterios 9 y 18).

Un reloj simulado sustituye a la hora real y las ejecuciones corren en el mismo hilo: cada `tick()` lanza lo debido.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app import auth
from app.config.store import get_config
from app.flows import rules
from app.flows.model import parse_graph
from app.flows.prompting import MockPromptRunner
from app.flows.runs import FlowExecutor, get_run_store
from app.flows.scheduler import FlowScheduler, get_scheduler
from app.flows.store import get_flow_store, reset_flow_store
from tests.flow_fixtures import OUTPUT_TABLE, PROMPT_TEXT, SAMPLING, edge, graph, node
from tests.test_flow_end_to_end import FakeDownloader, _subset
from tests.test_flows_api import reader  # noqa: F401  (fixture)
from tests.test_platform_state import MemoryBackend

HOURLY = {"type": "cada_horas", "hours": 1}


def _graph(schedule: dict = HOURLY, active: bool = True) -> dict:
    box = {"interval": {"type": "relativo", "unit": "hoy"}, "channels": ["voz", "chat"], "schedule": schedule,
           "active": active}
    return graph([node("tmp-d", "descarga", box), node("tmp-s", "sampling", {"size": "all"}, x=300),
                  node("tmp-p", "prompt", PROMPT_TEXT, x=600), node("tmp-o", "output", OUTPUT_TABLE, x=900)],
                 [edge("tmp-d", "tmp-s"), edge("tmp-s", "tmp-p"), edge("tmp-p", "tmp-o")])


def _local(day: int, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, second, tzinfo=ZoneInfo(get_config().general.timezone))


class Clock:
    def __init__(self, value: datetime):
        self.value = value

    def __call__(self) -> datetime:
        return self.value


@pytest.fixture
def real_origin(monkeypatch):
    monkeypatch.setattr(rules, "active_origin", lambda: "real")


@pytest.fixture
def downloader():
    return FakeDownloader(_subset())


def _scheduler(clock: Clock, downloader: FakeDownloader) -> FlowScheduler:
    return FlowScheduler(clock=clock,
                         executor_factory=lambda: FlowExecutor(MockPromptRunner(), 0, downloader=downloader, poll_s=0),
                         run_in_background=lambda job: job(), ingestion_up=downloader.available)


def _flow(graph_payload: dict | None = None):
    admin = auth.get_store().find_by_email("admin@bancohorizonte.demo")
    return get_flow_store().create(admin, "Programado", parse_graph(graph_payload or _graph()))


def _runs(flow) -> list[dict]:
    return [run.snapshot() for run in get_run_store().list(flow.id)]


def test_an_hourly_flow_runs_once_per_hour(api, real_origin, downloader):
    flow = _flow()
    clock = Clock(_local(14, 10, 20))
    scheduler = _scheduler(clock, downloader)
    assert scheduler.tick() == []  # lo ve por primera vez: la primera, a la hora siguiente
    for moment, launched in [((10, 59), 0), ((11, 0, 30), 1), ((11, 30), 0), ((11, 59, 59), 0), ((12, 0, 10), 1),
                             ((12, 0, 40), 0)]:
        clock.value = _local(14, *moment)
        assert len(scheduler.tick()) == launched, moment
    runs = _runs(flow)
    assert len(runs) == 2
    assert {r["origin"] for r in runs} == {"programada"}
    assert {r["status"] for r in runs} == {"ok"}
    assert {r["user"]["name"] for r in runs} == {"Scheduler"}
    assert [d["origin"] for d in downloader.started] == ["programada", "programada"]


def test_a_daily_flow_runs_at_its_time_in_the_platform_time_zone(api, real_origin, downloader):
    flow = _flow(_graph({"type": "diaria", "time": "08:00"}))
    clock = Clock(_local(14, 7, 0))
    scheduler = _scheduler(clock, downloader)
    scheduler.tick()
    for moment, launched in [((14, 7, 59), 0), ((14, 8, 0, 5), 1), ((14, 9, 0), 0), ((15, 7, 59), 0), ((15, 8, 1), 1)]:
        clock.value = _local(*moment)
        assert len(scheduler.tick()) == launched, moment
    assert len(_runs(flow)) == 2


def test_a_scheduled_run_is_skipped_while_another_is_running_and_noted_in_the_next(api, real_origin, downloader):
    flow = _flow()
    clock = Clock(_local(14, 10, 20))
    scheduler = _scheduler(clock, downloader)
    scheduler.tick()
    admin = auth.get_store().find_by_email("admin@bancohorizonte.demo")
    busy = get_run_store().start(flow, admin)  # una ejecución manual sigue en curso a las 11:00
    clock.value = _local(14, 11, 0, 5)
    assert scheduler.tick() == []
    busy.update(status="ok")
    clock.value = _local(14, 12, 0, 5)
    [launched] = scheduler.tick()
    run = get_run_store().get(flow.id, launched).snapshot()
    assert run["notes"] == ["Scheduled run at 11:00 skipped: another run was in progress"]
    assert run["origin"] == "programada"


def test_an_inactive_box_is_not_scheduled_but_runs_by_hand(api, real_origin, downloader):
    from app.flows import runs as flow_runs
    from app.flows.downloader import get_downloader
    from app.main import app
    flow = _flow(_graph(active=False))
    clock = Clock(_local(14, 10, 20))
    scheduler = _scheduler(clock, downloader)
    scheduler.tick()
    clock.value = _local(14, 11, 0, 5)
    assert scheduler.tick() == []
    app.dependency_overrides[get_downloader] = lambda: downloader
    try:
        flow_runs.DOWNLOAD_POLL_S = 0
        response = api.post(f"/api/flows/{flow.id}/runs")
    finally:
        flow_runs.DOWNLOAD_POLL_S = 2.0
        app.dependency_overrides.pop(get_downloader, None)
    assert response.status_code == 202
    assert response.json()["origin"] == "manual"


def test_flows_without_a_scheduled_box_are_never_launched(api, real_origin, downloader):
    plain = graph([node("tmp-s", "sampling", SAMPLING), node("tmp-p", "prompt", PROMPT_TEXT, x=300),
                   node("tmp-o", "output", OUTPUT_TABLE, x=600)], [edge("tmp-s", "tmp-p"), edge("tmp-p", "tmp-o")])
    _flow(plain)
    _flow(_graph({"type": "desactivada"}))
    clock = Clock(_local(14, 10, 20))
    scheduler = _scheduler(clock, downloader)
    for hour in range(10, 15):
        clock.value = _local(14, hour, 0, 5)
        assert scheduler.tick() == []


def test_after_a_restart_the_schedule_survives_and_missed_runs_are_not_recovered(api, real_origin, downloader):
    backend = MemoryBackend()
    reset_flow_store(backend)
    flow = _flow()
    clock = Clock(_local(14, 10, 20))
    _scheduler(clock, downloader).tick()
    # Reinicio a las 13:10: un almacén nuevo lee el flujo guardado y un programador nuevo empieza desde ahora.
    reset_flow_store(backend)
    clock.value = _local(14, 13, 10)
    restarted = _scheduler(clock, downloader)
    assert restarted.tick() == []
    clock.value = _local(14, 14, 0, 5)
    assert len(restarted.tick()) == 1
    assert get_flow_store().get(flow.id) is not None


def test_a_scheduled_run_that_does_not_validate_is_recorded_as_an_error(api, downloader):
    flow = _flow()  # origen sintético: la caja no valida
    clock = Clock(_local(14, 10, 20))
    scheduler = _scheduler(clock, downloader)
    scheduler.tick()
    clock.value = _local(14, 11, 0, 5)
    [launched] = scheduler.tick()
    run = get_run_store().get(flow.id, launched).snapshot()
    assert run["status"] == "error" and run["origin"] == "programada"
    assert any(note.startswith("download_needs_real_origin:") for note in run["notes"])
    assert downloader.started == []
    assert run["finished_at"] is not None


def test_the_listing_shows_the_next_scheduled_run(api, real_origin, downloader, monkeypatch):
    flow = _flow()
    plain = _flow(_graph({"type": "desactivada"}))
    clock = Clock(_local(14, 10, 20))
    scheduler = _scheduler(clock, downloader)
    monkeypatch.setattr("app.flows.scheduler._scheduler", scheduler)
    assert get_scheduler() is scheduler
    scheduler.tick()
    items = {item["id"]: item for item in api.get("/api/flows").json()["items"]}
    assert datetime.fromisoformat(items[flow.id]["next_run"]) == _local(14, 11, 0)
    assert items[plain.id]["next_run"] is None


def test_manual_runs_say_so_in_the_history(api):
    flow_payload = api.post("/api/flows", json={"name": "Manual"}).json()
    api.put(f"/api/flows/{flow_payload['id']}/graph", json=graph(
        [node("tmp-s", "sampling", SAMPLING), node("tmp-p", "prompt", PROMPT_TEXT, x=300),
         node("tmp-o", "output", OUTPUT_TABLE, x=600)], [edge("tmp-s", "tmp-p"), edge("tmp-p", "tmp-o")]))
    run = api.post(f"/api/flows/{flow_payload['id']}/runs").json()
    history = api.get(f"/api/flows/{flow_payload['id']}/runs").json()["items"]
    assert history[0]["origin"] == "manual"
    assert api.get(f"/api/flows/{flow_payload['id']}/runs/{run['id']}").json()["notes"] == []


def test_a_view_only_role_cannot_schedule_nor_run(api, reader):
    flow = api.post("/api/flows", json={"name": "Programado"}).json()
    assert api.put(f"/api/flows/{flow['id']}/graph", json=_graph(), headers=reader).status_code == 403
    assert api.post(f"/api/flows/{flow['id']}/runs", headers=reader).status_code == 403
    assert api.get("/api/flows", headers=reader).status_code == 200

