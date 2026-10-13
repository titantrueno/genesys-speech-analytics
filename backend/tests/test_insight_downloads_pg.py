"""Descargas lanzadas por la caja «Genesys download» de un flujo de insights (FE017, T1; criterios 4, 5, 6 y 19).

Una descarga de caja cuelga del flujo de insights (no de un flujo de descarga) y guarda su subconjunto: las
conversaciones que insertó o actualizó. Las que ya existían sin «Sobrescribir» y las que fallaron no forman parte de él.
"""
import json
import random

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import ids
from ingestion import db
from ingestion.main import create_app
from ingestion.settings import Settings
from tests.ingestion_helpers import DAY_END, DAY_START, SECRET, client_factory, create_flow, fixture, fixtures, make_fake

pytestmark = pytest.mark.pg
TOKEN = "token-interno-de-prueba"
USER = {"id": "1US-PRUEBA", "name": "Admin de prueba"}


def _insight_flow(pg_url: str) -> str:
    flow_id = ids.new_id(ids.FLOW, random.SystemRandom())
    with psycopg.connect(pg_url) as conn:
        db.migrate(conn)
        conn.execute("INSERT INTO insight_flow (id, name, author_id, author_name, graph, created_at, updated_at) "
                     "VALUES (%s, 'Flujo con caja', '1US-PRUEBA', 'Admin de prueba', %s, now(), now())",
                     (flow_id, json.dumps({"version": 1, "nodes": [], "edges": []})))
    return flow_id


def _api(pg_url, fake, run_in_background=lambda job: job()):
    app = create_app(Settings(database_url=pg_url, token=TOKEN), client_factory=client_factory(fake),
                     run_in_background=run_in_background, scheduler=False)
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {TOKEN}"
    return client


def _body(flow_id: str, overwrite: bool = False) -> dict:
    return {"insight_flow_id": flow_id, "from": DAY_START.isoformat(), "to": DAY_END.isoformat(),
            "channels": ["voz", "chat"], "overwrite": overwrite, "origin": "manual", "timezone": "Europe/Madrid",
            "user": USER}


def _launch(api, flow_id: str, overwrite: bool = False) -> dict:
    response = api.post("/insight-downloads", json=_body(flow_id, overwrite))
    assert response.status_code == 202, response.text
    run = api.get(f"/insight-downloads/{response.json()['id']}")
    assert run.status_code == 200, run.text
    return run.json()


def _subset(api, run_id: str) -> list[str]:
    response = api.get(f"/insight-downloads/{run_id}/conversations")
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _conversation_ids(pg_url, genesys_ids: list[str] | None = None) -> set[str]:
    with psycopg.connect(pg_url) as conn:
        rows = conn.execute("SELECT id, genesys_id FROM conversation").fetchall()
    return {cid for cid, gid in rows if genesys_ids is None or gid in genesys_ids}


def test_a_box_download_belongs_to_the_insight_flow_and_its_subset_is_what_it_loaded(pg_url):
    flow_id = _insight_flow(pg_url)
    with _api(pg_url, make_fake()) as api:
        run = _launch(api, flow_id)
        assert run["status"] in ("completada", "completada_con_avisos")
        assert run["insight_flow_id"] == flow_id and run["flow_id"] is None
        assert run["origin"] == "manual" and run["overwrite"] is False
        subset = _subset(api, run["id"])
    assert set(subset) == _conversation_ids(pg_url)
    assert len(subset) == run["counters"]["inserted"] + run["counters"]["updated"] > 0
    assert all(ids.is_valid(cid, ids.CONVERSATION) for cid in subset)


def test_only_new_conversations_enter_the_subset_without_overwrite(pg_url):
    flow_id = _insight_flow(pg_url)
    first = [fixture("37dcbccf"), fixture("8d29170a")]
    with _api(pg_url, make_fake(first)) as api:
        _launch(api, flow_id)
    before = _conversation_ids(pg_url)
    with _api(pg_url, make_fake()) as api:
        run = _launch(api, flow_id)
        subset = set(_subset(api, run["id"]))
    assert subset == _conversation_ids(pg_url) - before
    assert len(subset) == len(fixtures()) - len(first)


def test_repeating_the_download_gives_an_empty_subset_unless_it_overwrites(pg_url):
    flow_id = _insight_flow(pg_url)
    with _api(pg_url, make_fake()) as api:
        _launch(api, flow_id)
        again = _launch(api, flow_id)
        assert _subset(api, again["id"]) == []
        overwritten = _launch(api, flow_id, overwrite=True)
        assert set(_subset(api, overwritten["id"])) == _conversation_ids(pg_url)
        assert overwritten["counters"]["updated"] == len(_conversation_ids(pg_url))


