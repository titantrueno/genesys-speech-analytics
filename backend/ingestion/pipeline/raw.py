"""Respuestas de Genesys de una conversación, tal como llegan (FE011). Son la entrada de la normalización, lo que sirve
el Genesys falso y lo que se guarda en `raw_payload` para poder reanalizar.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RawConversation:
    details: dict  # detalle de analítica (`/analytics/conversations/{id}/details` o una fila de la consulta)
    sta: dict = field(default_factory=dict)  # resumen de Speech & Text Analytics
    # Documento de transcripción de cada comunicación del cliente (con una o varias transcripciones dentro, algunas
    # vacías); `None` = la URL de transcripción responde `404`.
    transcripts: dict[str, dict | None] = field(default_factory=dict)
    messages: dict | None = None  # conversación de mensajería (solo chat)
    messages_bulk: list[dict] | None = None  # mensajes con texto y estado; `None` si la API de mensajes no respondió

    @property
    def id(self) -> str:
        return self.details["conversationId"]

    @classmethod
    def from_folder(cls, folder: Path) -> "RawConversation":
        def read(name: str):
            path = folder / name
            return json.loads(path.read_text()) if path.exists() else None

        return cls(details=read("details.json"), sta=read("sta.json") or {}, transcripts=read("transcripts.json") or {},
                   messages=read("messages.json"), messages_bulk=read("messages_bulk.json"))

    def payloads(self) -> dict[str, object]:
        """Respuestas originales por tipo, para `raw_payload`."""
        found = {"details": self.details, "sta": self.sta, "transcripts": self.transcripts}
        if self.messages is not None:
            found["messages"] = self.messages
        if self.messages_bulk is not None:
            found["messages_bulk"] = self.messages_bulk
        return found
