"""Intérprete mock por reglas; la normalización conserva la longitud, así las posiciones recuperan las palabras originales."""
import re
from datetime import timedelta

from app.data.catalog import AGENT_IDS, COMPLIANCE_CHECKS, MAIN_TOPICS, QUEUE_IDS
from app.data.store import reference_date
from app.query.fields import normalize_text

TOPIC_PATTERNS = {
    "bloqueo_tarjeta": r"bloqueos? de (la )?tarjetas?|tarjetas? bloquead\w*|robos? de (la )?tarjetas?",
    "acceso_banca_digital": r"banca (digital|online)|acceso a la (app|banca)|usuarios? bloquead\w*|claves? de acceso",
    "tarjeta_denegada": r"tarjetas? denegad\w*|pagos? (denegad|rechazad)\w*|compras? rechazad\w*",
    "cargo_no_reconocido": r"(cargos?|compras?) no reconocid\w*|fraudes?",
    "transferencias_bizum": r"transferencias?|bizums?",
    "consulta_saldo_movimientos": r"saldos?|movimientos|extractos?|certificados?",
    "comisiones": r"comision\w*",
    "recibos_domiciliaciones": r"recibos?|domiciliacion\w*",
    "prestamos_hipotecas": r"prestamos?|hipotecas?",
    "contratacion_producto": r"contratacion\w*|contratar",
    "baja_cancelacion": r"\bbajas?\b|cancelacion\w*|cancelar",
    "cajeros": r"cajeros?",
    "datos_personales": r"datos personales|cambios? de (domicilio|direccion)",
    "alta_cliente": r"altas? de clientes?|aperturas? de cuentas?|nuevos clientes",
    "reclamacion_queja": r"quejas?|reclamacion\w*",
}
CHECK_PATTERNS = {
    "verificacion_identidad": r"sin verificar (la )?identidad|no (se )?verific\w* (la )?identidad",
    "saludo": r"sin saludo|sin saludar|no saluda\w*",
    "proteccion_datos": r"sin (el )?aviso de proteccion de datos",
    "no_solicitar_pin": r"(el agente )?(pidio|pide|solicito|solicita) (el )?pin",
    "bloqueo_preventivo": r"sin (ofrecer )?(el )?bloqueo preventivo",
    "despedida": r"sin despedida|sin despedirse",
}
STOPWORDS = {
    "de", "del", "la", "las", "el", "los", "lo", "y", "o", "e", "con", "en", "que", "a", "al", "por", "para",
    "un", "una", "unos", "unas", "se", "su", "sus", "donde", "conversaciones", "conversacion", "casos", "caso",
    "cliente", "clientes", "todas", "todos", "dame", "muestra", "muestrame", "quiero", "ver", "busca", "buscar",
    "hay", "son", "esta", "este", "estas", "estos",
}
MAX_TEXT = 500
MAX_DAYS = 3650
MAX_DURATION_S = 86400


class _Matcher:
    def __init__(self, text: str):
        self.masked = normalize_text(text)

    def take(self, pattern: str):
        found = list(re.finditer(pattern, self.masked))
        for match in found:
            start, end = match.span()
            self.masked = self.masked[:start] + " " * (end - start) + self.masked[end:]
        return found


def _cond(field: str, operator: str, value=None, **extra) -> dict:
    return {"field": field, "operator": operator, "value": value, **extra}


def _one_or_many(field: str, values: list) -> dict:
    return _cond(field, "is", values[0]) if len(values) == 1 else _cond(field, "in", values)


