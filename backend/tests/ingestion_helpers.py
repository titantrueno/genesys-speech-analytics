"""Ayudas de los tests del servicio de ingesta (FE011): Genesys falso con las fixtures, clones y flujos de prueba."""
import copy
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg

from app import ids
from ingestion import db
from ingestion.genesys.client import GenesysClient
from ingestion.genesys.fake import FakeGenesys
from ingestion.pipeline.raw import RawConversation

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "genesys"
CATALOG = json.loads((FIXTURES / "catalog.json").read_text())
CLIENT_ID, SECRET = "cliente-de-prueba", "secreto-de-prueba-123"
# 12 de octubre de 2026 en Madrid, el día de las fixtures.
DAY_START = datetime(2026, 10, 11, 22, 0, tzinfo=timezone.utc)
DAY_END = DAY_START + timedelta(days=1)


def fixture(short_id: str) -> RawConversation:
    return RawConversation.from_folder(next(FIXTURES.glob(f"*-{short_id}")))


def fixtures() -> list[RawConversation]:
    return [RawConversation.from_folder(p) for p in sorted(FIXTURES.iterdir()) if p.is_dir()]


def make_fake(conversations: list[RawConversation] | None = None) -> FakeGenesys:
    return FakeGenesys(client_id=CLIENT_ID, client_secret=SECRET,
                       conversations=fixtures() if conversations is None else conversations, catalog=CATALOG)


def client_factory(fake: FakeGenesys, secret: str = SECRET):
    return lambda: GenesysClient(CLIENT_ID, secret, "eu-west-1", transport=fake.transport, sleep=lambda _: None)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def clone(raw: RawConversation, index: int, start: datetime) -> RawConversation:
    """Copia de una conversación con otro identificador y otro inicio (solo cambian el inicio y el fin de la
    conversación: basta para la búsqueda por intervalo y para medir el rendimiento)."""
    new_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"clon-{raw.id}-{index}"))
    copied = RawConversation(**json.loads(json.dumps(raw.__dict__).replace(raw.id, new_id)))
    original_start = datetime.fromisoformat(raw.details["conversationStart"].replace("Z", "+00:00"))
    original_end = datetime.fromisoformat(raw.details["conversationEnd"].replace("Z", "+00:00"))
    copied.details["conversationStart"] = _iso(start)
    copied.details["conversationEnd"] = _iso(start + (original_end - original_start))
    return copied


def spread(raws: list[RawConversation], count: int, start: datetime, days: int) -> list[RawConversation]:
    step = timedelta(days=days) / count
    return [clone(raws[i % len(raws)], i, start + step * i) for i in range(count)]


def in_progress(raw: RawConversation) -> RawConversation:
    copied = copy.deepcopy(raw)
    copied.details.pop("conversationEnd")
    return copied


def with_media(raw: RawConversation, media: str) -> RawConversation:
    copied = copy.deepcopy(raw)
    for participant in copied.details["participants"]:
        for session in participant["sessions"]:
            session["mediaType"] = media
    return copied


def create_flow(database_url: str, name: str = "Descarga de prueba") -> str:
    """Flujo de descarga mínimo para colgar ejecuciones (el CRUD llega en T5)."""
    flow_id = ids.new_id(ids.FLOW, __import__("random").SystemRandom())
    with psycopg.connect(database_url) as conn:
        db.migrate(conn)
        conn.execute(
            "INSERT INTO download_flow (id, name, interval, channels, schedule, timezone, author_id, author_name) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (flow_id, name, json.dumps({"type": "relativo", "unit": "dias", "amount": 1}), ["voz", "chat"],
             json.dumps({"type": "desactivada"}), "Europe/Madrid", "1US-PRUEBA", "Admin de prueba"))
    return flow_id


def table_counts(database_url: str) -> dict[str, int]:
    tables = ["conversation", "segment", "turn", "topic_hit", "analysis", "raw_payload", "queue", "agent", "flow",
              "wrapup", "division"]
    with psycopg.connect(database_url) as conn:
        return {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}
