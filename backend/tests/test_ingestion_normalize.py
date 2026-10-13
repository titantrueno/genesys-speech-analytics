"""Normalización de conversaciones de Genesys (FE011, T3; criterios 7, 8, 9 y 27).

Cada test parte de una fixture real del 2026-10-12 (`tests/fixtures/genesys/`) y comprueba los valores esperados de la
spec. Los casos límite modifican una copia de la fixture.
"""
import copy
import json
from pathlib import Path

import pytest

from app import ids
from app.data.store import get_dataset
from ingestion.pipeline.normalize import DictNames, normalize
from ingestion.pipeline.raw import RawConversation

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "genesys"
CATALOG = json.loads((FIXTURES / "catalog.json").read_text())
AGENT_NAME = "Javier Del Olmo"


def raw(name: str) -> RawConversation:
    return RawConversation.from_folder(next(FIXTURES.glob(f"*-{name}")))


def run(conversation: RawConversation):
    return normalize(conversation, DictNames.from_catalog(CATALOG))


def speakers(conversation) -> list[str]:
    return [turn.speaker for turn in conversation.turns]


def segment_kinds(conversation) -> list[str]:
    return [segment.kind for segment in conversation.segments]


# Voz contenida en el bot ----------------------------------------------------------------------------------------------

def test_a_call_contained_in_the_bot():
    c = run(raw("37dcbccf"))
    assert c.genesys_id == "37dcbccf-2d89-424e-bc9e-9e53d8494a9a"
    assert c.id == ids.stable_id(ids.CONVERSATION, "genesys:37dcbccf-2d89-424e-bc9e-9e53d8494a9a")
    assert c.channel == "voz" and c.transcript_quality == "completa"
    assert (len(c.turns), speakers(c).count("bot"), speakers(c).count("cliente")) == (12, 9, 3)
    assert (c.ani, c.dnis, c.external_tag) == ("+34675075376", "+34919187266", "Javier Del Olmo")
    assert c.contained_in_bot and not c.derived_to_agent and not c.abandoned_in_queue
    assert c.disconnect_type == "endpoint"  # colgó el cliente
    assert segment_kinds(c) == ["cliente", "ivr"]
    ivr = c.segments[1]
    assert (ivr.flow_name, ivr.exit_reason) == ("Sierra VoiceAgent", "DISCONNECT")
    assert [t.name for t in c.topics] == ["Conexión", "Conexión", "Saludos", "Realización de pagos"]
    assert all(t.phrase and t.turn_seq is not None for t in c.topics)
    assert c.mos == pytest.approx(4.39, abs=0.01)
    assert c.metrics["ivr_s"] == pytest.approx(86.546)
    assert "talk_s" not in c.metrics  # una métrica que Genesys no da queda vacía, no a 0
    assert c.metrics["sta_time_pct"]["ivr"] == pytest.approx(99.93)
    assert c.metrics["acoustic_events"]["voice_internal"] > 0
    assert c.duration_s == 87


def test_turns_are_ordered_with_non_negative_offsets():
    for name in ["37dcbccf", "7b94988a", "8d29170a", "f7e79502", "c870bc58"]:
        c = run(raw(name))
        offsets = [t.offset_s for t in c.turns]
        assert offsets == sorted(offsets) and min(offsets) >= 0, name
        assert [t.seq for t in c.turns] == list(range(len(c.turns)))


# Voz bot → agente -----------------------------------------------------------------------------------------------------

def test_a_call_from_the_bot_to_an_agent():
    c = run(raw("7b94988a"))
    assert c.derived_to_agent and not c.contained_in_bot and c.transferred
    assert segment_kinds(c) == ["cliente", "ivr", "cola", "agente"]
    transfer = c.segments[2].started_at
    offset_of_transfer = (transfer - c.started_at).total_seconds()
    bot = [t for t in c.turns if t.speaker == "bot"]
    agent = [t for t in c.turns if t.speaker == "agente"]
    assert len(bot) == 24 and len(agent) == 2 and len(c.turns) == 40
    assert max(t.offset_s for t in bot) < offset_of_transfer < min(t.offset_s for t in agent)
    assert c.metrics["bot_time_s"] == pytest.approx(218.109)
    queue, agent_segment = c.segments[2], c.segments[3]
    assert c.queues[queue.queue_id] == ("7a25d5e8-6367-4166-8b2d-39fd49a57fd9", "AIT_Transcription")
    assert c.agents[agent_segment.agent_id][1] == AGENT_NAME  # el participante agente no trae nombre
    assert all(t.agent_id == agent_segment.agent_id for t in agent)
    assert c.wrapups[agent_segment.wrapup_genesys_id] == "Default Wrap-up Code"
    assert len(c.topics) == 8  # temas de los dos tramos
    thanks = next(t for t in c.turns if t.text == "vale muchas gracias")
    assert thanks.speaker == "cliente" and thanks.sentiment == 1.0
    assert c.customer_sentiment == pytest.approx(0.635, abs=0.001)
    assert c.metrics["sentiment_trend_class"] == "SlightlyImproving"
    confidence = c.metrics["asr_confidence"]
    assert confidence["agente"] < confidence["bot"]


