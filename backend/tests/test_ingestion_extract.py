"""Extracción de Genesys (FE011, T4; criterio 6): tramos de 7 días, paginación, omisiones y descarga tolerante."""
import json
import math
from datetime import datetime, timedelta

import pytest

from ingestion.genesys.client import GenesysAuthError
from ingestion.pipeline.extract import GenesysNames, fetch, search, split_interval
from tests.ingestion_helpers import (DAY_END, DAY_START, client_factory, fixture, fixtures, in_progress, make_fake,
                                     spread, with_media)

QUERY = "/api/v2/analytics/conversations/details/query"


def test_an_interval_is_split_into_chunks_of_at_most_seven_days():
    chunks = split_interval(DAY_START, DAY_START + timedelta(days=20))
    assert len(chunks) == 3
    assert chunks[0][0] == DAY_START and chunks[-1][1] == DAY_START + timedelta(days=20)
    assert all(end - start <= timedelta(days=7) for start, end in chunks)
    assert all(a[1] == b[0] for a, b in zip(chunks, chunks[1:]))


def test_search_walks_every_chunk_and_page():
    conversations = spread(fixtures(), 30, DAY_START, days=20)
    fake = make_fake(conversations)
    result = search(client_factory(fake)(), DAY_START, DAY_START + timedelta(days=20), {"voz", "chat"}, page_size=4)
    assert sorted(d["conversationId"] for d in result.found) == sorted(c.id for c in conversations)
    assert result.skipped == []
    starts = [datetime.fromisoformat(c.details["conversationStart"].replace("Z", "+00:00")) for c in conversations]
    per_chunk = [sum(start <= s < end for s in starts) for start, end in split_interval(DAY_START, DAY_START
                                                                                        + timedelta(days=20))]
    assert len(per_chunk) == 3 and all(per_chunk)
    queries = [c for c in fake.calls if c == ("POST", QUERY)]
    assert len(queries) == sum(math.ceil(n / 4) for n in per_chunk)  # una consulta por página de cada tramo


def test_search_skips_conversations_in_progress_of_other_media_or_channels():
    voice, chat = fixture("37dcbccf"), fixture("8d29170a")
    running = in_progress(spread([fixture("7b94988a")], 1, DAY_START + timedelta(hours=3), days=1)[0])
    email = with_media(spread([fixture("687f2225")], 1, DAY_START + timedelta(hours=4), days=1)[0], "email")
    fake = make_fake([voice, chat, running, email])
    result = search(client_factory(fake)(), DAY_START, DAY_END, {"voz"})
    assert [d["conversationId"] for d in result.found] == [voice.id]
    assert dict(result.skipped) == {running.id: "en curso", email.id: "otro medio", chat.id: "otro canal"}


def test_fetch_tolerates_a_404_of_a_communication_already_included():
    raw = fixture("c870bc58")
    fetched = fetch(client_factory(make_fake([raw]))(), raw.details)
    assert fetched.transcripts == raw.transcripts  # el segundo tramo queda en None, sin error
    assert fetched.messages_bulk == raw.messages_bulk


def test_fetch_keeps_going_when_the_messages_api_fails():
    raw = fixture("9e3ec75a")
    fake = make_fake([raw])
    fake.fail("POST", f"/api/v2/conversations/messages/{raw.id}/messages/bulk", *[503] * 4)
    fetched = fetch(client_factory(fake)(), raw.details)
    assert fetched.messages_bulk is None and fetched.transcripts == raw.transcripts


def test_fetch_tolerates_a_conversation_without_speech_analytics():
    raw = fixture("37dcbccf")
    fake = make_fake([raw])
    fake.fail("GET", f"/api/v2/speechandtextanalytics/conversations/{raw.id}", 404)
    assert fetch(client_factory(fake)(), raw.details).sta == {}


def test_authentication_errors_are_not_swallowed_by_fetch():
    raw = fixture("37dcbccf")
    fake = make_fake([raw])
    client = client_factory(fake)()
    client.ensure_token()
    fake.fail("GET", f"/api/v2/speechandtextanalytics/conversations/{raw.id}", 401, 401)
    with pytest.raises(GenesysAuthError):
        fetch(client, raw.details)


def test_names_are_resolved_once_per_run():
    fake = make_fake()
    names = GenesysNames(client_factory(fake)())
    queue = "7a25d5e8-6367-4166-8b2d-39fd49a57fd9"
    assert names.queue(queue) == names.queue(queue) == "AIT_Transcription"
    assert names.user("no-existe") is None
    assert fake.calls.count(("GET", f"/api/v2/routing/queues/{queue}")) == 1


def test_a_chunk_over_the_result_cap_is_split_until_it_fits():
    """Genesys deja de paginar a partir de cierto número de resultados (10.000 según su foro): un tramo que lo
    supera se parte en dos, sin bajar de una hora, para no perder conversaciones."""
    conversations = spread(fixtures(), 40, DAY_START, days=2)
    fake = make_fake(conversations)
    result = search(client_factory(fake)(), DAY_START, DAY_START + timedelta(days=2), {"voz", "chat"},
                    page_size=5, max_results=12)
    assert sorted(d["conversationId"] for d in result.found) == sorted(c.id for c in conversations)
    bodies = [json.loads(r.content) for r in fake.requests if r.url.path == QUERY]
    totals = {b["interval"]: sum(1 for c in conversations if _inside(c, b["interval"])) for b in bodies}
    paged = {b["interval"] for b in bodies if b["paging"]["pageNumber"] > 1}
    assert all(totals[interval] <= 12 for interval in paged)  # solo se pagina un tramo que cabe


def _inside(conversation, interval: str) -> bool:
    start, end = (datetime.fromisoformat(part.replace("Z", "+00:00")) for part in interval.split("/"))
    return start <= datetime.fromisoformat(conversation.details["conversationStart"].replace("Z", "+00:00")) < end
