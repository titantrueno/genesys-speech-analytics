"""Flujos de descarga en el servicio de ingesta (FE011, T5; criterios 13, 14, 15, 16 y 19)."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import psycopg
import pytest
from fastapi.testclient import TestClient

from ingestion.main import create_app
from ingestion.runs import RunExecutor, create_run, get_run
from ingestion.scheduler import Scheduler
from ingestion.settings import Settings
from tests.ingestion_helpers import client_factory, make_fake

pytestmark = pytest.mark.pg
TOKEN = "token-interno-de-prueba"
MADRID = ZoneInfo("Europe/Madrid")
AUTHOR = {"id": "1US-AUTOR", "name": "Autora de prueba"}
USER = {"id": "1US-LANZA", "name": "Quien lanza"}


class Clock:
    def __init__(self, value: datetime):
        self.value = value

    def __call__(self) -> datetime:
        return self.value


def _flow(**changes) -> dict:
    body = {"name": "Descarga diaria", "interval": {"type": "relativo", "unit": "hoy"}, "channels": ["voz", "chat"],
            "schedule": {"type": "desactivada"}, "active": True, "timezone": "Europe/Madrid", "author": AUTHOR}
    body.update(changes)
    return body


@pytest.fixture
def clock():
    # Las 23:00 del 12 de octubre de 2026 en Madrid: «hoy» cubre las conversaciones de las fixtures.
    return Clock(datetime(2026, 10, 12, 23, 0, tzinfo=MADRID))


@pytest.fixture
def fake():
    return make_fake()


@pytest.fixture
def api(pg_url, clock, fake):
    app = create_app(Settings(database_url=pg_url, token=TOKEN), client_factory=client_factory(fake), clock=clock,
                     run_in_background=lambda job: job(), scheduler=False)
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {TOKEN}"
        yield client


def _create(api, **changes) -> dict:
    response = api.post("/download-flows", json=_flow(**changes))
    assert response.status_code == 201, response.text
    return response.json()


# CRUD y validación -----------------------------------------------------------------------------------------------------

def test_create_read_list_update_and_delete(api):
    flow = _create(api)
    assert flow["id"].startswith("1FL-") and flow["author"] == AUTHOR and flow["next_run_at"] is None
    assert api.get(f"/download-flows/{flow['id']}").json() == flow
    assert [f["id"] for f in api.get("/download-flows").json()["items"]] == [flow["id"]]
    updated = api.put(f"/download-flows/{flow['id']}", json={**_flow(name="Otra"), "author": None})
    assert updated.status_code == 200 and updated.json()["name"] == "Otra"
    assert updated.json()["author"] == AUTHOR  # la autoría no cambia al editar
    assert api.delete(f"/download-flows/{flow['id']}").status_code == 204
    assert api.get(f"/download-flows/{flow['id']}").status_code == 404


@pytest.mark.parametrize("flow_id", ["1FL-00000000-0000-4000-8000-000000000000", "no-es-un-id",
                                     "1RN-00000000-0000-4000-8000-000000000000"])
def test_unknown_or_malformed_ids_are_404(api, flow_id):
    assert api.get(f"/download-flows/{flow_id}").status_code == 404
    assert api.post(f"/download-flows/{flow_id}/runs", json={"user": USER}).status_code == 404


@pytest.mark.parametrize("changes, field, message", [
    ({"name": " "}, "name", "The name cannot be empty"),
    ({"name": "x" * 81}, "name", "at most 80"),
    ({"interval": {"type": "relativo", "unit": "horas", "amount": 0}}, "interval", "between 1 and 720"),
    ({"interval": {"type": "relativo", "unit": "horas", "amount": 721}}, "interval", "between 1 and 720"),
    ({"interval": {"type": "relativo", "unit": "dias", "amount": 91}}, "interval", "between 1 and 90"),
    ({"interval": {"type": "relativo", "unit": "hoy", "amount": 3}}, "interval", "take no amount"),
    ({"interval": {"type": "especifico", "from": "2026-10-02T00:00", "to": "2026-10-01T00:00"}}, "interval",
     "before"),
    ({"interval": {"type": "especifico", "from": "2026-06-01T00:00", "to": "2026-10-01T00:00"}}, "interval",
     "90 days"),
    ({"interval": {"type": "especifico", "from": "2026-10-12T08:00", "to": "2026-10-13T08:00"}}, "interval",
     "future"),
    ({"channels": []}, "channels", "at least one channel"),
    ({"channels": ["voz", "email"]}, "channels", ""),
    ({"schedule": {"type": "cada_horas", "hours": 25}}, "schedule", "between 1 and 24"),
    ({"schedule": {"type": "diaria", "time": "25:00"}}, "schedule", "HH:MM"),
    ({"schedule": {"type": "diaria", "time": "07:00"},
      "interval": {"type": "especifico", "from": "2026-10-01T00:00", "to": "2026-10-02T00:00"}}, "schedule",
     "A scheduled download needs a relative interval"),
    ({"timezone": "Marte/Olimpo"}, "timezone", "Zona horaria"),
])
def test_each_rule_answers_422_with_a_message_per_field(api, changes, field, message):
    response = api.post("/download-flows", json=_flow(**changes))
    assert response.status_code == 422
    errors = [e for e in response.json()["detail"] if field in e["loc"]]
    assert errors, response.json()
    assert any(message in e["msg"] for e in errors), errors


def test_a_scheduled_flow_knows_its_next_run(api):
    flow = _create(api, schedule={"type": "cada_horas", "hours": 1})
    assert datetime.fromisoformat(flow["next_run_at"]) == datetime(2026, 10, 13, 0, 0, tzinfo=MADRID)
    inactive = api.put(f"/download-flows/{flow['id']}", json=_flow(schedule={"type": "cada_horas", "hours": 1},
                                                                    active=False)).json()
    assert inactive["next_run_at"] is None


# Ejecución manual, historial y log -------------------------------------------------------------------------------------

def test_a_manual_run_resolves_the_interval_and_records_who_launched_it(api):
    flow = _create(api)
    response = api.post(f"/download-flows/{flow['id']}/runs", json={"user": USER})
    assert response.status_code == 202
    accepted = response.json()
    assert accepted["origin"] == "manual" and accepted["started_by"] == USER
    assert accepted["interval"] == {"from": "2026-10-11T22:00:00+00:00", "to": "2026-10-12T21:00:00+00:00"}
    run = api.get(f"/download-flows/{flow['id']}/runs/{accepted['id']}").json()
    assert run["status"] == "completada_con_avisos" and run["counters"]["inserted"] == 10


def test_a_second_run_while_one_is_active_is_409(api, pg_url):
    flow = _create(api)
    create_run(pg_url, flow["id"], "manual", datetime(2026, 10, 12, tzinfo=timezone.utc),
               datetime(2026, 10, 13, tzinfo=timezone.utc), ["voz"])
    response = api.post(f"/download-flows/{flow['id']}/runs", json={"user": USER})
    assert response.status_code == 409 and "already running" in response.json()["detail"]


def test_history_is_newest_first_and_the_flow_shows_its_last_run(api):
    flow = _create(api)
    first = api.post(f"/download-flows/{flow['id']}/runs", json={"user": USER}).json()
    second = api.post(f"/download-flows/{flow['id']}/runs", json={"user": USER}).json()
    history = api.get(f"/download-flows/{flow['id']}/runs").json()["items"]
    assert [r["id"] for r in history] == [second["id"], first["id"]]
    assert {"origin", "interval", "counters", "duration_s", "status", "created_at"} <= history[0].keys()
    listed = api.get("/download-flows").json()["items"][0]
    # La segunda omite las conversaciones que ya cargó la primera (sin «Sobrescribir», FE013): no hay avisos.
    assert listed["last_run"]["id"] == second["id"] and listed["last_run"]["status"] == "completada"


def test_only_the_200_most_recent_runs_are_kept(api, pg_url):
    flow = _create(api)
    empty = make_fake([])
    for _ in range(203):
        run_id = create_run(pg_url, flow["id"], "manual", datetime(2026, 10, 12, tzinfo=timezone.utc),
                            datetime(2026, 10, 13, tzinfo=timezone.utc), ["voz"])
        RunExecutor(pg_url, client_factory(empty)).execute(run_id)
    history = api.get(f"/download-flows/{flow['id']}/runs").json()["items"]
    assert len(history) == 200 and history[0]["id"] == run_id


def test_the_log_is_paged_filtered_and_downloadable(api):
    flow = _create(api)
    run = api.post(f"/download-flows/{flow['id']}/runs", json={"user": USER}).json()
    url = f"/download-flows/{flow['id']}/runs/{run['id']}/log"
    entries = api.get(url).json()["items"]
    assert len(entries) > 5
    assert [e["id"] for e in api.get(url, params={"after": entries[1]["id"]}).json()["items"]] == \
        [e["id"] for e in entries[2:]]
    assert {e["level"] for e in api.get(url, params={"level": "aviso"}).json()["items"]} == {"aviso"}
    text = api.get(url, params={"format": "text"})
    assert text.headers["content-type"].startswith("text/plain")
    assert text.headers["content-disposition"].startswith("attachment")
    lines = text.text.strip().splitlines()
    assert len(lines) == len(entries) and "[aviso]" in text.text and run["id"] in text.headers["content-disposition"]


def test_deleting_a_flow_with_an_active_run_is_409(api, pg_url):
    flow = _create(api)
    create_run(pg_url, flow["id"], "manual", datetime(2026, 10, 12, tzinfo=timezone.utc),
               datetime(2026, 10, 13, tzinfo=timezone.utc), ["voz"])
    assert api.delete(f"/download-flows/{flow['id']}").status_code == 409


# Persistencia y reinicios ----------------------------------------------------------------------------------------------

def test_flows_runs_and_logs_survive_a_restart(api, pg_url, clock, fake):
    flow = _create(api)
    run = api.post(f"/download-flows/{flow['id']}/runs", json={"user": USER}).json()
    log = api.get(f"/download-flows/{flow['id']}/runs/{run['id']}/log").json()
    restarted = create_app(Settings(database_url=pg_url, token=TOKEN), client_factory=client_factory(fake),
                           clock=clock, scheduler=False)
    with TestClient(restarted, headers={"Authorization": f"Bearer {TOKEN}"}) as again:
        assert again.get(f"/download-flows/{flow['id']}").json() == api.get(f"/download-flows/{flow['id']}").json()
        assert again.get(f"/download-flows/{flow['id']}/runs/{run['id']}/log").json() == log


def test_a_run_interrupted_by_a_restart_ends_in_error(api, pg_url, clock, fake):
    flow = _create(api)
    run_id = create_run(pg_url, flow["id"], "manual", datetime(2026, 10, 12, tzinfo=timezone.utc),
                        datetime(2026, 10, 13, tzinfo=timezone.utc), ["voz"])
    with TestClient(create_app(Settings(database_url=pg_url, token=TOKEN), client_factory=client_factory(fake),
                               clock=clock, scheduler=False)):
        pass
    run = get_run(pg_url, run_id)
    assert run["status"] == "error" and "restart" in run["error"]
    assert api.post(f"/download-flows/{flow['id']}/runs", json={"user": USER}).status_code == 202


# Programador -----------------------------------------------------------------------------------------------------------

def _scheduler(pg_url, clock, fake, started: list) -> Scheduler:
    def submit(job):
        started.append(job)
    return Scheduler(pg_url, client_factory(fake), clock=clock, run_in_background=submit)


def _runs(pg_url) -> list[tuple]:
    with psycopg.connect(pg_url) as conn:
        return conn.execute("SELECT origin, status, interval_from, interval_to, notes FROM download_run "
                            "ORDER BY created_at").fetchall()


def test_an_hourly_flow_runs_once_per_hour_and_not_twice(api, pg_url, clock, fake):
    clock.value = datetime(2026, 10, 12, 10, 15, tzinfo=MADRID)
    _create(api, schedule={"type": "cada_horas", "hours": 1}, interval={"type": "relativo", "unit": "horas",
                                                                         "amount": 1})
    started: list = []
    scheduler = _scheduler(pg_url, clock, fake, started)
    for minute in [59, 60, 60.5, 75, 119, 120, 121]:
        clock.value = datetime(2026, 10, 12, 10, 0, tzinfo=MADRID) + timedelta(minutes=minute)
        scheduler.tick()
        while started:
            started.pop(0)()  # la ejecución termina antes del siguiente tic
    runs = _runs(pg_url)
    assert [r[0] for r in runs] == ["programada", "programada"]
    assert [r[2].astimezone(MADRID).hour for r in runs] == [10, 11]  # «la última hora» desde las 11:00 y las 12:00


def test_an_inactive_flow_is_not_scheduled(api, pg_url, clock, fake):
    clock.value = datetime(2026, 10, 12, 10, 15, tzinfo=MADRID)
    _create(api, schedule={"type": "cada_horas", "hours": 1}, active=False)
    started: list = []
    clock.value = datetime(2026, 10, 12, 12, 0, tzinfo=MADRID)
    _scheduler(pg_url, clock, fake, started).tick()
    assert started == [] and _runs(pg_url) == []


def test_a_scheduled_run_is_skipped_while_another_is_active_and_noted_in_the_next(api, pg_url, clock, fake):
    clock.value = datetime(2026, 10, 12, 10, 15, tzinfo=MADRID)
    flow = _create(api, schedule={"type": "cada_horas", "hours": 1})
    blocking = create_run(pg_url, flow["id"], "manual", datetime(2026, 10, 12, tzinfo=timezone.utc),
                          datetime(2026, 10, 13, tzinfo=timezone.utc), ["voz"])
    started: list = []
    scheduler = _scheduler(pg_url, clock, fake, started)
    clock.value = datetime(2026, 10, 12, 11, 0, tzinfo=MADRID)
    scheduler.tick()
    assert started == []  # omitida: la manual sigue activa
    RunExecutor(pg_url, client_factory(make_fake([]))).execute(blocking)
    clock.value = datetime(2026, 10, 12, 12, 0, tzinfo=MADRID)
    scheduler.tick()
    started.pop()()
    notes = _runs(pg_url)[-1][4]
    assert len(notes) == 1 and "11:00" in notes[0]
    run_id = api.get(f"/download-flows/{flow['id']}/runs").json()["items"][0]["id"]
    log = api.get(f"/download-flows/{flow['id']}/runs/{run_id}/log").json()["items"]
    assert any("11:00" in e["message"] and e["level"] == "aviso" for e in log)


def test_runs_missed_while_the_service_was_down_are_not_recovered(api, pg_url, clock, fake):
    clock.value = datetime(2026, 10, 12, 10, 15, tzinfo=MADRID)
    _create(api, schedule={"type": "cada_horas", "hours": 1})
    clock.value = datetime(2026, 10, 12, 14, 20, tzinfo=MADRID)  # el servicio estuvo parado de 10:15 a 14:20
    with TestClient(create_app(Settings(database_url=pg_url, token=TOKEN), client_factory=client_factory(fake),
                               clock=clock, scheduler=False), headers={"Authorization": f"Bearer {TOKEN}"}) as again:
        next_run = again.get("/download-flows").json()["items"][0]["next_run_at"]
        assert datetime.fromisoformat(next_run) == datetime(2026, 10, 12, 15, 0, tzinfo=MADRID)
    started: list = []
    _scheduler(pg_url, clock, fake, started).tick()
    assert started == []


def test_two_simultaneous_launches_start_a_single_run(api, pg_url, clock, fake):
    import threading

    from ingestion.runs import RunAlreadyActive
    from ingestion.scheduler import launch

    flow = _create(api)
    barrier, outcomes = threading.Barrier(2), []

    def attempt():
        barrier.wait()
        try:
            outcomes.append(launch(pg_url, flow["id"], "manual", None, clock(), client_factory(fake), lambda job: None))
        except RunAlreadyActive:
            outcomes.append("409")

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert sorted(o == "409" for o in outcomes) == [False, True]
    assert len(api.get(f"/download-flows/{flow['id']}/runs").json()["items"]) == 1


def test_a_failing_tick_is_logged_and_the_scheduler_keeps_going(pg_url, caplog):
    import logging

    scheduler = Scheduler("postgresql://nadie@127.0.0.1:1/nada?connect_timeout=1", client_factory(make_fake()))
    with caplog.at_level(logging.ERROR, logger="ingestion"):
        assert scheduler.safe_tick() == []
    assert any("programador" in record.getMessage() for record in caplog.records)
