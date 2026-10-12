"""Búsqueda y privacidad con el origen `real` (FE012, T5; criterios 11 y 12)."""
import psycopg
import pytest

from app.data.store import get_dataset
from app.flows.prompting import render_template
from app.routers.search import search_index
from tests.real_helpers import QS, real_api, real_id  # noqa: F401  (fixture)

pytestmark = pytest.mark.pg
CHAT_AGENT, CHAT_BOT_AGENT = "8d29170a", "f7e79502"
PII = {
    "phone": ("llámeme al 612 345 678", "[TELÉFONO]"),
    "email": ("mi correo es ana.perez@example.com", "[EMAIL]"),
    "dni": ("mi DNI es 12345678Z", "[DNI]"),
    "iban": ("el IBAN es ES9121000418450200051332", "[IBAN]"),
    "card": ("la tarjeta 4111 1111 1111 1111", "[TARJETA]"),
}
VISA = "Visa terminada en 4821"


def search(api, q, **params):
    response = api.get("/api/search/semantic", params={**QS, "q": q, "limit": 50, **params})
    assert response.status_code == 200, response.text
    return response.json()


def plant_text(pg_url, short_id, texts):
    """Sustituye los textos de los primeros turnos de una conversación guardada, como haría una descarga nueva."""
    with psycopg.connect(pg_url) as conn:
        for seq, text in enumerate(texts):
            conn.execute("UPDATE turn SET text = %s WHERE conversation_id = %s AND seq = %s",
                         (text, real_id(short_id), seq))
        conn.execute("UPDATE conversation SET updated_at = now() WHERE id = %s", (real_id(short_id),))


# --- Búsqueda ---

def test_semantic_search_finds_amazon_brasil_in_real_chats(real_api):
    body = search(real_api, "Amazon Brasil")
    assert body["total"] >= 1
    found = {r["conversation_id"] for r in body["results"]}
    assert real_id(CHAT_AGENT) in found
    assert any("Amazon" in turn["text"] for r in body["results"] for turn in r["turns"])


def test_the_index_covers_customer_bot_and_agent_turns_including_undelivered_ones(real_api):
    search(real_api, "hola")  # primer uso del origen real: construye el índice
    fragments = [f for f in search_index.engine().fragments]
    by_conv = {}
    for fragment in fragments:
        by_conv.setdefault(fragment.conversation_id, []).append(fragment)
    with_text = {c.id for c in get_dataset() if any(t.speaker != "sistema" for t in c.turns)}
    assert set(by_conv) == with_text and len(with_text) == 9  # la llamada sin transcripción no tiene nada que indexar
    conv = next(c for c in get_dataset() if c.id == real_id("9e3ec75a"))
    indexed = {i for f in by_conv[conv.id] for i in f.turns}
    undelivered = {i for i, t in enumerate(conv.turns) if not t.delivered}
    assert undelivered and undelivered <= indexed
    bot = next(c for c in get_dataset() if c.id == real_id(CHAT_BOT_AGENT))
    assert {t.speaker for i, t in enumerate(bot.turns) if i in {i for f in by_conv[bot.id] for i in f.turns}} \
        >= {"cliente", "bot", "agente"}


def test_the_index_is_rebuilt_when_the_origin_changes(real_api):
    real_api.put("/api/config/sources", json={"origin": "sintetico"})
    synthetic = search_index.engine()
    real_api.put("/api/config/sources", json={"origin": "real"})
    real = search_index.engine()
    assert real is not synthetic
    assert {f.conversation_id for f in real.fragments} == {c.id for c in get_dataset() if c.turns}


def test_new_downloads_rebuild_the_index_while_the_previous_one_keeps_serving(real_api, pg_url):
    first = search_index.engine()
    plant_text(pg_url, CHAT_AGENT, ["necesito hablar sobre una devolución de zapatillas"])
    assert search(real_api, "Amazon Brasil")["total"] >= 1  # la petición ya ve los datos nuevos; el índice, aún el anterior
    search_index.wait()
    assert search_index.engine() is not first
    assert search(real_api, "devolución de zapatillas")["total"] >= 1


# --- Privacidad ---

@pytest.fixture
def planted(real_api, pg_url):
    texts = [text for text, _ in PII.values()] + [VISA]
    plant_text(pg_url, CHAT_AGENT, texts)
    return real_api


def _texts(api, short_id=CHAT_AGENT):
    return [t["text"] for t in api.get(f"/api/conversations/{real_id(short_id)}").json()["turns"]]


def test_the_api_masks_the_text_of_real_conversations(planted):
    shown = " ".join(_texts(planted)[:6])
    for original in ("612 345 678", "ana.perez@example.com", "12345678Z", "ES9121000418450200051332",
                     "4111 1111 1111 1111"):
        assert original not in shown
    for _, token in PII.values():
        assert token in shown
    assert VISA in shown  # los últimos 4 dígitos no identifican a nadie


def test_without_masking_the_api_returns_the_original_text(planted):
    planted.put("/api/config/privacy", json={"pii_masking": False})
    assert "ana.perez@example.com" in " ".join(_texts(planted)[:6])


def test_the_index_and_the_prompt_variable_always_use_masked_text(planted):
    planted.put("/api/config/privacy", json={"pii_masking": False})
    search(planted, "hola")
    indexed = " ".join(f.text for f in search_index.engine().fragments if f.conversation_id == real_id(CHAT_AGENT))
    for original in ("612 345 678", "ana.perez@example.com", "12345678Z", "ES9121000418450200051332"):
        assert original not in indexed
    conv = next(c for c in get_dataset() if c.id == real_id(CHAT_AGENT))
    prompt = render_template("{{transcripcion}}", conv)
    assert "ana.perez@example.com" not in prompt and "[EMAIL]" in prompt


def test_the_listing_summary_and_search_results_are_masked_too(planted):
    body = search(planted, "correo ana.perez")
    assert "ana.perez@example.com" not in str(body)


def test_ani_dnis_and_external_tag_are_not_masked(real_api):
    item = next(i for i in real_api.get("/api/conversations", params={**QS, "page_size": 100}).json()["items"]
                if i["id"] == real_id("37dcbccf"))
    assert (item["ani"], item["external_tag"]) == ("+34675075376", "Javier Del Olmo")
    genesys = real_api.get(f"/api/conversations/{item['id']}").json()["genesys"]
    assert (genesys["ani"], genesys["dnis"], genesys["external_tag"]) == \
        ("+34675075376", "+34919187266", "Javier Del Olmo")


def test_the_phrases_behind_genesys_topics_are_masked(real_api, pg_url):
    with psycopg.connect(pg_url) as conn:
        conn.execute("UPDATE topic_hit SET phrase = 'escríbame a ana.perez@example.com' WHERE conversation_id = %s",
                     (real_id("7b94988a"),))
        conn.execute("UPDATE conversation SET updated_at = now() WHERE id = %s", (real_id("7b94988a"),))
    topics = real_api.get(f"/api/conversations/{real_id('7b94988a')}").json()["genesys"]["topics"]
    assert topics and all("ana.perez@example.com" not in (t["phrase"] or "") for t in topics)
    assert any("[EMAIL]" in (t["phrase"] or "") for t in topics)
