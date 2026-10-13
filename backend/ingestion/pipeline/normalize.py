"""Normalización de una conversación de Genesys al modelo de la ingesta (FE011, criterios 7, 8 y 9).

Funciones puras: de las respuestas crudas (`RawConversation`) y un resolutor de nombres a `NormalizedConversation`, sin
red ni base de datos. Reglas (ver la spec y los tipos de conversación observados el 2026-10-12):

- Turnos de voz: una frase de transcripción por turno, uniendo todas las transcripciones de la conversación sin
  duplicados (`transcriptId`) y ordenadas por instante.
- Turnos de chat: un mensaje por turno, de la API de mensajes (texto completo, también de los no entregados). Si no
  respondió, se agrupan las frases de la transcripción por `messageID`.
- Hablantes: `external` → cliente. Una frase `internal` es del agente si trae `userIds`; si no, del agente si cae en su
  tramo y del bot en otro caso. En chat, un mensaje saliente con autor (`createdBy`) es del agente y uno sin autor
  (`originatingEntity: Bot`, el flujo de entrada), del bot.
- Sentimiento: el de la frase si Genesys lo marca; neutro (`0`) si la transcripción tiene análisis de sentimiento y no
  la marca (hipótesis de la spec); vacío si la transcripción no tiene análisis. En chat, la media de las frases del
  mensaje.
- Identificadores v5 derivados del identificador de Genesys (`genesys:<id>`), para que la carga sea idempotente.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Protocol

from app import ids
from ingestion.pipeline.raw import RawConversation

CUSTOMER_PURPOSES = {"customer", "external"}
KIND_BY_PURPOSE = {"customer": "cliente", "external": "cliente", "workflow": "flujo_entrada", "ivr": "ivr",
                   "acd": "cola", "agent": "agente"}
_KIND_ORDER = ["cliente", "flujo_entrada", "ivr", "cola", "agente", "externo"]
CHANNEL_BY_MEDIA = {"voice": "voz", "message": "chat", "chat": "chat"}
FAILED = "delivery-failed"

# Métricas de sesión de Genesys (milisegundos) → clave de `metrics` (segundos). Se suman por tramo, salvo los tiempos
# medios (media) y los primeros contactos (mínimo).
TIME_METRICS = {
    "tIvr": "ivr_s", "tFlow": "flow_s", "tAcd": "queue_wait_s", "tAlert": "alert_s", "tTalk": "talk_s",
    "tHeld": "hold_s", "tAcw": "acw_s", "tHandle": "handle_s", "tAbandon": "abandon_s",
    "tFirstResponse": "first_response_s", "tFirstEngagement": "first_engagement_s",
    "tAverageAgentResponseTime": "avg_agent_response_s", "tAverageCustomerResponseTime": "avg_customer_response_s",
}
COUNT_METRICS = {"nOffered": "offered", "nTransferred": "transfers"}
STA_PERCENTAGES = {"agentDurationPercentage": "agent", "customerDurationPercentage": "customer",
                   "silenceDurationPercentage": "silence", "ivrDurationPercentage": "ivr",
                   "acdDurationPercentage": "acd", "otherDurationPercentage": "other"}


# Nombres ---------------------------------------------------------------------------------------------------------------

class Names(Protocol):
    def queue(self, genesys_id: str) -> str | None: ...
    def user(self, genesys_id: str) -> str | None: ...
    def wrapup(self, genesys_id: str) -> str | None: ...
    def division(self, genesys_id: str) -> str | None: ...


@dataclass
class DictNames:
    queues: dict[str, str] = field(default_factory=dict)
    users: dict[str, str] = field(default_factory=dict)
    wrapups: dict[str, str] = field(default_factory=dict)
    divisions: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_catalog(cls, catalog: dict) -> "DictNames":
        return cls(**{kind: dict(catalog.get(kind, {})) for kind in ("queues", "users", "wrapups", "divisions")})

    def queue(self, genesys_id: str) -> str | None:
        return self.queues.get(genesys_id)

    def user(self, genesys_id: str) -> str | None:
        return self.users.get(genesys_id)

    def wrapup(self, genesys_id: str) -> str | None:
        return self.wrapups.get(genesys_id)

    def division(self, genesys_id: str) -> str | None:
        return self.divisions.get(genesys_id)


# Modelo normalizado ----------------------------------------------------------------------------------------------------

@dataclass
class Segment:
    seq: int
    kind: str
    name: str | None
    genesys_participant_id: str | None
    started_at: datetime
    ended_at: datetime | None
    queue_id: str | None = None
    agent_id: str | None = None
    flow_genesys_id: str | None = None
    flow_name: str | None = None
    flow_type: str | None = None
    wrapup_genesys_id: str | None = None
    disconnect_type: str | None = None
    exit_reason: str | None = None
    transfer_target: str | None = None


@dataclass
class Turn:
    seq: int
    speaker: str
    text: str
    offset_s: float
    sentiment: float | None = None
    delivered: bool = True
    agent_id: str | None = None
    message_id: str | None = None
    confidence: float | None = None


@dataclass
class TopicHit:
    seq: int
    genesys_topic_id: str
    name: str
    phrase: str | None
    speaker: str | None
    turn_seq: int | None
    offset_s: float
    confidence: float | None


@dataclass
class NormalizedConversation:
    id: str
    genesys_id: str
    channel: str
    started_at: datetime
    ended_at: datetime
    duration_s: int
    direction: str | None
    external_tag: str | None
    ani: str | None
    dnis: str | None
    customer_id: str | None
    transcript_quality: str
    disconnect_type: str | None
    transferred: bool
    reconnected: bool
    contained_in_bot: bool
    derived_to_agent: bool
    abandoned_in_queue: bool
    undelivered_messages: int
    customer_sentiment: float | None
    mos: float | None
    metrics: dict
    segments: list[Segment]
    turns: list[Turn]
    topics: list[TopicHit]
    division_ids: list[str]
    # Catálogos referenciados: identificador de la plataforma → (identificador de Genesys, nombre).
    queues: dict[str, tuple[str, str]]
    agents: dict[str, tuple[str, str]]
    # Catálogos sin entidad en la plataforma: identificador de Genesys → nombre (y tipo, en los flujos).
    flows: dict[str, tuple[str, str | None]]
    wrapups: dict[str, str]
    divisions: dict[str, str]
    warnings: list[str]
    raw: RawConversation


# Utilidades ------------------------------------------------------------------------------------------------------------

def _time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _ms(value: datetime) -> float:
    return value.timestamp() * 1000


def _phone(value: str | None) -> str | None:
    return value.removeprefix("tel:") if value else None


def _offset(instant_ms: float, start_ms: float) -> float:
    return round(max(0.0, (instant_ms - start_ms) / 1000), 3)


def platform_id(prefix: str, genesys_id: str) -> str:
    return ids.stable_id(prefix, f"genesys:{genesys_id}")


@dataclass
class _Phrase:
    order: int
    transcript_id: str
    index: int
    text: str
    start_ms: float
    end_ms: float
    purpose: str
    user_ids: list[str]
    confidence: float | None
    message_id: str | None
    sentiment: float | None


class _Builder:
    def __init__(self, raw: RawConversation, names: Names):
        self.raw, self.names = raw, names
        self.details = raw.details
        self.started_at = _time(self.details["conversationStart"])
        self.ended_at = _time(self.details.get("conversationEnd")) or self.started_at
        self.start_ms = _ms(self.started_at)
        self.sessions = [(p, s) for p in self.details.get("participants", []) for s in p.get("sessions", [])]
        self.queues: dict[str, tuple[str, str]] = {}
        self.agents: dict[str, tuple[str, str]] = {}
        self.flows: dict[str, tuple[str, str | None]] = {}
        self.wrapups: dict[str, str] = {}
        self.warnings: list[str] = []

    # Catálogos ---------------------------------------------------------------------------------------------------------

    def _named(self, kind: str, genesys_id: str, fallback: str | None = None) -> str:
        name = getattr(self.names, kind)(genesys_id) or fallback
        if not name:
            self.warnings.append(f"Name not resolved ({kind}): the Genesys identifier {genesys_id} is used")
        return name or genesys_id

    def queue_id(self, genesys_id: str, fallback: str | None = None) -> str:
        queue_id = platform_id(ids.QUEUE, genesys_id)
        if queue_id not in self.queues:
            self.queues[queue_id] = (genesys_id, self._named("queue", genesys_id, fallback))
        return queue_id

    def agent_id(self, user_id: str, fallback: str | None = None) -> str:
        agent_id = platform_id(ids.AGENT, user_id)
        if agent_id not in self.agents:
            self.agents[agent_id] = (user_id, self._named("user", user_id, fallback))
        return agent_id

    # Tramos ------------------------------------------------------------------------------------------------------------

    def segments(self) -> list[Segment]:
        built = []
        for participant, session in self.sessions:
            parts = session.get("segments", [])
            if not parts:
                continue
            kind = KIND_BY_PURPOSE.get(participant.get("purpose"), "externo")
            starts = [_time(p["segmentStart"]) for p in parts]
            ends = [_time(p.get("segmentEnd")) for p in parts]
            interact = [p for p in parts if p.get("segmentType") == "interact" and p.get("disconnectType")]
            disconnects = interact or [p for p in parts if p.get("disconnectType")]
            segment = Segment(seq=0, kind=kind, name=participant.get("participantName"),
                              genesys_participant_id=participant.get("participantId"), started_at=min(starts),
                              ended_at=max(ends) if all(ends) else None,
                              disconnect_type=disconnects[-1]["disconnectType"] if disconnects else None)
            queue = next((p["queueId"] for p in parts if p.get("queueId")), None)
            if queue and kind in ("cola", "agente"):
                segment.queue_id = self.queue_id(queue, participant.get("participantName") if kind == "cola" else None)
                if kind == "cola":
                    segment.name = self.queues[segment.queue_id][1]
            if kind == "agente" and participant.get("userId"):
                segment.agent_id = self.agent_id(participant["userId"], participant.get("participantName"))
                segment.name = self.agents[segment.agent_id][1]
            wrapup = next((p["wrapUpCode"] for p in parts if p.get("wrapUpCode")), None)
            if wrapup:
                segment.wrapup_genesys_id = wrapup
                self.wrapups.setdefault(wrapup, self._named("wrapup", wrapup))
            flow = session.get("flow")
            if flow:
                segment.flow_genesys_id, segment.flow_name = flow.get("flowId"), flow.get("flowName")
                segment.flow_type, segment.exit_reason = flow.get("flowType"), flow.get("exitReason")
                segment.transfer_target = flow.get("transferTargetName")
                if segment.flow_genesys_id:
                    self.flows[segment.flow_genesys_id] = (segment.flow_name or segment.flow_genesys_id,
                                                           segment.flow_type)
            built.append((segment, session))
        built.sort(key=lambda item: (item[0].started_at, _KIND_ORDER.index(item[0].kind)))
        for seq, (segment, _) in enumerate(built):
            segment.seq = seq
        self.session_of = {id(segment): session for segment, session in built}
        return [segment for segment, _ in built]

    def metrics_of(self, segment: Segment) -> dict[str, list[float]]:
        found: dict[str, list[float]] = {}
        for metric in self.session_of[id(segment)].get("metrics", []):
            found.setdefault(metric["name"], []).append(metric["value"])
        return found

    def is_bot(self, segment: Segment) -> bool:
        if segment.kind == "ivr":
            return True
        # El flujo de entrada de mensajería solo es un bot si escribe (chats bot → agente del 2026-10-12).
        return segment.kind == "flujo_entrada" and sum(self.metrics_of(segment).get("oMessageCount", [])) > 0

    # Transcripciones ---------------------------------------------------------------------------------------------------

    def phrases(self) -> tuple[list[_Phrase], list[tuple[dict, dict[tuple[str, int], _Phrase]]], dict]:
        """Frases de todas las transcripciones (sin repetir `transcriptId`), sus análisis y la acústica."""
        phrases, analyses, acoustics, seen, order = [], [], {}, set(), 0
        for document in self.raw.transcripts.values():
            for transcript in (document or {}).get("transcripts", []):
                transcript_id = transcript.get("transcriptId")
                if transcript_id in seen:
                    continue
                seen.add(transcript_id)
                analytics = transcript.get("analytics") or {}
                has_sentiment = "sentiment" in analytics
                by_index = {}
                for raw_phrase in transcript.get("phrases", []):
                    index = raw_phrase.get("phraseIndex", len(by_index))
                    duration = (raw_phrase.get("duration") or {}).get("milliseconds", 0)
                    phrase = _Phrase(
                        order=order, transcript_id=transcript_id, index=index, text=raw_phrase.get("text") or "",
                        start_ms=raw_phrase["startTimeMs"], end_ms=raw_phrase["startTimeMs"] + duration,
                        purpose=raw_phrase.get("participantPurpose", ""), user_ids=raw_phrase.get("userIds") or [],
                        confidence=raw_phrase.get("confidence"), message_id=raw_phrase.get("messageID"),
                        sentiment=0.0 if has_sentiment else None)
                    order += 1
                    phrases.append(phrase)
                    by_index[(transcript_id, index)] = phrase
                for entry in analytics.get("sentiment") or []:
                    target = _phrase_for(entry, by_index.values())
                    if target is not None and entry.get("sentiment") is not None:
                        target.sentiment = float(entry["sentiment"])
                analyses.append((analytics, by_index))
                for event in analytics.get("acoustics") or []:
                    key = f"{event.get('eventType')}_{event.get('participant')}"
                    acoustics[key] = acoustics.get(key, 0) + 1
        return phrases, analyses, acoustics


def _comparable(text: str | None) -> str:
    return "".join(ch for ch in (text or "").casefold() if ch.isalnum())


def _phrase_for(entry: dict, phrases) -> "_Phrase | None":
    """Frase a la que se refiere una entrada de sentimiento o de tema.

    Su `phraseIndex` no es el de la frase (en `7b94988a`, el sentimiento de «Vale, muchas gracias.» trae el 3 y la frase
    es la 5), así que se enlaza por lado, instante y texto: la frase del mismo lado que contiene el instante, y entre
    varias (las frases de un mismo mensaje de chat comparten instante), la que contiene el texto.
    """
    start = entry.get("startTimeMs")
    side = [p for p in phrases if p.purpose == entry.get("participant")]
    at = [p for p in side if start is not None and p.start_ms <= start <= max(p.end_ms, p.start_ms)]
    wanted = _comparable(entry.get("phrase") or entry.get("transcriptPhrase"))
    with_text = [p for p in at if wanted and (wanted in _comparable(p.text) or _comparable(p.text) in wanted)]
    preceding = [p for p in side if start is not None and p.start_ms <= start]
    found = with_text or at or preceding
    return max(found, key=lambda p: (p.start_ms, p.order)) if found else None


def _agent_at(segments: list[Segment], instant: datetime) -> Segment | None:
    for segment in segments:
        if segment.kind == "agente" and segment.started_at <= instant and (segment.ended_at is None
                                                                           or instant <= segment.ended_at):
            return segment
    return None


def normalize(raw: RawConversation, names: Names) -> NormalizedConversation:
    b = _Builder(raw, names)
    details = raw.details
    segments = b.segments()
    customer_sessions = [s for p, s in b.sessions if p.get("purpose") in CUSTOMER_PURPOSES]
    media = next((s.get("mediaType") for s in customer_sessions), None) or b.sessions[0][1].get("mediaType")
    channel = CHANNEL_BY_MEDIA.get(media, "voz")
    bots = [s for s in segments if b.is_bot(s)]
    phrases, analyses, acoustics = b.phrases()

    # Turnos ------------------------------------------------------------------------------------------------------------
    turns: list[Turn] = []
    turn_of_phrase: dict[int, int] = {}  # orden de la frase → índice del turno en `turns`
    undelivered = 0

    def internal_speaker(phrase: _Phrase) -> tuple[str, str | None]:
        if phrase.user_ids:
            return "agente", b.agent_id(phrase.user_ids[0])
        agent = _agent_at(segments, _time_ms(phrase.start_ms))
        if agent:
            return "agente", agent.agent_id
        if bots:
            return "bot", None
        return ("agente", next(s.agent_id for s in segments if s.kind == "agente")) \
            if any(s.kind == "agente" for s in segments) else ("sistema", None)

    def speaker_of(phrase: _Phrase) -> tuple[str, str | None]:
        if phrase.purpose == "external":
            return "cliente", None
        if phrase.purpose == "internal":
            return internal_speaker(phrase)
        return "sistema", None

    if channel == "voz":
        for phrase in sorted(phrases, key=lambda p: (p.start_ms, p.order)):
            if not phrase.text.strip():
                continue
            speaker, agent_id = speaker_of(phrase)
            turn_of_phrase[phrase.order] = len(turns)
            turns.append(Turn(seq=0, speaker=speaker, text=phrase.text, offset_s=_offset(phrase.start_ms, b.start_ms),
                              sentiment=phrase.sentiment, agent_id=agent_id, confidence=phrase.confidence))
    else:
        by_message: dict[str, list[_Phrase]] = {}
        for phrase in phrases:
            if phrase.message_id:
                by_message.setdefault(phrase.message_id, []).append(phrase)

        def message_sentiment(message_id: str) -> float | None:
            values = [p.sentiment for p in by_message.get(message_id, []) if p.sentiment is not None]
            return round(mean(values), 4) if values else None

        if raw.messages_bulk is not None:
            entities = sorted(enumerate(raw.messages_bulk), key=lambda item: (item[1].get("timestamp", ""), item[0]))
            for _, entity in entities:
                message = entity.get("normalizedMessage") or {}
                text = message.get("text") or entity.get("textBody") or ""
                if not text.strip():
                    continue
                if entity.get("direction") == "inbound":
                    speaker, agent_id = "cliente", None
                elif (entity.get("createdBy") or {}).get("id"):
                    speaker, agent_id = "agente", b.agent_id(entity["createdBy"]["id"])
                else:
                    speaker, agent_id = "bot", None
                delivered = entity.get("status") != FAILED
                undelivered += not delivered
                turn_index = len(turns)
                for phrase in by_message.get(entity.get("id"), []):
                    turn_of_phrase[phrase.order] = turn_index
                turns.append(Turn(seq=0, speaker=speaker, text=text, delivered=delivered, agent_id=agent_id,
                                  offset_s=_offset(_ms(_time(entity["timestamp"])), b.start_ms),
                                  message_id=entity.get("id"), sentiment=message_sentiment(entity.get("id"))))
        else:
            b.warnings.append("The messages API did not respond: turns built from the transcript")
            groups = sorted(by_message.items(), key=lambda item: min((p.start_ms, p.order) for p in item[1]))
            for message_id, group in groups:
                group.sort(key=lambda p: (p.start_ms, p.order))
                text = " ".join(p.text.strip() for p in group if p.text.strip())
                if not text:
                    undelivered += 1  # mensaje sin texto: no entregado, sin texto que mostrar
                    continue
                speaker, agent_id = speaker_of(group[0])
                for phrase in group:
                    turn_of_phrase[phrase.order] = len(turns)
                turns.append(Turn(seq=0, speaker=speaker, text=text, agent_id=agent_id, message_id=message_id,
                                  offset_s=_offset(group[0].start_ms, b.start_ms),
                                  sentiment=message_sentiment(message_id)))
    # Orden estable por instante; el índice de cada turno pasa a ser su `seq`.
    order = sorted(range(len(turns)), key=lambda i: (turns[i].offset_s, i))
    position = {old: new for new, old in enumerate(order)}
    turns = [turns[i] for i in order]
    for seq, turn in enumerate(turns):
        turn.seq = seq
    turn_of_phrase = {phrase: position[index] for phrase, index in turn_of_phrase.items()}

    # Temas detectados --------------------------------------------------------------------------------------------------
    topics: list[TopicHit] = []
    seen_topics = set()
    for analytics, by_index in analyses:
        candidates = sorted(by_index.values(), key=lambda p: (p.start_ms, p.order))
        for topic in analytics.get("topics") or []:
            key = (topic.get("topicId"), topic.get("startTimeMs"), topic.get("transcriptPhrase"),
                   topic.get("participant"))
            if key in seen_topics:
                continue
            seen_topics.add(key)
            start = topic.get("startTimeMs", b.start_ms)
            phrase = _phrase_for(topic, [p for p in candidates if p.order in turn_of_phrase])
            turn_seq = turn_of_phrase.get(phrase.order) if phrase else None
            if turn_seq is not None:
                speaker = turns[turn_seq].speaker
            else:
                speaker = "cliente" if topic.get("participant") == "external" else ("agente" if topic.get("userId")
                                                                                    else "bot")
            confidence = topic.get("confidence")
            topics.append(TopicHit(seq=0, genesys_topic_id=topic.get("topicId", ""), name=topic.get("topicName", ""),
                                   phrase=topic.get("transcriptPhrase"), speaker=speaker, turn_seq=turn_seq,
                                   offset_s=_offset(start, b.start_ms),
                                   confidence=confidence / 100 if confidence is not None else None))
    topics.sort(key=lambda t: t.offset_s)
    for seq, topic in enumerate(topics):
        topic.seq = seq

    # Métricas ----------------------------------------------------------------------------------------------------------
    values: dict[str, list[float]] = {}
    for segment in segments:
        for name, found in b.metrics_of(segment).items():
            values.setdefault(name, []).extend(found)
    metrics: dict = {}
    for name, key in TIME_METRICS.items():
        if name in values:
            found = values[name]
            total = mean(found) if name.startswith("tAverage") else min(found) if name.startswith("tFirst") \
                else sum(found)
            metrics[key] = round(total / 1000, 3)
    for name, key in COUNT_METRICS.items():
        if name in values:
            metrics[key] = int(sum(values[name]))
    if bots:
        bot_ms = sum(sum(b.metrics_of(s).get("tIvr" if s.kind == "ivr" else "tFlow", [])) for s in bots)
        metrics["bot_time_s"] = round(bot_ms / 1000, 3)
        metrics["bot_turns"] = sum(1 for t in turns if t.speaker == "bot")
    if channel == "chat":
        if raw.messages_bulk is not None:
            outbound = [e for e in raw.messages_bulk if e.get("direction") == "outbound"]
            metrics["customer_messages"] = sum(1 for e in raw.messages_bulk if e.get("direction") == "inbound")
            metrics["agent_messages"] = sum(1 for e in outbound if (e.get("createdBy") or {}).get("id"))
            metrics["bot_messages"] = len(outbound) - metrics["agent_messages"]
        else:
            by_kind = {kind: sum(sum(b.metrics_of(s).get("oMessageCount", [])) for s in segments if s.kind == kind)
                       for kind in ("cliente", "agente", "flujo_entrada")}
            metrics["customer_messages"], metrics["agent_messages"] = by_kind["cliente"], by_kind["agente"]
            metrics["bot_messages"] = by_kind["flujo_entrada"]
        metrics["undelivered_messages"] = undelivered
    sta = raw.sta or {}
    if sta.get("participantMetrics"):
        metrics["sta_time_pct"] = {key: sta["participantMetrics"][name] for name, key in STA_PERCENTAGES.items()
                                   if name in sta["participantMetrics"]}
    for name, key in (("sentimentTrend", "sentiment_trend"), ("sentimentTrendClass", "sentiment_trend_class")):
        if name in sta:
            metrics[key] = sta[name]
    if sta.get("empathyScores"):
        empathy = [{"agent_id": b.agent_id(e["userId"]) if e.get("userId") else None, "score": e["score"]}
                   for e in sta["empathyScores"] if e.get("score") is not None]
        if empathy:
            metrics["empathy"] = empathy
    if acoustics:
        metrics["acoustic_events"] = acoustics
    if channel == "voz" and turns:
        confidence: dict[str, list[float]] = {}
        for turn in turns:
            if turn.confidence is not None:
                confidence.setdefault(turn.speaker, []).append(turn.confidence)
        metrics["asr_confidence"] = {speaker: round(mean(found), 4) for speaker, found in confidence.items()}
    if details.get("mediaStatsMinConversationRFactor") is not None:
        metrics["r_factor"] = details["mediaStatsMinConversationRFactor"]

    # Conversación ------------------------------------------------------------------------------------------------------
    customer_participants = [p for p in details.get("participants", []) if p.get("purpose") in CUSTOMER_PURPOSES]
    ani = _phone(next((s.get("ani") for s in customer_sessions if s.get("ani")), None))
    dnis = _phone(next((s.get("dnis") for s in customer_sessions if s.get("dnis")), None))
    contact = next((p["externalContactId"] for p in customer_participants if p.get("externalContactId")), None)
    customer_id = (platform_id(ids.CUSTOMER, contact) if contact
                   else platform_id(ids.CUSTOMER, f"ani:{ani}") if ani else None)
    customer_segments = [s for s in segments if s.kind == "cliente"]
    has_queue = any(s.kind == "cola" for s in segments)
    attended = any(s.kind == "agente" and any(p.get("segmentType") == "interact"
                                              for p in b.session_of[id(s)].get("segments", [])) for s in segments)
    speaker_set = {t.speaker for t in turns}
    agent_spoke = any(
        (sum(b.metrics_of(s).get("tTalk", [])) > 0) if channel == "voz"
        else sum(b.metrics_of(s).get("oMessageCount", [])) - sum(b.metrics_of(s).get("nError", [])) > 0
        for s in segments if s.kind == "agente")
    bot_spoke = any((sum(b.metrics_of(s).get("tIvr", [])) > 0) if s.kind == "ivr" else True for s in bots)
    if not turns:
        quality = "sin_transcripcion"
        b.warnings.append("Conversation without transcript")
    elif (agent_spoke and "agente" not in speaker_set) or (bot_spoke and "bot" not in speaker_set):
        quality = "parcial"
        missing = [who for who, spoke in (("agente", agent_spoke), ("bot", bot_spoke)) if spoke and who not in speaker_set]
        b.warnings.append(f"Partial transcript: {' and '.join(missing)} took part without phrases")
    else:
        quality = "completa"
    if undelivered:
        b.warnings.append(f"{undelivered} undelivered message(s)")
    customer_values = [t.sentiment for t in turns if t.speaker == "cliente" and t.sentiment is not None]
    customer_sentiment = sta.get("sentimentScore")
    if customer_sentiment is None and customer_values:
        customer_sentiment = mean(customer_values)
    division_ids = list(details.get("divisionIds", []))

    return NormalizedConversation(
        id=platform_id(ids.CONVERSATION, raw.id), genesys_id=raw.id, channel=channel,
        started_at=b.started_at, ended_at=b.ended_at,
        duration_s=round((b.ended_at - b.started_at).total_seconds()),
        direction=details.get("originatingDirection"), external_tag=details.get("externalTag"),
        ani=ani, dnis=dnis, customer_id=customer_id, transcript_quality=quality,
        disconnect_type=customer_segments[-1].disconnect_type if customer_segments else None,
        transferred=any(s.disconnect_type == "transfer" or s.exit_reason == "TRANSFER" for s in segments),
        reconnected=len(customer_segments) > 1,
        contained_in_bot=bool(bots) and not has_queue, derived_to_agent=bool(bots) and has_queue,
        abandoned_in_queue=has_queue and not attended, undelivered_messages=undelivered,
        customer_sentiment=customer_sentiment, mos=details.get("mediaStatsMinConversationMos"), metrics=metrics,
        segments=segments, turns=turns, topics=topics, division_ids=division_ids,
        queues=b.queues, agents=b.agents, flows=b.flows, wrapups=b.wrapups,
        divisions={d: b._named("division", d) for d in division_ids}, warnings=b.warnings, raw=raw)


def _time_ms(value: float) -> datetime:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
