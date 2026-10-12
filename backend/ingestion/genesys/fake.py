"""Genesys Cloud falso para los tests y las pruebas de rendimiento (FE011). Nunca toca la red.

Sirve, con `httpx.MockTransport`, las rutas que usa la ingesta a partir de conversaciones cargadas en memoria (las
fixtures de `tests/fixtures/genesys/`, capturadas de la cuenta del laboratorio): OAuth, consulta de detalles de
analítica (con el límite de 7 días), Speech & Text Analytics, URL de transcripción firmadas, mensajes y catálogos.

`fail(método, ruta_o_url, *respuestas)` programa respuestas para las siguientes llamadas a esa ruta: un código, una
tupla `(código, cabeceras[, cuerpo])` o una excepción de httpx.
"""
import base64
import itertools
import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import httpx

MAX_INTERVAL = timedelta(days=7)
_ROUTES = [
    ("POST", re.compile(r"^/oauth/token$"), "_token"),
    ("GET", re.compile(r"^/api/v2/organizations/me$"), "_organization"),
    ("POST", re.compile(r"^/api/v2/analytics/conversations/details/query$"), "_details_query"),
    ("GET", re.compile(r"^/api/v2/analytics/conversations/(?P<cid>[^/]+)/details$"), "_details"),
    ("GET", re.compile(r"^/api/v2/speechandtextanalytics/conversations/(?P<cid>[^/]+)$"), "_sta"),
    ("GET", re.compile(r"^/api/v2/speechandtextanalytics/conversations/(?P<cid>[^/]+)/communications/(?P<comm>[^/]+)"
                       r"/transcripturl$"), "_transcript_url"),
    ("GET", re.compile(r"^/api/v2/conversations/messages/(?P<cid>[^/]+)$"), "_messages"),
    ("POST", re.compile(r"^/api/v2/conversations/messages/(?P<cid>[^/]+)/messages/bulk$"), "_messages_bulk"),
    ("GET", re.compile(r"^/api/v2/routing/queues/(?P<id>[^/]+)$"), "_queue"),
    ("GET", re.compile(r"^/api/v2/users/(?P<id>[^/]+)$"), "_user"),
    ("GET", re.compile(r"^/api/v2/routing/wrapupcodes/(?P<id>[^/]+)$"), "_wrapup"),
    ("GET", re.compile(r"^/api/v2/authorization/divisions/(?P<id>[^/]+)$"), "_division"),
]


