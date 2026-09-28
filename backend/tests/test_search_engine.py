import random
import time
from datetime import datetime

import pytest

from app import ids
from app.data.store import get_dataset
from app.models import Analysis, Conversation, Turn
from app.search.engine import SearchEngine, build_fragments
from app.search.tfidf import TfidfEngine

_rng = random.Random(3)


def _conv(texts, speakers=None) -> Conversation:
    speakers = speakers or ["cliente" if i % 2 == 0 else "agente" for i in range(len(texts))]
    return Conversation(
        id=ids.new_id(ids.CONVERSATION, _rng),
        channel="chat",
        started_at=datetime(2026, 9, 1, 10),
        duration_s=60,
        queue_id=ids.stable_id(ids.QUEUE, "Particulares"),
        queue="Particulares",
        agent_id=ids.stable_id(ids.AGENT, "Agente"),
        agent="Agente",
        customer_id=ids.new_id(ids.CUSTOMER, _rng),
        turns=[Turn(speaker=s, text=t, offset_s=i, sentiment=0.0) for i, (s, t) in enumerate(zip(speakers, texts))],
        analysis=Analysis(
            summary="", main_topic="comisiones", secondary_topics=[], sentiment=0.0, sentiment_timeline=[],
            resolution="resuelta", csat=4.0, effort=2.0, churn_risk="bajo", compliance={}, entities=[], keywords=[],
        ),
    )


def _spans(conv):
    return [(f.start_turn, f.end_turn, f.turns) for f in build_fragments(conv)]


# --- Fragmentos ---------------------------------------------------------------------------------

def test_fragments_are_windows_of_three_turns_with_step_two_skipping_system_turns():
    conv = _conv(["a", "b", "c", "d", "e", "f", "g"],
                 ["bot", "cliente", "sistema", "agente", "cliente", "agente", "cliente"])
    assert _spans(conv) == [(0, 3, (0, 1, 3)), (3, 5, (3, 4, 5)), (5, 6, (5, 6))]


def test_fragments_stop_when_a_window_reaches_the_last_turn():
    assert _spans(_conv(list("abcde"))) == [(0, 2, (0, 1, 2)), (2, 4, (2, 3, 4))]
    assert _spans(_conv(list("abcdef"))) == [(0, 2, (0, 1, 2)), (2, 4, (2, 3, 4)), (4, 5, (4, 5))]
    assert _spans(_conv(["solo"])) == [(0, 0, (0,))]


def test_fragment_text_joins_its_turns_and_keeps_the_conversation():
    conv = _conv(["Hola", "Ha fallado", "Aviso"], ["cliente", "agente", "sistema"])
    [fragment] = build_fragments(conv)
    assert fragment.conversation_id == conv.id
    assert fragment.text == "Hola\nHa fallado"


def test_conversation_with_only_system_turns_has_no_fragments():
    assert build_fragments(_conv(["x", "y"], ["sistema", "sistema"])) == []


# --- Puntuación ---------------------------------------------------------------------------------

@pytest.fixture
def small_engine():
    convs = [
        _conv(["Quiero bloquear la tarjeta porque me la han robado", "La bloqueo ahora mismo"]),
        _conv(["Me cobran una comisión de mantenimiento", "Reviso las comisiones de su cuenta"]),
        _conv(["El cajero no me dio el dinero", "Abro una incidencia del cajero"]),
        _conv(["El cajero no me dio el dinero", "Abro una incidencia del cajero"]),
    ]
    # Sin expansión: estos tests prueban el modelo vectorial; la expansión se prueba en test_search_relevance.
    return convs, TfidfEngine(convs, synonyms=())


def test_engine_implements_the_search_engine_interface(small_engine):
    _, engine = small_engine
    assert isinstance(engine, SearchEngine)


def test_identical_fragment_scores_one_and_scores_are_between_zero_and_one(small_engine):
    convs, engine = small_engine
    hits = engine.search("Me cobran una comisión de mantenimiento\nReviso las comisiones de su cuenta")
    assert hits[0].fragment.conversation_id == convs[1].id
    assert hits[0].score == pytest.approx(1.0)
    assert all(0 <= h.score <= 1 for h in hits)


