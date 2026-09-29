"""Enmascarado de datos personales (FE005, criterio 10): patrones, dataset completo, API, búsqueda, explorador y flujos."""
import re
import time

import pytest

from app.data.store import get_dataset
from app.flows.prompting import MockPromptRunner, render_template
from app.main import app
from app.privacy.masking import mask, masked
from app.routers.flows import get_prompt_runner
from tests.flow_fixtures import SAMPLING, days_ago
from tests.test_flow_runs import by_type, detail, flow_with, run

# Formatos del generador (app/data/generator.py): DNI de 8 cifras y letra, IBAN español en grupos de 4.
DATASET_DNI = re.compile(r"\b\d{8}[A-Z]\b")
DATASET_IBAN = re.compile(r"\bES\d{2}(?: \d{4}){5}\b")


def pii_of(text: str) -> set[str]:
    return set(DATASET_DNI.findall(text)) | set(DATASET_IBAN.findall(text))


def all_texts(conv) -> list[str]:
    return [conv.analysis.summary, *(t.text for t in conv.turns)]


@pytest.fixture(scope="module")
def with_pii():
    """Conversaciones del dataset que contienen un DNI o un IBAN, y el conjunto de esos datos."""
    convs = [c for c in get_dataset() if any(pii_of(t) for t in all_texts(c))]
    values = {v for c in convs for t in all_texts(c) for v in pii_of(t)}
    assert len(convs) > 100 and values
    return convs, values


def set_masking(api, enabled: bool) -> None:
    assert api.put("/api/config/privacy", json={"pii_masking": enabled}).status_code == 200


def leaked(body: str, values: set[str]) -> set[str]:
    return {v for v in values if v in body}


# --- Patrones ---

@pytest.mark.parametrize("text,expected", [
    ("Sí, es 12345678Z.", "Sí, es [DNI]."),
    ("Mi DNI es 12345678-z", "Mi DNI es [DNI]"),
    ("NIE X1234567L y Y-7654321G", "NIE [DNI] y [DNI]"),
    ("le leo su cuenta: ES91 9999 1234 5678 9012 3456.", "le leo su cuenta: [IBAN]."),
    ("IBAN ES9199991234567890123456", "IBAN [IBAN]"),
    ("IBAN alemán DE89370400440532013000", "IBAN alemán [IBAN]"),
    ("tarjeta 4111 1111 1111 1111", "tarjeta [TARJETA]"),
    ("tarjeta 4111-1111-1111-1111 caducada", "tarjeta [TARJETA] caducada"),
    ("llámeme al 600 123 456", "llámeme al [TELÉFONO]"),
    ("o al +34 912345678", "o al [TELÉFONO]"),
    ("o al 0034 600-12-34-56", "o al [TELÉFONO]"),
    ("su móvil 600 12 34 56.", "su móvil [TELÉFONO]."),
    ("escriba a ana.lopez+banco@correo.es, gracias", "escriba a [EMAIL], gracias"),
])
def test_each_type_is_masked(text, expected):
    assert mask(text) == expected


@pytest.mark.parametrize("text", [
    "con la tarjeta terminada en 1234",
    "el teléfono termina en 456",
    "un cargo de 1.234,56 €",
    "una cuota de 612.345 €",
    "un importe de 600,50 €",
    "el 12/09/2026 a las 10:30",
    "el 2026-09-12",
    "expediente 20260912",
    "reclamación REC-2026-004512",
    "conversación 1CO-4B2E9A7F-3D1C-4A9B-8E5D-8F0A6C3E71AB",
    "un préstamo de 30000 € a 60 meses",
    "referencia 12345678901234567890123",
    # Un número de 8 cifras seguido de «y», «a» o «e» (letras de DNI) no es un DNI: separador y letra de control.
    "expediente 20213570 y el 15/3/2026",
    "cuenta 66230047 a nombre de la clienta",
    "el recibo 12345678 e importe",
    "un DNI con letra que no cuadra: 12345678A",
])
def test_known_false_positives_are_kept(text):
    assert mask(text) == text