def test_an_internal_phrase_without_user_ids_inside_the_agent_segment_is_from_the_agent():
    conversation = raw("7b94988a")
    for document in conversation.transcripts.values():
        for transcript in (document or {}).get("transcripts", []):
            for phrase in transcript["phrases"]:
                phrase.pop("userIds", None)
    c = run(conversation)
    assert [t.speaker for t in c.turns].count("agente") == 2


# Voz parcial o sin transcripción --------------------------------------------------------------------------------------

def test_an_agent_who_spoke_without_phrases_makes_the_transcript_partial():
    c = run(raw("687f2225"))
    assert c.transcript_quality == "parcial"
    assert set(speakers(c)) == {"cliente"}
    assert any("Partial transcript" in warning for warning in c.warnings)
    agent = next(s for s in c.segments if s.kind == "agente")
    assert c.agents[agent.agent_id][1] == AGENT_NAME and agent.wrapup_genesys_id
    assert c.metrics["talk_s"] == pytest.approx(45.754)
    assert next(s for s in c.segments if s.kind == "cola").queue_id


def test_a_call_without_phrases_has_no_transcript():
    c = run(raw("87a83caa"))
    assert c.transcript_quality == "sin_transcripcion" and c.turns == []
    assert c.contained_in_bot
    assert any("without transcript" in warning for warning in c.warnings)


# Chat -----------------------------------------------------------------------------------------------------------------

def test_a_chat_with_an_agent_has_one_turn_per_message():
    c = run(raw("8d29170a"))
    assert c.channel == "chat" and c.transcript_quality == "completa"
    assert (len(c.turns), speakers(c).count("cliente"), speakers(c).count("agente")) == (16, 8, 8)
    assert c.ani is None and c.dnis is None and "acoustic_events" not in c.metrics
    assert not c.derived_to_agent and not c.contained_in_bot  # el flujo de entrada no escribe
    assert segment_kinds(c) == ["cliente", "flujo_entrada", "cola", "agente"]
    assert c.metrics["first_response_s"] == pytest.approx(19.107)
    assert (c.metrics["customer_messages"], c.metrics["agent_messages"]) == (8, 8)
    assert len(c.topics) == 2
    # Un mensaje de chat toma la media de sus frases: la negativa y dos neutras.
    sms = next(t for t in c.turns if "Tampoco he recibido ningún SMS" in t.text)
    assert sms.sentiment == pytest.approx(-1 / 3, abs=0.001)
    assert next(t for t in c.turns if t.text.startswith("No, eso es todo.")).sentiment == pytest.approx(0.5)
    assert all(t.message_id for t in c.turns)


def test_a_chat_from_the_bot_to_an_agent():
    c = run(raw("f7e79502"))
    order = speakers(c)
    assert len(c.turns) == 11 and order.count("bot") == 3
    assert max(i for i, s in enumerate(order) if s == "bot") < order.index("agente")
    assert c.derived_to_agent and c.metrics["bot_messages"] == 3
    assert c.metrics["bot_time_s"] == pytest.approx(3.026)
    assert c.turns[order.index("bot")].text.startswith("Hola, soy el asistente virtual.")


def test_a_short_chat_where_the_agent_only_says_hello():
    c = run(raw("90116482"))
    assert [t.text for t in c.turns if t.speaker == "agente"] == ["hola"]
    assert speakers(c).count("bot") == 3


def test_an_undelivered_message_keeps_its_text():
    c = run(raw("9e3ec75a"))
    failed = [t for t in c.turns if not t.delivered]
    assert [(t.speaker, t.text) for t in failed] == [("agente", "lo estoy revisando, un segundo")]
    assert c.undelivered_messages == 1 and c.transcript_quality == "completa"
    assert any("undelivered" in warning for warning in c.warnings)


def test_a_chat_with_a_delivered_and_an_undelivered_agent_message():
    c = run(raw("d74fc0d8"))
    agent = [t for t in c.turns if t.speaker == "agente"]
    assert [t.delivered for t in agent] == [True, False] and c.undelivered_messages == 1


def test_a_reconnected_chat_has_both_legs():
    c = run(raw("c870bc58"))
    assert c.reconnected
    agents = [s for s in c.segments if s.kind == "agente"]
    assert len(agents) == 2 and all(s.wrapup_genesys_id for s in agents)
    assert segment_kinds(c).count("cliente") == 2
    assert (speakers(c).count("cliente"), speakers(c).count("agente")) == (5, 4)
    assert {"Queja", "Remitir a un supervisor"} <= {t.name for t in c.topics}
    assert not any("error" in warning.lower() for warning in c.warnings)  # el 404 del segundo tramo es normal


