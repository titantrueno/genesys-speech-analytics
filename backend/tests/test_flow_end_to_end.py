"""Ejecución end-to-end de un flujo con caja «Genesys download» (FE017, T4; criterios 3, 4, 5, 6, 7 y 19).

El servicio de ingesta se sustituye por un descargador falso: la caja lanza la descarga, sigue sus contadores, espera a
que termine y pasa al Sampling solo el subconjunto de la descarga. Si no trae conversaciones, el resto queda `omitido`.
"""
import copy
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.config.store import get_config
from app.data.store import get_dataset
from app.flows import rules, runs
from app.flows.downloader import DownloadRejected, DownloaderUnavailable, get_downloader
from app.flows.model import parse_graph
from app.flows.prompting import MockPromptRunner
from app.flows.runs import FlowExecutor, get_run_store
from app.flows.store import get_flow_store
from app.main import app
from app.routers.flows import get_prompt_runner
from tests.flow_fixtures import OUTPUT_TABLE, PROMPT_TEXT, SAMPLING, edge, graph, node
from tests.test_flow_runs import detail, flow_with, run
from tests.test_flows_api import reader  # noqa: F401  (fixture)

DOWNLOAD = {"interval": {"type": "relativo", "unit": "hoy"}, "channels": ["voz", "chat"], "overwrite": True}


def _graph(sampling: dict | None = None, download: dict | None = None) -> dict:
    return graph(
        [node("tmp-d", "descarga", DOWNLOAD if download is None else download),
         node("tmp-s", "sampling", {"size": "all"} if sampling is None else sampling, x=300),
         node("tmp-p", "prompt", PROMPT_TEXT, x=600), node("tmp-o", "output", OUTPUT_TABLE, x=900)],
        [edge("tmp-d", "tmp-s"), edge("tmp-s", "tmp-p"), edge("tmp-p", "tmp-o")])


class FakeDownloader:
    """Descarga que pasa por `en_curso` con contadores crecientes y termina con el estado y el subconjunto pedidos."""

    def __init__(self, subset: list[str], final: str = "completada", steps: int = 3, error: str | None = None):
        self.subset_ids, self.final, self.steps, self.error = subset, final, steps, error
        self.started: list[dict] = []
        self.polls = 0
        self.fail_on_poll: int | None = None
        self.reject: str | None = None
        self.up = True

    def available(self) -> bool:
        return self.up

    def start(self, **kwargs) -> dict:
        if self.reject:
            raise DownloadRejected(self.reject)
        self.started.append(kwargs)
        return self._run("pendiente", 0)

    def status(self, run_id: str) -> dict:
        self.polls += 1
        if self.fail_on_poll is not None and self.polls >= self.fail_on_poll:
            raise DownloaderUnavailable("The ingestion service is not available")
        done = self.polls >= self.steps
        return self._run(self.final if done else "en_curso", min(self.polls, self.steps))

    def subset(self, run_id: str) -> list[str]:
        return list(self.subset_ids)

    def log(self, run_id: str, params: dict) -> httpx.Response:
        if params.get("format") == "text":
            return httpx.Response(200, text="log en texto\n", headers={"content-disposition": "attachment; x"})
        return httpx.Response(200, json={"items": [{"id": 1, "level": "info", "stage": "start", "message": "Run"}]})

    def _run(self, status: str, step: int) -> dict:
        inserted = round(len(self.subset_ids) * step / self.steps)
        return {"id": "1RN-00000000-0000-4000-8000-000000000001", "status": status,
                "error": self.error if status == "error" else None,
                "counters": {"found": len(self.subset_ids), "downloaded": inserted, "inserted": inserted,
                             "updated": 0, "skipped": 0, "skipped_existing": 0, "errors": 0}}


class CountingRunner(MockPromptRunner):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def run(self, *args, **kwargs):
        self.calls += 1
        return super().run(*args, **kwargs)