@dataclass
class FakeConversation:
    """Respuestas de Genesys para una conversación, tal como se guardan en una carpeta de fixtures."""
    details: dict
    sta: dict = field(default_factory=dict)
    # Documento de transcripción de cada comunicación (con una o varias transcripciones dentro, algunas vacías);
    # `None` = la URL de transcripción responde `404`.
    transcripts: dict[str, dict | None] = field(default_factory=dict)
    messages: dict | None = None
    messages_bulk: list[dict] | None = None

    @property
    def id(self) -> str:
        return self.details["conversationId"]

    @classmethod
    def load(cls, folder: Path) -> "FakeConversation":
        read = lambda name: json.loads((folder / name).read_text()) if (folder / name).exists() else None  # noqa: E731
        return cls(details=read("details.json"), sta=read("sta.json") or {}, transcripts=read("transcripts.json") or {},
                   messages=read("messages.json"), messages_bulk=read("messages_bulk.json"))


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class FakeGenesys:
    bucket_host = "fake-transcripts.s3.eu-west-1.amazonaws.com"

    def __init__(self, client_id: str = "cliente", client_secret: str = "secreto", token_ttl_s: int = 86399,
                 conversations: list[FakeConversation] | None = None, catalog: dict | None = None):
        self._credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        self._token_ttl = token_ttl_s
        self._tokens = itertools.count(1)
        self.issued_tokens: list[str] = []
        self.conversations = {c.id: c for c in conversations or []}
        self.catalog = catalog or {"organization": {"id": "org-falsa", "name": "Laboratorio"},
                                   "queues": {}, "users": {}, "wrapups": {}, "divisions": {}}
        self.documents: dict[str, Any] = {}
        self.requests: list[httpx.Request] = []
        self._failures: dict[tuple[str, str], deque] = defaultdict(deque)
        self.transport = httpx.MockTransport(self._handle)

    @classmethod
    def from_fixtures(cls, root: Path, **kwargs) -> "FakeGenesys":
        conversations = [FakeConversation.load(folder) for folder in sorted(root.iterdir())
                         if folder.is_dir() and (folder / "details.json").exists()]
        catalog = json.loads((root / "catalog.json").read_text())
        return cls(conversations=conversations, catalog=catalog, **kwargs)

    # Programación de fallos y consulta de llamadas ---------------------------------------------------------------------

    def fail(self, method: str, target: str, *responses) -> None:
        self._failures[(method, target)].extend(responses)

    @property
    def calls(self) -> list[tuple[str, str]]:
        return [(r.method, r.url.path) for r in self.requests]

    def signed_url(self, key: str) -> str:
        return f"https://{self.bucket_host}/{key}?X-Amz-Signature=firma-{key}&X-Amz-Expires=300"

    # Transporte --------------------------------------------------------------------------------------------------------

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        for target in (str(request.url), request.url.path):
            queue = self._failures.get((request.method, target))
            if queue:
                return _programmed(queue.popleft())
        if request.url.host == self.bucket_host:
            key = request.url.path.lstrip("/")
            return self._json(self.documents[key]) if key in self.documents else self._json({}, 404)
        if request.url.path != "/oauth/token" and not self._authorized(request):
            return self._json({"message": "Token no válido"}, 401)
        for method, pattern, handler in _ROUTES:
            match = pattern.match(request.url.path)
            if method == request.method and match:
                return getattr(self, handler)(request, **match.groupdict())
        return self._json({"message": f"Ruta no simulada: {request.method} {request.url.path}"}, 404)

    def _authorized(self, request: httpx.Request) -> bool:
        return request.headers.get("authorization", "") in {f"Bearer {t}" for t in self.issued_tokens}

    @staticmethod
    def _json(body: Any, status: int = 200) -> httpx.Response:
        return httpx.Response(status, json=body)

    # Rutas -------------------------------------------------------------------------------------------------------------

    def _token(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("authorization") != f"Basic {self._credentials}":
            return self._json({"error": "invalid_client"}, 401)
        if parse_qs(request.content.decode()).get("grant_type") != ["client_credentials"]:
            return self._json({"error": "unsupported_grant_type"}, 400)
        token = f"token-falso-{next(self._tokens)}"
        self.issued_tokens.append(token)
        return self._json({"access_token": token, "token_type": "bearer", "expires_in": self._token_ttl})

    def _organization(self, request: httpx.Request) -> httpx.Response:
        return self._json(self.catalog["organization"])

    def _details_query(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        start, end = (_parse_time(part) for part in body["interval"].split("/"))
        if end - start > MAX_INTERVAL:
            return self._json({"message": "You must specify a search interval as part of your query that does not "
                                          "exceed 7 days", "code": "bad.request"}, 400)
        found = sorted((c.details for c in self.conversations.values()
                        if start <= _parse_time(c.details["conversationStart"]) < end),
                       key=lambda d: d["conversationStart"])
        paging = body.get("paging", {})
        size, number = paging.get("pageSize", 25), paging.get("pageNumber", 1)
        page = found[(number - 1) * size:number * size]
        return self._json({"conversations": page, "totalHits": len(found)} if page else {"totalHits": len(found)})

    def _conversation(self, cid: str) -> FakeConversation | None:
        return self.conversations.get(cid)

    def _details(self, request: httpx.Request, cid: str) -> httpx.Response:
        conversation = self._conversation(cid)
        return self._json(conversation.details) if conversation else self._json({}, 404)

    def _sta(self, request: httpx.Request, cid: str) -> httpx.Response:
        conversation = self._conversation(cid)
        return self._json(conversation.sta) if conversation else self._json({}, 404)

    def _transcript_url(self, request: httpx.Request, cid: str, comm: str) -> httpx.Response:
        conversation = self._conversation(cid)
        document = conversation.transcripts.get(comm) if conversation else None
        if document is None:
            return self._json({"message": "TranscriptResponse could not be found", "code": "resource.not.found"}, 404)
        key = f"{cid}/{comm}"
        self.documents[key] = document
        return self._json({"url": self.signed_url(key)})

    def _messages(self, request: httpx.Request, cid: str) -> httpx.Response:
        conversation = self._conversation(cid)
        return self._json(conversation.messages) if conversation and conversation.messages else self._json({}, 404)

    def _messages_bulk(self, request: httpx.Request, cid: str) -> httpx.Response:
        conversation = self._conversation(cid)
        if not conversation or conversation.messages_bulk is None:
            return self._json({}, 404)
        wanted = set(json.loads(request.content))
        return self._json({"entities": [m for m in conversation.messages_bulk if m["id"] in wanted]})

    def _named(self, kind: str, entity_id: str) -> httpx.Response:
        name = self.catalog.get(kind, {}).get(entity_id)
        return self._json({"id": entity_id, "name": name}) if name else self._json({}, 404)

    def _queue(self, request, id):  # noqa: A002
        return self._named("queues", id)

    def _user(self, request, id):  # noqa: A002
        return self._named("users", id)

    def _wrapup(self, request, id):  # noqa: A002
        return self._named("wrapups", id)

    def _division(self, request, id):  # noqa: A002
        return self._named("divisions", id)


def _programmed(response) -> httpx.Response:
    if isinstance(response, Exception):
        raise response
    if isinstance(response, int):
        return httpx.Response(response, json={"message": f"Fallo programado {response}"})
    status, headers, *body = response
    return httpx.Response(status, headers=headers, json=body[0] if body else {"message": f"Fallo programado {status}"})
