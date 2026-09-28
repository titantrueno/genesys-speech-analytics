"""Identificadores de entidad con formato PREFIJO-UUID (ver vault/ingenieria/registro-de-identificadores.md)."""
import random
import re
import uuid

CONVERSATION = "1CO"
CUSTOMER = "1CU"
USER = "1US"
AGENT = "1AG"
QUEUE = "1QU"
SAVED_QUERY = "1QY"
FLOW = "1FL"
NODE = "1ND"
RUN = "1RN"
TOPIC = "1TP"
SECONDARY_TOPIC = "1TS"
CHECK = "1CK"
CONNECTOR = "1CN"
AUDIT = "1AU"

PREFIXES = {
    CONVERSATION: "Conversación",
    CUSTOMER: "Cliente",
    USER: "Usuario",
    AGENT: "Agente",
    QUEUE: "Cola",
    "1RO": "Rol",
    TOPIC: "Main topic",
    SECONDARY_TOPIC: "Tema secundario",
    CHECK: "Check de cumplimiento",
    SAVED_QUERY: "Consulta guardada",
    FLOW: "Flujo de insights",
    NODE: "Nodo de flujo",
    RUN: "Ejecución de flujo",
    CONNECTOR: "Conector de datos",
    AUDIT: "Entrada de auditoría",
}

_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "speech-analytics.bancohorizonte.demo")
_ID_RE = re.compile(r"^(1[A-Z]{2})-[0-9A-F]{8}-[0-9A-F]{4}-[45][0-9A-F]{3}-[89AB][0-9A-F]{3}-[0-9A-F]{12}$")


def _check_prefix(prefix: str) -> None:
    if prefix not in PREFIXES:
        raise ValueError(f"Prefijo no registrado: {prefix!r}")


def _format(prefix: str, value: uuid.UUID) -> str:
    return f"{prefix}-{str(value).upper()}"


def new_id(prefix: str, rng: random.Random) -> str:
    _check_prefix(prefix)
    return _format(prefix, uuid.UUID(int=rng.getrandbits(128), version=4))


def stable_id(prefix: str, name: str) -> str:
    _check_prefix(prefix)
    return _format(prefix, uuid.uuid5(_NAMESPACE, f"{prefix}:{name}"))


def normalize(value: str) -> str:
    return value.strip().upper()


def is_valid(value: str, prefix: str | None = None) -> bool:
    match = _ID_RE.match(value)
    if not match or match.group(1) not in PREFIXES:
        return False
    return prefix is None or match.group(1) == prefix