@pytest.fixture
def real_origin(monkeypatch):
    # La validación exige datos reales; el dataset sintético hace de base (el subconjunto son sus identificadores).
    monkeypatch.setattr(rules, "active_origin", lambda: "real")
    monkeypatch.setattr(runs, "DOWNLOAD_POLL_S", 0)


def _subset(count: int = 5) -> list[str]:
    period = copy.deepcopy(SAMPLING["query"])
    from app.query.engine import run_query
    from app.query.model import parse_query
    return [c.id for c in run_query(parse_query(period), get_dataset())[:count]]


@pytest.fixture
def downloader():
    fake = FakeDownloader(_subset())
    app.dependency_overrides[get_downloader] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_downloader, None)


@pytest.fixture
def counting():
    runner = CountingRunner()
    app.dependency_overrides[get_prompt_runner] = lambda: runner
    yield runner
    app.dependency_overrides.pop(get_prompt_runner, None)


def _nodes(flow: dict) -> dict[str, str]:
    return {n["type"]: n["id"] for n in flow["graph"]["nodes"]}


def test_the_box_downloads_and_the_sampling_only_sees_its_subset(api, real_origin, downloader):
    flow = flow_with(api, _graph())
    final = detail(api, flow, run(api, flow)["id"])
    ids = _nodes(flow)
    assert final["status"] == "ok", final
    assert {k: final["nodes"][v]["status"] for k, v in ids.items()} == {
        "descarga": "ok", "sampling": "ok", "prompt": "ok", "output": "ok"}
    assert final["sample_size"] == len(downloader.subset_ids) == 5
    rows = next(iter(final["outputs"].values()))["result"]["rows"]
    assert sorted(r["conversation"]["id"] for r in rows) == sorted(downloader.subset_ids)
    assert len(get_dataset()) > 5  # hay más conversaciones del mismo periodo y no entran
    assert final["download"]["run_id"] == "1RN-00000000-0000-4000-8000-000000000001"
    assert final["download"]["status"] == "completada"
    assert final["download"]["counters"]["inserted"] == 5
    assert final["nodes"][ids["descarga"]]["processed"] == final["nodes"][ids["descarga"]]["total"] == 5


def test_the_download_gets_the_box_configuration_and_the_resolved_interval(api, real_origin, downloader):
    flow = flow_with(api, _graph())
    before = datetime.now(ZoneInfo(get_config().general.timezone))
    run(api, flow)
    [started] = downloader.started
    tz = get_config().general.timezone
    assert started["insight_flow_id"] == flow["id"]
    assert started["channels"] == ["voz", "chat"] and started["overwrite"] is True
    assert started["origin"] == "manual" and started["timezone"] == tz
    assert started["user"]["id"] and started["user"]["name"]
    assert started["interval_from"] == before.replace(hour=0, minute=0, second=0, microsecond=0)
    assert started["interval_from"] <= started["interval_to"]


def test_the_sampling_conditions_still_apply_to_the_subset(api, real_origin, downloader):
    channel = next(c.channel for c in get_dataset() if c.id == downloader.subset_ids[0])
    expected = [cid for cid in downloader.subset_ids
                if next(c.channel for c in get_dataset() if c.id == cid) == channel]
    sampling = {"query": {"root": {"op": "and", "conditions": [
        {"field": "channel", "operator": "is", "value": channel}]}}, "size": "all"}
    flow = flow_with(api, _graph(sampling))
    final = detail(api, flow, run(api, flow)["id"])
    rows = next(iter(final["outputs"].values()))["result"]["rows"]
    assert sorted(r["conversation"]["id"] for r in rows) == sorted(expected)