def test_property_generated_personal_data_is_masked_and_nothing_else(with_pii):
    """3.000 frases con un dato personal generado (DNI/NIE válidos, IBAN, teléfono, email, tarjeta) y dos textos seguros."""
    import random

    rng = random.Random(7)
    letters = "TRWAGMYFPDXBNJZSQVHLCKE"

    def dni():
        n = rng.randint(0, 99_999_999)
        value = f"{n:08d}{letters[n % 23]}"
        return rng.choice([value, f"{value[:8]}-{value[8]}", value.lower()])

    def nie():
        prefix, n = rng.choice("XYZ"), rng.randint(0, 9_999_999)
        letter = letters[int(f"{'XYZ'.index(prefix)}{n:07d}") % 23]
        return rng.choice([f"{prefix}{n:07d}{letter}", f"{prefix}-{n:07d}-{letter}"])

    def iban():
        compact = "ES" + "".join(str(rng.randint(0, 9)) for _ in range(22))
        return rng.choice([compact, " ".join(compact[i:i + 4] for i in range(0, 24, 4))])

    def phone():
        d = rng.choice("6789") + "".join(str(rng.randint(0, 9)) for _ in range(8))
        return rng.choice([d, f"{d[:3]} {d[3:6]} {d[6:]}", f"{d[:3]} {d[3:5]} {d[5:7]} {d[7:]}", f"+34 {d}",
                           f"0034 {d[:3]}-{d[3:6]}-{d[6:]}"])

    def email():
        return f"{rng.choice(['ana', 'j.perez', 'luis+banco'])}{rng.randint(1, 99)}@{rng.choice(['correo.es', 'mail.com'])}"

    def card():
        d = "".join(str(rng.randint(0, 9)) for _ in range(16))
        return rng.choice([d, " ".join(d[i:i + 4] for i in range(0, 16, 4)), "-".join(d[i:i + 4] for i in range(0, 16, 4))])

    def safe():
        return rng.choice([
            f"{rng.randint(1, 99999):,}".replace(",", ".") + f",{rng.randint(0, 99):02d} €",
            f"{rng.randint(1, 28)}/{rng.randint(1, 12)}/2026", f"{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}",
            f"expediente {rng.randint(2020_0000, 2026_9999)}", f"terminada en {rng.randint(1000, 9999)}",
            f"REC-2026-{rng.randint(0, 999_999):06d}", f"{rng.randint(1, 120)} meses",
            f"cuenta {rng.randint(10_000_000, 99_999_999)} a nombre de",
        ])

    generators = {"[DNI]": [dni, nie], "[IBAN]": [iban], "[TELÉFONO]": [phone], "[EMAIL]": [email], "[TARJETA]": [card]}
    for _ in range(3000):
        token, options = rng.choice(list(generators.items()))
        value, first, second = rng.choice(options)(), safe(), safe()
        text = f"Le indico {value}, y además {first} y {second} e importe."
        assert mask(text) == f"Le indico {token}, y además {first} y {second} e importe.", text


def test_the_whole_dataset_is_masked_without_false_positives(with_pii):
    for conv in get_dataset():
        for original, shown in zip(all_texts(conv), all_texts(masked(conv))):
            assert not pii_of(shown), (conv.id, shown)
            if not pii_of(original):
                assert shown == original, (conv.id, original, shown)
            assert mask(shown) == shown  # idempotente


def test_masking_copies_and_never_changes_the_dataset(with_pii):
    conv = with_pii[0][0]
    before = conv.model_dump()
    copy = masked(conv)
    assert copy is not conv and copy.id == conv.id
    assert conv.model_dump() == before
    assert copy.analysis.sentiment == conv.analysis.sentiment
    assert masked(conv) is copy  # cacheada


def test_cache_does_not_mix_up_conversations_with_the_same_id(with_pii):
    conv = with_pii[0][0]
    masked(conv)
    edited = conv.model_copy(update={"turns": [conv.turns[0].model_copy(update={"text": "Mi DNI es 87654321X."})]})
    assert masked(edited).turns[0].text == "Mi DNI es [DNI]."
    assert len(masked(conv).turns) == len(conv.turns)


# --- API ---

def test_masking_is_on_by_default_in_the_detail(api, with_pii):
    conv = with_pii[0][0]
    body = api.get(f"/api/conversations/{conv.id}").text
    assert not leaked(body, with_pii[1])
    assert "[DNI]" in body or "[IBAN]" in body


def test_turning_masking_off_shows_the_original_data(api, with_pii):
    conv = with_pii[0][0]
    set_masking(api, False)
    body = api.get(f"/api/conversations/{conv.id}").text
    assert leaked(body, with_pii[1])
    set_masking(api, True)
    assert not leaked(api.get(f"/api/conversations/{conv.id}").text, with_pii[1])


def test_listing_and_explorer_do_not_leak(api, with_pii):
    params = {"from": days_ago(89), "to": days_ago(1), "page_size": 100}
    for page in (1, 2, 3):
        assert not leaked(api.get("/api/conversations", params={**params, "page": page}).text, with_pii[1])
    query = {"from": days_ago(89), "to": days_ago(1), "root": {"op": "and", "conditions": []}}
    assert not leaked(api.post("/api/query/run", params={"page_size": 100}, json=query).text, with_pii[1])


