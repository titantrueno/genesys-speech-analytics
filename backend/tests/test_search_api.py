import random
import time
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.data.catalog import MAIN_TOPICS, QUEUE_IDS
from app.data.store import conversation_index, get_dataset, reference_date
from app.main import app
from app.text import normalize_text
from app.routers import search as search_router
from app.search.engine import Fragment, Hit
from app.search.synonyms import SYNONYMS
from tests.search_relevance import LABELLED_QUERIES, PARAPHRASE_PAIRS

URL = "/api/search/semantic"
REF = reference_date()
FULL = {"from": (REF - timedelta(days=90)).isoformat(), "to": (REF - timedelta(days=1)).isoformat()}


def search(api, q, **params):
    response = api.get(URL, params={"q": q, **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_reference_date_differs_from_today():
    # Lección de FE001: con la fecha de hoy los errores de periodo pasan desapercibidos.
    assert REF != date.today()


# --- Forma de la respuesta ----------------------------------------------------------------------

def test_result_shape_metadata_turns_and_expansions(api):
    body = search(api, "me han cobrado algo que no he comprado", **FULL)
    assert body["query"] == "me han cobrado algo que no he comprado"
    assert "no reconozco" in body["expansions"]
    assert body["period"] == FULL
    assert body["total"] >= len(body["results"]) > 0
    result = body["results"][0]
    conv = conversation_index()[result["conversation_id"]]
    assert result["conversation_id"].startswith("1CO-")
    assert 0 < result["score"] <= 1
    assert result["start_turn"] == result["turns"][0]["index"]
    assert result["end_turn"] == result["turns"][-1]["index"]
    for turn in result["turns"]:
        assert turn["text"] == conv.turns[turn["index"]].text
        assert turn["speaker"] == conv.turns[turn["index"]].speaker != "sistema"
    meta = result["conversation"]
    assert meta["started_at"] == conv.started_at.isoformat()
    assert (meta["channel"], meta["queue_id"], meta["queue"]) == (conv.channel, conv.queue_id, conv.queue)
    assert (meta["main_topic"], meta["main_topic_label"]) == \
        (conv.analysis.main_topic, MAIN_TOPICS[conv.analysis.main_topic].name)
    assert (meta["summary"], meta["sentiment"]) == (conv.analysis.summary, conv.analysis.sentiment)


def test_highlights_exist_literally_in_the_fragment(api):
    body = search(api, "tengo un cargo que no reconozco en la tarjeta", **FULL)
    for result in body["results"]:
        text = "\n".join(t["text"] for t in result["turns"])
        assert result["highlights"], result
        for term in result["highlights"]:
            assert term in text
            assert len(term) >= 3
    top = body["results"][0]
    assert any(normalize_text(word).startswith("recono") for word in top["highlights"])  # «reconozco», «reconocido»…
    customer_text = " ".join(t["text"] for t in top["turns"] if t["speaker"] == "cliente")
    assert any(word in customer_text for word in top["highlights"])  # criterio 18: habla el cliente


def test_highlights_include_expansion_terms_and_inflections(api):
    body = search(api, "he extraviado la visa, inutilízala", **FULL)
    words = {normalize_text(t) for r in body["results"] for t in r["highlights"]}
    assert "tarjeta" in words  # por la expansión de «visa»
    assert words & {"bloquear", "bloqueo", "bloqueada", "bloquearla"}


def test_results_are_sorted_and_rounded(api):
    results = search(api, "el cajero no me dio el dinero", group="fragment", limit=100, **FULL)["results"]
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert all(round(s, 4) == s for s in scores)


# --- Agrupación, umbral y límite ----------------------------------------------------------------

def test_group_by_conversation_scores_each_conversation_by_its_best_fragment(api):
    q = "quiero cerrar la cuenta y cancelar las tarjetas"
    grouped = search(api, q, limit=100, **FULL)
    fragments = search(api, q, group="fragment", limit=100, **FULL)
    ids = [r["conversation_id"] for r in grouped["results"]]
    assert len(ids) == len(set(ids))
    assert fragments["total"] > grouped["total"]
    engine = search_router.get_search_engine()
    for r in grouped["results"]:
        own = [h for h in engine.search(q) if h.fragment.conversation_id == r["conversation_id"]]
        assert r["score"] == round(own[0].score, 4)
        representative = max(own, key=lambda h: h.focus)
        assert (r["start_turn"], r["end_turn"]) == (representative.fragment.start_turn, representative.fragment.end_turn)


def test_min_score_filters_and_total_counts_before_limit(api):
    q = "no puedo entrar en la app"
    everything = search(api, q, group="fragment", limit=100, **FULL)
    threshold = everything["results"][20]["score"]
    filtered = search(api, q, group="fragment", limit=5, min_score=threshold, **FULL)
    assert len(filtered["results"]) == 5
    assert filtered["total"] >= 21
    assert all(r["score"] >= threshold for r in filtered["results"])
    assert search(api, q, min_score=1, **FULL)["total"] == 0


def test_default_limit_is_twenty(api):
    assert len(search(api, "tarjeta", **FULL)["results"]) == 20


# --- Filtros ------------------------------------------------------------------------------------

def _expected_conversations(q, keep):
    engine = search_router.get_search_engine()
    return {h.fragment.conversation_id for h in engine.search(q) if keep(conversation_index()[h.fragment.conversation_id])}


@pytest.mark.parametrize("params,keep", [
    ({}, lambda c: REF - timedelta(days=30) <= c.started_at.date() <= REF - timedelta(days=1)),
    ({"channel": "chat", **FULL}, lambda c: c.channel == "chat"),
    ({"queue": [QUEUE_IDS["Tarjetas"], QUEUE_IDS["Banca digital"]], **FULL},
     lambda c: c.queue in ("Tarjetas", "Banca digital")),
    ({"from": (REF - timedelta(days=10)).isoformat(), "to": (REF - timedelta(days=5)).isoformat()},
     lambda c: REF - timedelta(days=10) <= c.started_at.date() <= REF - timedelta(days=5)),
])
def test_filters_match_an_independent_filtering(api, params, keep):
    q = "me han bloqueado la tarjeta"
    body = search(api, q, limit=100, **params)
    expected = _expected_conversations(q, keep)
    assert body["total"] == len(expected) > 0
    assert {r["conversation_id"] for r in body["results"]} <= expected


def test_default_period_is_the_platform_default(api):
    body = search(api, "tarjeta")
    assert body["period"] == {"from": (REF - timedelta(days=30)).isoformat(), "to": (REF - timedelta(days=1)).isoformat()}


# --- Validación ---------------------------------------------------------------------------------

@pytest.mark.parametrize("params", [
    {"q": ""},
    {"q": "   "},
    {"q": "a" * 501},
    {"q": "tarjeta", "from": "2026-09-10", "to": "2026-09-01"},
    {"q": "tarjeta", "min_score": "-0.1"},
    {"q": "tarjeta", "min_score": "1.5"},
    {"q": "tarjeta", "min_score": "nan"},
    {"q": "tarjeta", "group": "cola"},
    {"q": "tarjeta", "limit": "0"},
    {"q": "tarjeta", "limit": "101"},
    {"q": "tarjeta", "channel": "fax"},
    {"q": "tarjeta", "queue": "1AG-4B2E9A7F-3D1C-4A9B-8E5D-8F0A6C3E71AB"},
    {"q": "tarjeta", "queue": "Tarjetas"},
    {},
])
def test_invalid_parameters_return_422(api, params):
    assert api.get(URL, params=params).status_code == 422, params


def test_viewer_gets_403():
    client = TestClient(app)
    viewer = auth.get_store().find_by_email("viewer@bancohorizonte.demo")
    response = client.get(URL, params={"q": "tarjeta"}, headers={"Authorization": f"Bearer {auth.create_token(viewer)}"})
    assert response.status_code == 403


# --- Motor sustituible e índice al arrancar -----------------------------------------------------

class FakeEngine:
    def __init__(self):
        conv = get_dataset()[-1]
        self.conv = conv
        self.fragments = [Fragment(conv.id, 0, 1, (0, 1), f"{conv.turns[0].text}\n{conv.turns[1].text}")]
        self.calls = []

    def search(self, text, candidates=None):
        self.calls.append((text, candidates))
        return [Hit(self.fragments[0], 0.42)]

    def expansions(self, text):
        return ["falso"]

    def similar(self, conversation_id, k=10):
        return []


def test_api_only_depends_on_the_search_engine_interface(api):
    fake = FakeEngine()
    app.dependency_overrides[search_router.get_search_engine] = lambda: fake
    try:
        body = search(api, "cualquier cosa", **FULL)
    finally:
        app.dependency_overrides.clear()
    assert body["expansions"] == ["falso"]
    assert [(r["conversation_id"], r["score"], r["start_turn"], r["end_turn"]) for r in body["results"]] == \
        [(fake.conv.id, 0.42, 0, 1)]
    text, candidates = fake.calls[0]
    assert text == "cualquier cosa" and fake.conv.id in candidates


def test_index_is_built_at_startup_before_the_first_search():
    search_router.build_default_engine.cache_clear()
    with TestClient(app):
        assert search_router.build_default_engine.cache_info().currsize == 1


# --- Propiedad y rendimiento --------------------------------------------------------------------

def test_random_texts_never_fail(api):
    rng = random.Random(2026)
    vocabulary = [e.replace("*", "") for group in SYNONYMS for e in group] + \
        [w for q, _ in LABELLED_QUERIES + PARAPHRASE_PAIRS for w in q.split()]
    alphabet = "abcñáéíóúü ¿?¡!.*+()[]{}|\\^$\"'%_-\n\t0123456789€😀中"
    for i in range(300):
        if i % 2:
            text = " ".join(rng.choice(vocabulary) for _ in range(rng.randint(1, 30)))
        else:
            text = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 60)))
        text = text[:500]
        response = api.get(URL, params={"q": text, "group": rng.choice(["conversation", "fragment"]), **FULL})
        assert response.status_code in (200, 422), (text, response.status_code)
        if response.status_code == 422:
            assert not text.strip(), text
            continue
        scores = [r["score"] for r in response.json()["results"]]
        assert all(0 <= s <= 1 for s in scores), text
        assert scores == sorted(scores, reverse=True), text


def test_each_labelled_query_answers_in_under_500_ms(api):
    search(api, "calentamiento", **FULL)
    for q, _ in LABELLED_QUERIES + PARAPHRASE_PAIRS:
        started = time.perf_counter()
        search(api, q, **FULL)
        elapsed = time.perf_counter() - started
        assert elapsed < 0.5, (q, elapsed)


# --- Umbral en contexto (criterio 19) -----------------------------------------------------------

def test_max_score_is_the_best_score_before_the_threshold(api):
    q = "no puedo entrar en la app"
    open_search = search(api, q, **FULL)
    assert open_search["max_score"] == open_search["results"][0]["score"]
    capped = search(api, q, min_score=1, **FULL)
    assert capped["total"] == 0
    assert capped["max_score"] == open_search["max_score"]
    fragments = search(api, q, group="fragment", min_score=0.2, **FULL)
    assert fragments["max_score"] == open_search["max_score"]


def test_max_score_respects_filters_and_is_null_without_matches(api):
    q = "no puedo entrar en la app"
    chat = search(api, q, channel="chat", **FULL)
    assert chat["max_score"] == chat["results"][0]["score"]
    assert search(api, "zzqx wwvk", **FULL)["max_score"] is None
