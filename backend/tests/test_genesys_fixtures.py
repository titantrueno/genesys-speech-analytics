"""Fixtures de Genesys y Genesys falso (FE011, T2; criterio 24).

Las fixtures son respuestas reales de la cuenta del laboratorio del 2026-10-12, saneadas por
`scripts/capture_genesys_fixtures.py`: sin organización, sin URL firmadas ni tokens, con ANI y `externalTag`.
"""
import importlib.util
import json
from pathlib import Path

import pytest

from ingestion.genesys.client import GenesysClient, GenesysError, GenesysNotFound
from ingestion.genesys.fake import FakeGenesys

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "genesys"
ROOT = Path(__file__).resolve().parents[2]
DAY = "2026-10-11T22:00:00.000Z/2026-10-12T22:00:00.000Z"  # 12 de octubre en Madrid

_spec = importlib.util.spec_from_file_location("capture", ROOT / "scripts" / "capture_genesys_fixtures.py")
capture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(capture)


def _folders() -> list[Path]:
    return sorted(p for p in FIXTURES.iterdir() if p.is_dir())


def _client(fake: FakeGenesys) -> GenesysClient:
    return GenesysClient("cliente", "secreto", "eu-west-1", transport=fake.transport, sleep=lambda _: None)


@pytest.fixture
def fake():
    return FakeGenesys.from_fixtures(FIXTURES, client_id="cliente", client_secret="secreto")


def test_there_is_one_fixture_per_reference_conversation():
    expected = {f"{kind}-{cid[:8]}" for kind, cid in capture.REFERENCES.items()}
    assert {p.name for p in _folders()} == expected
    for folder in _folders():
        names = {p.name for p in folder.iterdir()}
        required = {"details.json", "sta.json", "transcripts.json"}
        if folder.name.startswith("chat_"):
            required |= {"messages.json", "messages_bulk.json"}
        assert required <= names, folder.name


@pytest.mark.parametrize("folder", _folders(), ids=lambda p: p.name)
def test_fixtures_carry_no_organization_signed_urls_or_tokens(folder):
    text = "".join(p.read_text() for p in folder.glob("*.json"))
    for forbidden in ['"organizationId"', "X-Amz-", "amazonaws", "access_token", "Bearer "]:
        assert forbidden not in text, f"{folder.name} contiene {forbidden}"
    for document in json.loads((folder / "transcripts.json").read_text()).values():
        if document:
            assert capture.PLACEHOLDER_ORG in document["uri"]


def test_fixtures_keep_the_phone_and_the_external_tag():
    details = json.loads((FIXTURES / "voz_contenida_bot-37dcbccf" / "details.json").read_text())
    assert details["externalTag"]
    assert any(s.get("ani", "").startswith("tel:+34") for p in details["participants"] for s in p["sessions"])


def test_sanitize_removes_the_organization_and_signed_urls():
    raw = {"organizationId": "org-1", "uri": "/transcript/v1/organizations/org-1/conversations/c",
           "media": ["https://bucket.s3.amazonaws.com/a.json?X-Amz-Signature=abc&X-Amz-Expires=300"],
           "nested": [{"organizationId": "org-1", "keep": "tel:+34600000000"}]}
    assert capture.sanitize(raw, "org-1") == {
        "uri": f"/transcript/v1/organizations/{capture.PLACEHOLDER_ORG}/conversations/c",
        "media": ["[URL firmada]"], "nested": [{"keep": "tel:+34600000000"}]}


def test_the_fake_serves_the_day_page_by_page(fake):
    client, found, page = _client(fake), [], 1
    while True:
        body = client.post("/api/v2/analytics/conversations/details/query",
                           json={"interval": DAY, "paging": {"pageSize": 4, "pageNumber": page}})
        found += body.get("conversations", [])
        if len(found) >= body["totalHits"]:
            break
        page += 1
    assert page == 3
    assert {c["conversationId"] for c in found} == set(capture.REFERENCES.values())


def test_the_fake_rejects_intervals_longer_than_seven_days(fake):
    with pytest.raises(GenesysError, match="7 days") as caught:
        _client(fake).post("/api/v2/analytics/conversations/details/query",
                           json={"interval": "2026-10-01T00:00:00.000Z/2026-10-09T00:00:00.000Z"})
    assert caught.value.status == 400


def test_a_reconnected_chat_has_one_transcript_document_and_a_404(fake):
    client = _client(fake)
    base = "/api/v2/speechandtextanalytics/conversations/c870bc58-1f9d-4c89-a7d7-a86b2b32625a/communications"
    document = client.get_signed(client.get(f"{base}/85a3cf6c-7036-4b4f-aebf-2f83bc78d363/transcripturl")["url"])
    assert len(document["transcripts"]) == 2
    with pytest.raises(GenesysNotFound):
        client.get(f"{base}/d3daf81b-d5d8-4d52-9ed5-276abc836381/transcripturl")


def test_the_fake_returns_undelivered_messages_with_their_text(fake):
    conversation = "9e3ec75a-11c8-4df7-9002-339916be2827"
    client = _client(fake)
    ids = [m["messageId"] for p in client.get(f"/api/v2/conversations/messages/{conversation}")["participants"]
           for m in p.get("messages", [])]
    entities = client.post(f"/api/v2/conversations/messages/{conversation}/messages/bulk", json=ids)["entities"]
    failed = [e for e in entities if e["status"] == "delivery-failed"]
    assert [e["normalizedMessage"]["text"] for e in failed] == ["lo estoy revisando, un segundo"]


def test_the_fake_resolves_catalog_names(fake):
    details = json.loads((FIXTURES / "voz_bot_agente-7b94988a" / "details.json").read_text())
    queue = next(seg["queueId"] for p in details["participants"] for s in p["sessions"] for seg in s["segments"]
                 if seg.get("queueId"))
    assert _client(fake).get(f"/api/v2/routing/queues/{queue}")["name"] == "AIT_Transcription"