def test_without_the_messages_api_turns_come_from_the_transcript():
    conversation = raw("9e3ec75a")
    conversation.messages_bulk = None
    c = run(conversation)
    assert len(c.turns) == 6 and set(speakers(c)) == {"cliente"}  # 6 mensajes del cliente, en su orden
    assert c.turns[0].text.startswith("Hola, buenas tardes.")
    assert c.undelivered_messages == 1  # el mensaje vacío del agente se cuenta, sin texto
    assert any("messages API" in warning for warning in c.warnings)


def test_transcript_fallback_groups_phrases_of_the_same_message():
    conversation = raw("8d29170a")
    conversation.messages_bulk = None
    assert len(run(conversation).turns) == 16


# Sentimiento ----------------------------------------------------------------------------------------------------------

def _without_sentiment_key(conversation: RawConversation) -> RawConversation:
    for document in conversation.transcripts.values():
        for transcript in (document or {}).get("transcripts", []):
            (transcript.get("analytics") or {}).pop("sentiment", None)
    return conversation


def test_turns_of_a_transcript_with_sentiment_analysis_are_neutral_by_default():
    c = run(raw("37dcbccf"))  # el análisis de sentimiento existe, pero no marca ninguna frase
    assert {t.sentiment for t in c.turns} == {0.0}


def test_turns_of_a_transcript_without_sentiment_analysis_have_no_sentiment():
    c = run(_without_sentiment_key(raw("37dcbccf")))
    assert {t.sentiment for t in c.turns} == {None}


def test_customer_sentiment_falls_back_to_the_mean_of_customer_turns():
    conversation = raw("8d29170a")
    conversation.sta.pop("sentimentScore")
    c = run(conversation)
    values = [t.sentiment for t in c.turns if t.speaker == "cliente" and t.sentiment is not None]
    assert c.customer_sentiment == pytest.approx(sum(values) / len(values))


# Identificadores y cliente --------------------------------------------------------------------------------------------

def test_the_customer_comes_from_the_external_contact_then_the_phone():
    conversation = raw("37dcbccf")
    contact = next(p["externalContactId"] for p in conversation.details["participants"] if p.get("externalContactId"))
    assert run(conversation).customer_id == ids.stable_id(ids.CUSTOMER, f"genesys:{contact}")
    for participant in conversation.details["participants"]:
        participant.pop("externalContactId", None)
    assert run(conversation).customer_id == ids.stable_id(ids.CUSTOMER, "genesys:ani:+34675075376")
    for participant in conversation.details["participants"]:
        for session in participant["sessions"]:
            session.pop("ani", None)
    assert run(conversation).customer_id is None


def test_real_identifiers_never_collide_with_the_synthetic_dataset():
    synthetic = {value for c in get_dataset() for value in (c.id, c.customer_id, c.agent_id, c.queue_id)}
    for folder in FIXTURES.glob("*-*"):
        c = run(RawConversation.from_folder(folder))
        real = {c.id, c.customer_id, *c.queues, *c.agents} - {None}
        assert all(ids.is_valid(value) for value in real), folder.name
        assert not real & synthetic, folder.name


def test_normalizing_does_not_modify_the_raw_conversation():
    conversation = raw("c870bc58")
    before = copy.deepcopy(conversation)
    run(conversation)
    assert conversation == before


def test_user_ids_identify_the_agent_even_without_an_agent_segment():
    conversation = raw("7b94988a")
    conversation.details["participants"] = [p for p in conversation.details["participants"] if p["purpose"] != "agent"]
    c = run(conversation)
    agent = [t for t in c.turns if t.speaker == "agente"]
    assert len(agent) == 2
    assert {c.agents[t.agent_id][1] for t in agent} == {AGENT_NAME}


def test_transcript_fallback_joins_the_phrases_of_each_message():
    with_api = run(raw("8d29170a"))
    conversation = raw("8d29170a")
    conversation.messages_bulk = None
    fallback = run(conversation)
    comparable = lambda text: "".join(ch for ch in text.casefold() if ch.isalnum())  # noqa: E731
    assert [comparable(t.text) for t in fallback.turns] == [comparable(t.text) for t in with_api.turns]
    assert [t.speaker for t in fallback.turns] == [t.speaker for t in with_api.turns]


def test_a_transcript_repeated_in_two_communications_counts_once():
    conversation = raw("37dcbccf")
    (document,) = conversation.transcripts.values()
    conversation.transcripts["otra-comunicacion"] = copy.deepcopy(document)
    c = run(conversation)
    assert len(c.turns) == 12 and len(c.topics) == 4
