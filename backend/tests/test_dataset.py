import re
from pathlib import Path
from collections import Counter
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app import ids
from app.data.catalog import AGENTS_BY_QUEUE, BANK_TIMEZONE, MAIN_TOPICS, QUEUES, RESULT_MARKERS
from app.data.generator import generate_dataset
from app.main import app

REF = date(2026, 9, 27)
SEED = 42
EXPECTED_TOPICS = {
    "alta_cliente", "baja_cancelacion", "contratacion_producto", "cargo_no_reconocido",
    "bloqueo_tarjeta", "acceso_banca_digital", "transferencias_bizum", "comisiones",
    "recibos_domiciliaciones", "prestamos_hipotecas", "tarjeta_denegada", "cajeros",
    "datos_personales", "consulta_saldo_movimientos", "reclamacion_queja",
}
EXPECTED_QUEUES = {
    "Particulares", "Tarjetas", "Fraude y seguridad", "Banca digital",
    "Préstamos e hipotecas", "Inversión y ahorro", "Empresas",
}
IBAN_RE = re.compile(r"\bES\d{2}(?: ?\d{4}){5}\b")
DNI_RE = re.compile(r"\b(\d{8})([A-Z])\b")
CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
SENTENCE_END_RE = re.compile(r"[.!?](?=\s|$)")


@pytest.fixture(scope="module")
def dataset():
    return generate_dataset(seed=SEED, reference_date=REF)


def transcript(conv) -> str:
    return " ".join(t.text for t in conv.turns).lower()


def test_health():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_catalog_matches_spec():
    assert set(MAIN_TOPICS) == EXPECTED_TOPICS
    assert set(QUEUES) == EXPECTED_QUEUES
    assert set(RESULT_MARKERS) == {"resuelta", "no_resuelta", "escalada"}


def test_generation_is_deterministic(dataset):
    again = generate_dataset(seed=SEED, reference_date=REF)
    assert [c.model_dump() for c in again] == [c.model_dump() for c in dataset]
    other = generate_dataset(seed=SEED + 1, reference_date=REF)
    assert [c.model_dump() for c in other] != [c.model_dump() for c in dataset]


def test_size_ids_and_date_range(dataset):
    assert len(dataset) == 1000
    assert len({c.id for c in dataset}) == 1000
    assert all(ids.is_valid(c.id, ids.CONVERSATION) for c in dataset)
    assert all(ids.is_valid(c.customer_id, ids.CUSTOMER) for c in dataset)
    bank = ZoneInfo(BANK_TIMEZONE)
    start = datetime.combine(REF - timedelta(days=90), datetime.min.time(), tzinfo=bank)
    end = datetime.combine(REF, datetime.min.time(), tzinfo=bank)
    assert all(start <= c.started_at < end for c in dataset)
    assert {c.channel for c in dataset} == {"voz", "chat"}


def test_turns_and_analysis_are_well_formed(dataset):
    for c in dataset:
        assert len(c.turns) >= 6
        offsets = [t.offset_s for t in c.turns]
        assert offsets == sorted(offsets)
        assert c.duration_s >= offsets[-1]
        assert all(-1 <= t.sentiment <= 1 for t in c.turns)
        assert {t.speaker for t in c.turns} >= {"cliente", "agente"}
        a = c.analysis
        assert -1 <= a.sentiment <= 1
        assert a.resolution in RESULT_MARKERS
        assert 1 <= a.csat <= 5 and 1 <= a.effort <= 5
        assert a.churn_risk in {"bajo", "medio", "alto"}
        assert len(a.sentiment_timeline) == len(c.turns)
        assert a.keywords
        assert c.queue in EXPECTED_QUEUES


def test_every_conversation_has_valid_main_topic_and_summary(dataset):
    for c in dataset:
        assert c.analysis.main_topic in MAIN_TOPICS
        sentences = len(SENTENCE_END_RE.findall(c.analysis.summary))
        assert 2 <= sentences <= 4, c.analysis.summary


def test_transcript_is_coherent_with_main_topic(dataset):
    for c in dataset:
        keywords = MAIN_TOPICS[c.analysis.main_topic].keywords
        text = transcript(c)
        assert any(k in text for k in keywords), (c.id, c.analysis.main_topic)


