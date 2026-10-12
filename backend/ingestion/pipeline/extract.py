"""Extracción de Genesys Cloud (FE011, criterio 6): búsqueda por tramos y descarga tolerante de cada conversación."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ingestion.genesys.client import GenesysAuthError, GenesysClient, GenesysError, GenesysNotFound
from ingestion.pipeline.normalize import CHANNEL_BY_MEDIA, CUSTOMER_PURPOSES
from ingestion.pipeline.raw import RawConversation

MAX_CHUNK = timedelta(days=7)  # la consulta de detalles de analítica rechaza intervalos más largos
PAGE_SIZE = 100
BULK_SIZE = 100
QUERY = "/api/v2/analytics/conversations/details/query"
TRANSCRIBED_MEDIA = {"voice", "message", "chat"}
IN_PROGRESS, OTHER_MEDIA, OTHER_CHANNEL = "en curso", "otro medio", "otro canal"


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def split_interval(start: datetime, end: datetime, chunk: timedelta = MAX_CHUNK) -> list[tuple[datetime, datetime]]:
    chunks, cursor = [], start
    while cursor < end:
        chunks.append((cursor, min(cursor + chunk, end)))
        cursor = chunks[-1][1]
    return chunks


@dataclass
class SearchResult:
    found: list[dict] = field(default_factory=list)  # detalle de analítica de cada conversación a descargar
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (identificador de Genesys, motivo)


def _channel(details: dict) -> str | None:
    sessions = [s for p in details.get("participants", []) for s in p.get("sessions", [])
                if p.get("purpose") in CUSTOMER_PURPOSES]
    sessions = sessions or [s for p in details.get("participants", []) for s in p.get("sessions", [])]
    return CHANNEL_BY_MEDIA.get(sessions[0].get("mediaType")) if sessions else None


def search(client: GenesysClient, start: datetime, end: datetime, channels: set[str] | list[str],
           page_size: int = PAGE_SIZE, on_chunk=None) -> SearchResult:
    result, seen = SearchResult(), set()
    chunks = split_interval(start, end)
    for number, (chunk_start, chunk_end) in enumerate(chunks, 1):
        page, total, in_chunk = 1, None, 0
        while total is None or (page - 1) * page_size < total:
            body = client.post(QUERY, json={"interval": f"{_iso(chunk_start)}/{_iso(chunk_end)}", "order": "asc",
                                            "orderBy": "conversationStart",
                                            "paging": {"pageSize": page_size, "pageNumber": page}}) or {}
            total = body.get("totalHits", 0)
            rows = body.get("conversations", [])
            if not rows:
                break
            for details in rows:
                genesys_id = details["conversationId"]
                if genesys_id in seen:  # una conversación que cruza el límite entre tramos aparece en los dos
                    continue
                seen.add(genesys_id)
                in_chunk += 1
                channel = _channel(details)
                if not details.get("conversationEnd"):
                    result.skipped.append((genesys_id, IN_PROGRESS))
                elif channel is None:
                    result.skipped.append((genesys_id, OTHER_MEDIA))
                elif channel not in channels:
                    result.skipped.append((genesys_id, OTHER_CHANNEL))
                else:
                    result.found.append(details)
            page += 1
        if on_chunk:
            on_chunk(number, len(chunks), chunk_start, chunk_end, in_chunk)
    return result


def fetch(client: GenesysClient, details: dict) -> RawConversation:
    """Speech & Text Analytics, transcripciones de cada comunicación del cliente y, en chat, sus mensajes.

    Un `404` de STA o de una transcripción no es un error (la conversación no tiene análisis, o sus frases llegaron en
    la transcripción de otra comunicación). Si falla la API de mensajes, la normalización usa la transcripción. Los
    errores de autenticación nunca se ocultan.
    """
    genesys_id = details["conversationId"]
    try:
        sta = client.get(f"/api/v2/speechandtextanalytics/conversations/{genesys_id}") or {}
    except GenesysNotFound:
        sta = {}
    transcripts: dict[str, dict | None] = {}
    is_message = False
    for participant in details.get("participants", []):
        for session in participant.get("sessions", []):
            is_message |= session.get("mediaType") == "message"
            if participant.get("purpose") not in CUSTOMER_PURPOSES or session.get("mediaType") not in TRANSCRIBED_MEDIA:
                continue
            path = (f"/api/v2/speechandtextanalytics/conversations/{genesys_id}/communications/"
                    f"{session['sessionId']}/transcripturl")
            try:
                transcripts[session["sessionId"]] = client.get_signed(client.get(path)["url"])
            except GenesysNotFound:
                transcripts[session["sessionId"]] = None
    raw = RawConversation(details=details, sta=sta, transcripts=transcripts)
    if is_message:
        try:
            raw.messages = client.get(f"/api/v2/conversations/messages/{genesys_id}")
            message_ids = [m["messageId"] for p in raw.messages.get("participants", [])
                           for m in p.get("messages", []) if m.get("messageId")]
            entities = []
            for i in range(0, len(message_ids), BULK_SIZE):
                body = client.post(f"/api/v2/conversations/messages/{genesys_id}/messages/bulk",
                                   json=message_ids[i:i + BULK_SIZE]) or {}
                entities += body.get("entities", [])
            raw.messages_bulk = entities
        except GenesysAuthError:
            raise
        except GenesysError:
            raw.messages_bulk = None
    return raw


class GenesysNames:
    """Nombres de colas, usuarios, wrap-ups y divisiones con una caché por ejecución (criterio 8)."""
    PATHS = {"queue": "/api/v2/routing/queues/{}", "user": "/api/v2/users/{}",
             "wrapup": "/api/v2/routing/wrapupcodes/{}", "division": "/api/v2/authorization/divisions/{}"}

    def __init__(self, client: GenesysClient):
        self._client = client
        self._cache: dict[tuple[str, str], str | None] = {}

    def _lookup(self, kind: str, genesys_id: str) -> str | None:
        key = (kind, genesys_id)
        if key not in self._cache:
            try:
                self._cache[key] = (self._client.get(self.PATHS[kind].format(genesys_id)) or {}).get("name")
            except GenesysAuthError:
                raise
            except GenesysError:
                self._cache[key] = None
        return self._cache[key]

    def queue(self, genesys_id: str) -> str | None:
        return self._lookup("queue", genesys_id)

    def user(self, genesys_id: str) -> str | None:
        return self._lookup("user", genesys_id)

    def wrapup(self, genesys_id: str) -> str | None:
        return self._lookup("wrapup", genesys_id)

    def division(self, genesys_id: str) -> str | None:
        return self._lookup("division", genesys_id)