def test_query_without_common_terms_returns_nothing(small_engine):
    _, engine = small_engine
    assert engine.search("zzqx wwvk") == []
    assert engine.search("   ") == []


def test_hits_are_sorted_by_score_with_stable_tie_break(small_engine):
    convs, engine = small_engine
    hits = engine.search("cajero dinero")
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)
    assert [h.fragment.conversation_id for h in hits[:2]] == [convs[2].id, convs[3].id]
    assert hits[0].score == hits[1].score


def test_search_ignores_accents_case_and_inflection(small_engine):
    convs, engine = small_engine
    hits = engine.search("TARJETA BLOQUEADA")
    assert hits[0].fragment.conversation_id == convs[0].id
    assert engine.search("comisión")[0].fragment.conversation_id == convs[1].id
    assert _scores(engine.search("COMISION DE MANTENIMIENTO")) == _scores(engine.search("comisión de mantenimiento"))
    assert _scores(engine.search("Robádo")) == _scores(engine.search("robado"))


def _scores(hits):
    return [(h.fragment.conversation_id, h.fragment.start_turn, h.score) for h in hits]


def test_search_can_be_limited_to_candidate_conversations(small_engine):
    convs, engine = small_engine
    hits = engine.search("cajero dinero", candidates={convs[3].id})
    assert {h.fragment.conversation_id for h in hits} == {convs[3].id}


# --- Similares ----------------------------------------------------------------------------------

def test_similar_excludes_the_conversation_and_is_sorted(small_engine):
    convs, engine = small_engine
    similar = engine.similar(convs[2].id, k=2)
    assert [cid for cid, _ in similar][0] == convs[3].id
    assert convs[2].id not in [cid for cid, _ in similar]
    assert similar[0][1] == pytest.approx(1.0)
    assert [s for _, s in similar] == sorted((s for _, s in similar), reverse=True)
    assert len(similar) <= 2


def test_similar_of_unknown_conversation_raises_key_error(small_engine):
    _, engine = small_engine
    with pytest.raises(KeyError):
        engine.similar("1CO-00000000-0000-4000-8000-000000000000")


# --- Dataset completo ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def dataset_engine():
    dataset = get_dataset()
    started = time.perf_counter()
    engine = TfidfEngine(dataset)
    build_s = time.perf_counter() - started
    print(f"\n[índice] {engine.stats()} construido en {build_s:.2f} s")
    assert build_s < 15
    return {c.id: c for c in dataset}, engine


TOPICAL_QUERIES = {
    "el cajero no me dio el dinero y me lo han cargado": "cajeros",
    "me ha aparecido un cargo que no reconozco": "cargo_no_reconocido",
    "no puedo entrar en la app, tengo el usuario bloqueado": "acceso_banca_digital",
    "quiero cerrar la cuenta y cancelar las tarjetas": "baja_cancelacion",
    # Texto común (saludo, verificación, despedida) mezclado con el tema: el IDF debe anularlo.
    "buenos días, le atiende, verificar su identidad, gracias por confiar, quiero hacer un bizum": "transferencias_bizum",
}


@pytest.mark.parametrize("query,topic", TOPICAL_QUERIES.items())
def test_common_text_does_not_outrank_the_topic(dataset_engine, query, topic):
    by_id, engine = dataset_engine
    top = engine.search(query)[:5]
    assert len(top) == 5
    assert [by_id[h.fragment.conversation_id].analysis.main_topic for h in top] == [topic] * 5


def test_every_non_system_turn_of_the_dataset_is_indexed(dataset_engine):
    by_id, engine = dataset_engine
    covered = {(f.conversation_id, t) for f in engine.fragments for t in f.turns}
    expected = {(cid, i) for cid, c in by_id.items() for i, t in enumerate(c.turns) if t.speaker != "sistema"}
    assert covered == expected