def test_semantic_search_turns_are_masked(api, with_pii):
    body = api.get("/api/search/semantic", params={"q": "verificar su identidad DNI", "from": days_ago(89),
                                                   "to": days_ago(1), "limit": 100}).json()
    assert body["results"]
    assert not leaked(str(body), with_pii[1])
    assert any("[DNI]" in t["text"] for r in body["results"] for t in r["turns"])


@pytest.mark.parametrize("enabled", [True, False])
def test_searching_a_dni_finds_nothing_whatever_the_switch(api, with_pii, enabled):
    set_masking(api, enabled)
    dni = next(v for v in sorted(with_pii[1]) if DATASET_DNI.fullmatch(v))
    body = api.get("/api/search/semantic", params={"q": dni, "from": days_ago(89), "to": days_ago(1),
                                                   "group": "fragment"}).json()
    hits = [r for r in body["results"] if any(dni in t["text"] for t in r["turns"])]
    assert hits == []
    assert not leaked(str(body["results"]), with_pii[1])  # `query` repite lo que se buscó


def test_explorer_text_conditions_search_the_text_as_shown(api, with_pii):
    conv = next(c for c in with_pii[0] if any(DATASET_DNI.search(t.text) for t in c.turns))
    dni = next(DATASET_DNI.search(t.text).group() for t in conv.turns if DATASET_DNI.search(t.text))
    day = conv.started_at.date().isoformat()
    query = {"from": day, "to": day,
             "root": {"op": "and", "conditions": [{"field": "transcript", "operator": "contains", "value": dni}]}}
    assert api.post("/api/query/run", json=query).json()["total"] == 0
    set_masking(api, False)
    assert api.post("/api/query/run", json=query).json()["total"] >= 1


# --- Flujos ---

class Spy(MockPromptRunner):
    rendered: list[str] = []

    def run(self, config, conversation, previous):
        Spy.rendered.append(render_template(config.template, conversation, previous))
        return super().run(config, conversation, previous)


@pytest.mark.parametrize("enabled", [True, False])
def test_prompts_always_receive_masked_transcripts_and_outputs_do_not_leak(api, with_pii, enabled):
    set_masking(api, enabled)
    sampling = {**SAMPLING, "query": {"from": days_ago(89), "to": days_ago(1),
                                      "root": {"op": "and", "conditions": [
                                          {"field": "main_topic", "operator": "is",
                                           "value": "transferencias_bizum"}]}}}
    flow = flow_with(api, {"version": 1, "nodes": [
        {"id": "tmp-s", "type": "sampling", "position": {"x": 0, "y": 0}, "config": sampling},
        {"id": "tmp-p", "type": "prompt", "position": {"x": 0, "y": 0}, "config": {
            "template": "Resume: {{transcripcion}} {{summary}}", "model": "mock-preciso", "temperature": 0.5,
            "output": {"type": "texto"}}},
        {"id": "tmp-t", "type": "output", "position": {"x": 0, "y": 0},
         "config": {"kind": "tabla", "destination": "tabla"}},
        {"id": "tmp-r", "type": "output", "position": {"x": 0, "y": 0},
         "config": {"kind": "informe", "destination": "informe"}},
    ], "edges": [{"source": "tmp-s", "target": "tmp-p"}, {"source": "tmp-p", "target": "tmp-t"},
                 {"source": "tmp-p", "target": "tmp-r"}]})
    Spy.rendered = []
    app.dependency_overrides[get_prompt_runner] = Spy
    try:
        final = detail(api, flow, run(api, flow)["id"])
    finally:
        app.dependency_overrides.clear()
    assert final["status"] == "ok", final
    assert len(Spy.rendered) == 40
    assert any("[IBAN]" in text or "[DNI]" in text for text in Spy.rendered)
    assert not any(leaked(text, with_pii[1]) for text in Spy.rendered)
    assert not leaked(str(final["outputs"]), with_pii[1])
    assert by_type(flow)["output"]


# --- Rendimiento ---

def test_detail_and_search_stay_under_500_ms_with_masking(api, with_pii):
    api.get("/api/search/semantic", params={"q": "calentamiento"})
    for conv in with_pii[0][:20]:
        start = time.perf_counter()
        api.get(f"/api/conversations/{conv.id}")
        assert time.perf_counter() - start < 0.5
    start = time.perf_counter()
    api.get("/api/search/semantic", params={"q": "mi DNI y mi cuenta", "from": days_ago(89), "to": days_ago(1),
                                            "limit": 100})
    assert time.perf_counter() - start < 0.5