def test_a_conversation_that_fails_is_not_in_the_subset(pg_url):
    flow_id = _insight_flow(pg_url)
    fake = make_fake()
    failing = fixture("8d29170a").id
    fake.fail("GET", f"/api/v2/speechandtextanalytics/conversations/{failing}", *[503] * 4)
    with _api(pg_url, fake) as api:
        run = _launch(api, flow_id)
        subset = set(_subset(api, run["id"]))
    assert run["counters"]["errors"] == 1
    assert subset == _conversation_ids(pg_url)
    assert not _conversation_ids(pg_url, [failing])


def test_one_active_download_per_box(pg_url):
    flow_id = _insight_flow(pg_url)
    queued = []
    with _api(pg_url, make_fake(), run_in_background=queued.append) as api:
        assert api.post("/insight-downloads", json=_body(flow_id)).status_code == 202
        second = api.post("/insight-downloads", json=_body(flow_id))
        assert second.status_code == 409
        # Otro flujo sí puede descargar a la vez.
        assert api.post("/insight-downloads", json=_body(_insight_flow(pg_url))).status_code == 202


def test_the_log_is_readable_and_has_no_secrets(pg_url):
    flow_id = _insight_flow(pg_url)
    fake = make_fake()
    with _api(pg_url, fake) as api:
        run = _launch(api, flow_id)
        log = api.get(f"/insight-downloads/{run['id']}/log").json()["items"]
        text = api.get(f"/insight-downloads/{run['id']}/log", params={"format": "text"}).text
        outputs = [json.dumps(run), json.dumps(log), text, json.dumps(_subset(api, run["id"]))]
    assert {e["stage"] for e in log} >= {"start", "authentication", "search", "load"}
    assert "Europe/Madrid" in log[0]["message"]
    for secret in [SECRET, *fake.issued_tokens]:
        assert all(secret not in output for output in outputs)


def test_unknown_runs_and_download_flow_runs_are_not_box_downloads(pg_url):
    flow_id = _insight_flow(pg_url)
    with _api(pg_url, make_fake()) as api:
        assert api.get(f"/insight-downloads/{ids.new_id(ids.RUN, random.SystemRandom())}").status_code == 404
        assert api.get("/insight-downloads/no-es-un-id/conversations").status_code == 404
        download_flow = create_flow(pg_url)
        started = api.post(f"/download-flows/{download_flow}/runs", json={"user": USER})
        assert started.status_code == 202, started.text
        assert api.get(f"/insight-downloads/{started.json()['id']}").status_code == 404
        # La caja exige un flujo de insights que exista y datos válidos.
        missing = _body(ids.new_id(ids.FLOW, random.SystemRandom()))
        assert api.post("/insight-downloads", json=missing).status_code == 404
        assert api.post("/insight-downloads", json={**_body(flow_id), "channels": []}).status_code == 422
        assert api.post("/insight-downloads", json={**_body(flow_id), "origin": "otra"}).status_code == 422
        reversed_ = {**_body(flow_id), "from": DAY_END.isoformat(), "to": DAY_START.isoformat()}
        assert api.post("/insight-downloads", json=reversed_).status_code == 422


def test_without_the_internal_token_the_routes_answer_401(pg_url):
    flow_id = _insight_flow(pg_url)
    with _api(pg_url, make_fake()) as api:
        api.headers.pop("Authorization")
        assert api.post("/insight-downloads", json=_body(flow_id)).status_code == 401


def test_deleting_the_insight_flow_deletes_its_downloads(pg_url):
    flow_id = _insight_flow(pg_url)
    with _api(pg_url, make_fake()) as api:
        run = _launch(api, flow_id)
        assert api.delete(f"/insight-flows/{flow_id}").status_code == 204
        assert api.get(f"/insight-downloads/{run['id']}").status_code == 404
    with psycopg.connect(pg_url) as conn:
        assert conn.execute("SELECT count(*) FROM run_log WHERE run_id = %s", (run["id"],)).fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM download_run_conversation").fetchone()[0] == 0


def test_a_download_run_belongs_to_exactly_one_kind_of_flow(pg_url):
    flow_id = _insight_flow(pg_url)
    download_flow = create_flow(pg_url)
    insert = ("INSERT INTO download_run (id, flow_id, insight_flow_id, origin, status, interval_from, interval_to, "
              "channels) VALUES (%s, %s, %s, 'manual', 'completada', %s, %s, %s)")
    for owners in ((None, None), (download_flow, flow_id)):
        with psycopg.connect(pg_url) as conn, pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(insert, (ids.new_id(ids.RUN, random.SystemRandom()), *owners, DAY_START, DAY_END, ["voz"]))