def test_no_other_node_starts_before_the_download_ends():
    fake = FakeDownloader(_subset(), steps=4)
    flow = get_flow_store().create(_user(), "Flujo", parse_graph(_graph()))
    seen = []

    def watch(r):
        snap = r.snapshot()
        box = next(n for n in snap["graph"]["nodes"] if n["type"] == "descarga")["id"]
        seen.append((snap["nodes"][box]["status"], snap["nodes"][box]["processed"],
                     {k: v["status"] for k, v in snap["nodes"].items() if k != box}))
    the_run = get_run_store().create(flow, _user())
    FlowExecutor(MockPromptRunner(), 0, on_step=watch, downloader=fake, poll_s=0).execute(the_run)
    running = [s for s in seen if s[0] == "en_curso"]
    assert len(running) >= 3
    assert all(set(others.values()) == {"pendiente"} for _, _, others in running)
    processed = [p for _, p, _ in seen]
    assert processed == sorted(processed)


def test_a_failed_download_stops_the_flow(api, real_origin, downloader):
    downloader.final, downloader.error = "error", "Invalid Genesys credentials"
    flow = flow_with(api, _graph())
    final = detail(api, flow, run(api, flow)["id"])
    ids = _nodes(flow)
    assert final["status"] == "error"
    assert final["nodes"][ids["descarga"]]["status"] == "error"
    assert "Invalid Genesys credentials" in final["nodes"][ids["descarga"]]["message"]
    assert {final["nodes"][ids[t]]["status"] for t in ("sampling", "prompt", "output")} == {"pendiente"}


def test_a_download_without_conversations_skips_the_rest_without_calling_the_llm(api, real_origin, downloader,
                                                                                  counting):
    downloader.subset_ids = []
    flow = flow_with(api, _graph())
    final = detail(api, flow, run(api, flow)["id"])
    ids = _nodes(flow)
    assert final["status"] == "ok"
    assert final["nodes"][ids["descarga"]]["status"] == "ok"
    for t in ("sampling", "prompt", "output"):
        assert final["nodes"][ids[t]]["status"] == "omitido"
        assert final["nodes"][ids[t]]["message"] == "The download returned no conversations"
    assert counting.calls == 0 and final["outputs"] == {}


def test_the_ingestion_service_falling_mid_run_ends_in_error(api, real_origin, downloader):
    downloader.fail_on_poll = 2
    flow = flow_with(api, _graph())
    final = detail(api, flow, run(api, flow)["id"])
    box = _nodes(flow)["descarga"]
    assert final["status"] == "error"
    assert final["nodes"][box]["message"] == "The ingestion service is not available"


def test_a_rejected_download_ends_in_error(api, real_origin, downloader):
    downloader.reject = "This flow is already downloading"
    flow = flow_with(api, _graph())
    final = detail(api, flow, run(api, flow)["id"])
    assert final["nodes"][_nodes(flow)["descarga"]]["message"] == "This flow is already downloading"


def test_validation_fails_when_the_ingestion_service_is_down(api, real_origin, downloader):
    downloader.up = False
    issues = api.post("/api/flows/validate", json=_graph()).json()["issues"]
    assert {"code": "ingestion_unavailable", "message": "The ingestion service is not available.",
            "node_id": "tmp-d"} in issues
    flow = flow_with(api, _graph())
    response = api.post(f"/api/flows/{flow['id']}/runs")
    assert response.status_code == 422
    assert downloader.started == []
    # Un flujo sin caja no pregunta por la ingesta.
    plain = graph([node("tmp-s", "sampling", SAMPLING), node("tmp-p", "prompt", PROMPT_TEXT),
                   node("tmp-o", "output", OUTPUT_TABLE)], [edge("tmp-s", "tmp-p"), edge("tmp-p", "tmp-o")])
    assert all(i["code"] != "ingestion_unavailable" for i in api.post("/api/flows/validate", json=plain).json()["issues"])


def test_the_download_and_its_log_are_readable_from_the_run(api, real_origin, downloader):
    flow = flow_with(api, _graph())
    run_id = run(api, flow)["id"]
    base = f"/api/flows/{flow['id']}/runs/{run_id}/download"
    status = api.get(base)
    assert status.status_code == 200 and status.json()["status"] == "completada"
    assert api.get(f"{base}/log").json()["items"][0]["stage"] == "start"
    text = api.get(f"{base}/log", params={"format": "text"})
    assert text.status_code == 200 and text.text == "log en texto\n"
    downloader.up = False
    downloader.fail_on_poll = 0
    assert api.get(base).status_code == 503