def test_summary_mentions_motive_and_result(dataset):
    for c in dataset:
        summary = c.analysis.summary.lower()
        keywords = MAIN_TOPICS[c.analysis.main_topic].keywords
        assert any(k in summary for k in keywords), c.analysis.summary
        assert RESULT_MARKERS[c.analysis.resolution].lower() in summary, c.analysis.summary


def test_topic_distribution_is_realistic(dataset):
    counts = Counter(c.analysis.main_topic for c in dataset)
    assert set(counts) == EXPECTED_TOPICS
    top5 = {topic for topic, _ in counts.most_common(5)}
    assert {"cargo_no_reconocido", "acceso_banca_digital"} <= top5
    assert min(counts.values()) >= 10
    assert max(counts.values()) >= 3 * min(counts.values())


def test_topics_route_to_their_usual_queues(dataset):
    fraud_queues = Counter(c.queue for c in dataset if c.analysis.main_topic == "cargo_no_reconocido")
    assert fraud_queues.most_common(1)[0][0] == "Fraude y seguridad"
    digital_queues = Counter(c.queue for c in dataset if c.analysis.main_topic == "acceso_banca_digital")
    assert digital_queues.most_common(1)[0][0] == "Banca digital"


def test_no_full_card_numbers(dataset):
    for c in dataset:
        for turn in c.turns:
            text = IBAN_RE.sub("", turn.text)
            text = DNI_RE.sub("", text)
            assert not CARD_RE.search(text), (c.id, turn.text)


def iban_is_valid(iban: str) -> bool:
    compact = iban.replace(" ", "")
    rearranged = compact[4:] + compact[:4]
    digits = "".join(str(int(ch, 36)) for ch in rearranged)
    return int(digits) % 97 == 1


def test_fake_identifiers_have_valid_format(dataset):
    ibans = [m.group(0) for c in dataset for t in c.turns for m in IBAN_RE.finditer(t.text)]
    dnis = [m for c in dataset for t in c.turns for m in DNI_RE.findall(t.text)]
    assert ibans and dnis
    assert all(iban_is_valid(i) for i in ibans)
    assert all("TRWAGMYFPDXBNJZSQVHLCKE"[int(num) % 23] == letter for num, letter in dnis)


def test_agents_and_queues_have_stable_ids(dataset):
    for c in dataset:
        assert c.agent_id == ids.stable_id(ids.AGENT, c.agent)
        assert c.queue_id == ids.stable_id(ids.QUEUE, c.queue)
    assert {c.agent_id for c in dataset} <= {ids.stable_id(ids.AGENT, a) for agents in AGENTS_BY_QUEUE.values() for a in agents}


def test_content_is_unchanged_by_the_identifier_format(dataset):
    """Huella del dataset (seed 42, 2026-09-27) anterior a FE008: solo deben cambiar los identificadores."""
    assert dict(Counter(c.analysis.main_topic for c in dataset)) == {
        "acceso_banca_digital": 106, "alta_cliente": 25, "baja_cancelacion": 51, "bloqueo_tarjeta": 91, "cajeros": 40,
        "cargo_no_reconocido": 166, "comisiones": 68, "consulta_saldo_movimientos": 63, "contratacion_producto": 54,
        "datos_personales": 21, "prestamos_hipotecas": 54, "recibos_domiciliaciones": 54, "reclamacion_queja": 19,
        "tarjeta_denegada": 81, "transferencias_bizum": 107,
    }
    assert dict(Counter(c.queue for c in dataset)) == {
        "Banca digital": 141, "Empresas": 65, "Fraude y seguridad": 154, "Inversión y ahorro": 37,
        "Particulares": 369, "Préstamos e hipotecas": 62, "Tarjetas": 172,
    }
    assert dict(Counter(c.analysis.resolution for c in dataset)) == {"escalada": 172, "no_resuelta": 205, "resuelta": 623}
    assert dict(Counter(c.channel for c in dataset)) == {"chat": 391, "voz": 609}
    assert sum(c.duration_s for c in dataset) == 230337
    assert round(sum(c.analysis.sentiment for c in dataset), 2) == 1.66
    assert len({c.customer_id for c in dataset}) == 472


def test_no_hand_built_legacy_identifiers_in_code():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    legacy = re.compile(r"CNV-|CLI-|[\"']u-[a-z]")
    offenders = [f"{f.name}:{n}" for f in app_dir.rglob("*.py")
                 for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1) if legacy.search(line)]
    assert offenders == []