def interpret(text: str) -> tuple[dict, list[str]]:
    original = text.strip()
    m = _Matcher(original)
    conditions: list[dict] = []
    period: dict = {}
    ref = reference_date()
    yesterday = ref - timedelta(days=1)

    quote = r"(?:(?P<who>clientes?|agentes?) que )?(?:(?:dicen|digan|dice|diga|mencionen|menciona|mencione) )?[\"«“](?P<q>[^\"»”]+)[\"»”]"
    for match in m.take(quote):
        speaker = None
        if match.group("who"):
            speaker = "cliente" if match.group("who").startswith("cliente") else "agente"
        span = match.span("q")
        literal = original[span[0]:span[1]].strip()
        if literal:
            conditions.append(_cond("transcript", "contains", literal, **({"speaker": speaker} if speaker else {})))

    for match in m.take(r"(?:en )?(?:los )?ultimos? (\d+) dias"):
        days = min(max(int(match.group(1)), 1), MAX_DAYS)
        period = {"from": (ref - timedelta(days=days)).isoformat(), "to": yesterday.isoformat()}
    if m.take(r"esta semana"):
        period = {"from": (yesterday - timedelta(days=yesterday.weekday())).isoformat(), "to": yesterday.isoformat()}
    if m.take(r"(?:en )?(?:la )?ultima semana"):
        period = {"from": (ref - timedelta(days=7)).isoformat(), "to": yesterday.isoformat()}
    if m.take(r"(?:en )?(?:el )?ultimo mes"):
        period = {"from": (ref - timedelta(days=30)).isoformat(), "to": yesterday.isoformat()}
    if m.take(r"\bayer\b"):
        period = {"from": yesterday.isoformat(), "to": yesterday.isoformat()}

    for match in m.take(r"(?:que )?(?:duren|duran|de) (mas|menos) de (\d+) (minutos?|segundos?)"):
        seconds = min(int(match.group(2)) * (60 if match.group(3).startswith("minuto") else 1), MAX_DURATION_S)
        conditions.append(_cond("duration", "gt" if match.group(1) == "mas" else "lt", seconds))

    if m.take(r"(?:que )?incumpl\w*(?: (?:algun|alguno de los|los))?(?: checks?)?|incumplimientos?"):
        conditions.append({"op": "or", "conditions": [_cond(f"check:{code}", "fails") for code in COMPLIANCE_CHECKS]})
    for code, pattern in CHECK_PATTERNS.items():
        if m.take(pattern):
            conditions.append(_cond(f"check:{code}", "fails"))

    if m.take(r"recontact\w*|volvieron a (llamar|contactar)|contactos? repetidos?"):
        conditions.append(_cond("repeat_contact", "is", True))

    for match in m.take(r"(?:con )?riesgo (?:de (?:abandono|baja) )?(alto|medio|bajo)|(alto|medio|bajo) riesgo"):
        conditions.append(_cond("churn_risk", "is", match.group(1) or match.group(2)))

    if m.take(r"insatisfech\w*|csat bajo"):
        conditions.append(_cond("csat", "lt", 3))
    if m.take(r"\bsatisfech\w*|csat alto"):
        conditions.append(_cond("csat", "gte", 4))
    if m.take(r"(?:con )?esfuerzo alto"):
        conditions.append(_cond("effort", "gte", 4))
    if m.take(r"(?:con )?esfuerzo bajo"):
        conditions.append(_cond("effort", "lte", 2))

    resolutions = []
    if m.take(r"no resuelt\w*|sin resolver|sin resolucion|pendientes?"):
        resolutions.append("no_resuelta")
    if m.take(r"escalad\w*"):
        resolutions.append("escalada")
    if m.take(r"\bresuelt\w*"):
        resolutions.append("resuelta")
    if resolutions:
        conditions.append(_one_or_many("resolution", resolutions))

    if m.take(r"muy negativ\w*"):
        conditions.append(_cond("sentiment", "lt", -0.6))
    if m.take(r"negativ\w*"):
        conditions.append(_cond("sentiment", "lt", -0.3))
    if m.take(r"positiv\w*"):
        conditions.append(_cond("sentiment", "gt", 0.3))
    if m.take(r"neutr\w*"):
        conditions.append(_cond("sentiment", "between", [-0.3, 0.3]))

    chat = bool(m.take(r"\bchats?\b"))
    voice = bool(m.take(r"\b(llamadas?|voz|telefonicas?)\b"))
    if chat != voice:
        conditions.append(_cond("channel", "is", "chat" if chat else "voz"))

    queues = []
    for name, queue_id in QUEUE_IDS.items():
        key = normalize_text(name)
        short = key.split(" ")[0]
        if m.take(rf"(?:la )?cola (?:de |del )?(?:{re.escape(key)}|{re.escape(short)})\b"):
            queues.append(queue_id)
    if queues:
        conditions.append(_one_or_many("queue", queues))

    agents = [agent_id for name, agent_id in AGENT_IDS.items() if m.take(rf"\b{re.escape(normalize_text(name))}\b")]
    if agents:
        conditions.append(_one_or_many("agent", agents))

    topics = [code for code in MAIN_TOPICS if code in TOPIC_PATTERNS and m.take(TOPIC_PATTERNS[code])]
    if topics:
        conditions.append(_one_or_many("main_topic", topics))

    unrecognized = [original[w.start():w.end()] for w in re.finditer(r"\w+", m.masked)
                    if w.group() not in STOPWORDS and not w.group().isdigit()]
    return {**period, "root": {"op": "and", "conditions": conditions}}, unrecognized


def validate_text(text: str) -> str | None:
    if not text or not text.strip():
        return "Escribe una frase"
    if len(text) > MAX_TEXT:
        return f"La frase no puede superar {MAX_TEXT} caracteres"
    return None