def test_a_run_without_a_box_has_no_download(api):
    flow = flow_with(api, graph([node("tmp-s", "sampling", SAMPLING), node("tmp-p", "prompt", PROMPT_TEXT),
                                 node("tmp-o", "output", OUTPUT_TABLE)],
                                [edge("tmp-s", "tmp-p"), edge("tmp-p", "tmp-o")]))
    run_id = run(api, flow)["id"]
    assert detail(api, flow, run_id)["download"] is None
    assert api.get(f"/api/flows/{flow['id']}/runs/{run_id}/download").status_code == 404



def _user():
    from app import auth
    return auth.get_store().find_by_email("admin@bancohorizonte.demo")


# --- Casos añadidos en /test ---

def test_behind_the_box_the_sampling_keeps_its_method_and_size(api, real_origin, downloader):
    flow = flow_with(api, _graph({"method": "aleatorio", "size": 2}))
    final = detail(api, flow, run(api, flow)["id"])
    rows = next(iter(final["outputs"].values()))["result"]["rows"]
    assert final["sample_size"] == 2
    assert {r["conversation"]["id"] for r in rows} <= set(downloader.subset_ids)


def test_a_download_with_warnings_lets_the_flow_continue(api, real_origin, downloader):
    downloader.final = "completada_con_avisos"
    flow = flow_with(api, _graph())
    final = detail(api, flow, run(api, flow)["id"])
    assert final["status"] == "ok" and final["download"]["status"] == "completada_con_avisos"
    assert final["sample_size"] == len(downloader.subset_ids)


def test_the_real_data_snapshot_is_refreshed_after_the_download(monkeypatch):
    """Sin una petición HTTP de por medio (ejecución programada), la instantánea de los datos reales solo se recarga si
    el ejecutor abre una «petición» nueva al terminar la descarga y antes del Sampling."""
    events = []
    fake = FakeDownloader(_subset(), steps=1)
    original_subset = fake.subset
    fake.subset = lambda run_id: events.append("subset") or original_subset(run_id)
    monkeypatch.setattr(runs, "begin_request", lambda: events.append("begin_request"))
    import app.flows.runs as runs_module
    original_candidates = runs_module.candidates
    monkeypatch.setattr(runs_module, "candidates",
                        lambda config, subset=None: events.append("sampling") or original_candidates(config, subset))
    flow = get_flow_store().create(_user(), "Flujo", parse_graph(_graph()))
    the_run = get_run_store().create(flow, _user())
    FlowExecutor(MockPromptRunner(), 0, downloader=fake, poll_s=0).execute(the_run)
    assert events == ["subset", "begin_request", "sampling"]


def test_a_view_only_role_reads_the_download_of_a_run(api, real_origin, downloader, reader):
    flow = flow_with(api, _graph())
    run_id = run(api, flow)["id"]
    base = f"/api/flows/{flow['id']}/runs/{run_id}/download"
    assert api.get(base, headers=reader).status_code == 200
    assert api.get(f"{base}/log", headers=reader).status_code == 200
    assert api.post(f"/api/flows/{flow['id']}/runs", headers=reader).status_code == 403


def test_a_download_that_disappears_says_so(api, real_origin, downloader):
    """Si la descarga deja de existir a mitad (se borró el flujo), el nodo no culpa a la ingesta."""
    def gone(run_id):
        raise DownloaderUnavailable(f"The download {run_id} is not available (404)")
    downloader.status = gone
    flow = flow_with(api, _graph())
    final = detail(api, flow, run(api, flow)["id"])
    assert "(404)" in final["nodes"][_nodes(flow)["descarga"]]["message"]
