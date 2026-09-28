import random
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app import ids
from app.data.catalog import (
    AGENT_IDS,
    AGENTS_BY_QUEUE,
    BANK_NAME,
    BANK_TIMEZONE,
    FRAUD_SPIKE_DAYS,
    FRAUD_TOPICS,
    MAIN_TOPICS,
    PRODUCTS_BY_QUEUE,
    QUEUE_IDS,
    REPEATED_COMPLAINT_TOPIC,
    MainTopic,
)
from app.data.scenarios import OUTCOMES, SCENARIOS
from app.models import Analysis, Conversation, Entity, Turn

DAYS_BACK = 90
CUSTOMER_POOL = 650
RESOLUTIONS = ("resuelta", "no_resuelta", "escalada")
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]
FIRST_NAMES = [("Ana", "f"), ("María", "f"), ("Laura", "f"), ("Isabel", "f"), ("Pilar", "f"), ("Sara", "f"),
               ("Cristina", "f"), ("Teresa", "f"), ("Jorge", "m"), ("Manuel", "m"), ("Pablo", "m"),
               ("Francisco", "m"), ("Luis", "m"), ("Miguel", "m"), ("Adrián", "m"), ("Rubén", "m")]
LAST_NAMES = ["García", "Fernández", "López", "Martín", "Sánchez", "Gómez", "Ruiz", "Díaz", "Álvarez",
              "Romero", "Torres", "Vázquez", "Ramos", "Gil", "Blanco", "Suárez"]
DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
FRAUD_OFFER_TOPICS = {"cargo_no_reconocido"}
RESOLUTION_DELTA = {"resuelta": 0.7, "no_resuelta": -0.2, "escalada": -0.1}
CSAT_BASE = {"resuelta": 4.3, "no_resuelta": 2.3, "escalada": 2.8}
EFFORT_BASE = {"resuelta": 1.8, "no_resuelta": 3.8, "escalada": 3.3}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _weighted(rng: random.Random, options: dict):
    return rng.choices(list(options), weights=list(options.values()))[0]


def _fake_dni(rng: random.Random) -> str:
    number = rng.randint(10_000_000, 79_999_999)
    return f"{number}{DNI_LETTERS[number % 23]}"


def _fake_iban(rng: random.Random) -> str:
    bban = "9999" + "".join(str(rng.randint(0, 9)) for _ in range(16))
    check = 98 - int(bban + "142800") % 97
    compact = f"ES{check:02d}{bban}"
    return " ".join(compact[i:i + 4] for i in range(0, len(compact), 4))


def _format_amount(value: float) -> str:
    integer, decimals = f"{value:.2f}".split(".")
    integer = f"{int(integer):,}".replace(",", ".")
    return f"{integer} €" if decimals == "00" else f"{integer},{decimals} €"


def _amount(rng: random.Random, topic: MainTopic) -> float:
    low, high, step = topic.amount_range
    return round(round(rng.uniform(low, high) / step) * step, 2)


def _spanish_date(day: date) -> str:
    return f"{day.day} de {MONTHS[day.month - 1]}"


def _build_customers(rng: random.Random, id_rng: random.Random) -> list[dict]:
    customers = []
    for _ in range(CUSTOMER_POOL):
        first, gender = rng.choice(FIRST_NAMES)
        customers.append({
            "id": ids.new_id(ids.CUSTOMER, id_rng),
            "name": f"{first} {rng.choice(LAST_NAMES)}",
            "gender": gender,
            "dni": _fake_dni(rng),
            "iban": _fake_iban(rng),
        })
    return customers


def _pick_start(rng: random.Random, reference_date: date) -> datetime:
    while True:
        day = reference_date - timedelta(days=rng.randint(1, DAYS_BACK))
        if day.weekday() < 5 or rng.random() < 0.4:
            break
    hour = rng.choices(range(8, 22), weights=[3, 6, 8, 8, 7, 5, 4, 5, 6, 6, 5, 4, 3, 2])[0]
    return datetime.combine(day, time(hour, rng.randint(0, 59), rng.randint(0, 59)), tzinfo=ZoneInfo(BANK_TIMEZONE))


def _pick_topic(rng: random.Random, started_at: datetime, reference_date: date) -> MainTopic:
    days_ago = (reference_date - started_at.date()).days
    weights = {}
    for code, topic in MAIN_TOPICS.items():
        spike = 3 if code in FRAUD_TOPICS and days_ago in FRAUD_SPIKE_DAYS else 1
        weights[code] = topic.weight * spike
    return MAIN_TOPICS[_weighted(rng, weights)]


class _Script:
    def __init__(self, values: dict):
        self.values = values
        self.turns: list[tuple[str, str, str]] = []

    def add(self, speaker: str, text: str, role: str = "core") -> None:
        self.turns.append((speaker, text.format(**self.values), role))


def _build_conversation(rng, customer, topic, started_at, channel, resolution) -> Conversation:
    queue = _weighted(rng, topic.queues)
    agent = rng.choice(AGENTS_BY_QUEUE[queue])
    agent_first = agent.split()[0]
    scenario = rng.choice(SCENARIOS[topic.code])
    outcome = OUTCOMES[topic.code][resolution]
    event_day = started_at.date() - timedelta(days=rng.randint(0, 6))
    products = PRODUCTS_BY_QUEUE.get(queue, PRODUCTS_BY_QUEUE["Particulares"])
    values = {
        "importe": _format_amount(_amount(rng, topic)),
        "comercio": rng.choice(topic.merchants) if topic.merchants else "",
        "fecha": _spanish_date(event_day),
        "last4": f"{rng.randint(0, 9999):04d}",
        "tel4": f"{rng.randint(100, 999)}",
        "iban": _fake_iban(rng) if topic.code == "transferencias_bizum" else customer["iban"],
        "producto": rng.choice(products),
        "dni": customer["dni"],
    }
    s = _Script(values)

    compliance = {
        "saludo": rng.random() < 0.95,
        "verificacion_identidad": rng.random() < 0.88,
        "proteccion_datos": rng.random() < 0.85,
        "no_solicitar_pin": rng.random() >= 0.04,
        "bloqueo_preventivo": (rng.random() < 0.8) if topic.code in FRAUD_OFFER_TOPICS else None,
        "despedida": rng.random() < 0.9,
    }
    greeting = (f"Buenos días, le atiende {agent_first} de {BANK_NAME}. ¿En qué puedo ayudarle?"
                if compliance["saludo"] else "Dígame.")
    core = scenario["turns"]

    if channel == "chat":
        s.add("bot", f"Hola, soy el asistente virtual de {BANK_NAME}. ¿En qué puedo ayudarle?", "open")
        s.add(*core[0])
        s.add("bot", "Le paso con un gestor para que revise su caso.", "open")
        s.add("sistema", f"{agent_first} se ha unido a la conversación.", "open")
        chat_greeting = f"Hola, soy {agent_first} de {BANK_NAME}. Ya he leído su consulta, lo reviso ahora mismo."
        s.add("agente", chat_greeting if compliance["saludo"] else "Hola.", "open")
    else:
        s.add("agente", greeting, "open")
        s.add(*core[0])

    if compliance["verificacion_identidad"]:
        s.add("agente", "Antes de continuar, para verificar su identidad, ¿me indica su DNI?", "check")
        s.add("cliente", "Sí, es {dni}.", "check")
        s.add("agente", "Gracias, identidad verificada.", "check")
    if compliance["proteccion_datos"]:
        s.add("agente", "Le informo de que sus datos se tratarán conforme a nuestra política de protección de datos.", "check")

    for i, (speaker, text) in enumerate(core[1:], start=1):
        s.add(speaker, text)
        if i == 2 and not compliance["no_solicitar_pin"]:
            s.add("agente", "Para agilizar, ¿me puede decir el PIN de la tarjeta?", "violation")
            s.add("cliente", "¿El PIN? Pensaba que eso no se pedía nunca.", "violation")

    if compliance["bloqueo_preventivo"]:
        s.add("agente", "Le recomiendo bloquear preventivamente la tarjeta terminada en {last4}. ¿Quiere que lo haga ahora?", "check")
        s.add("cliente", "Sí, por favor, bloquéela.", "check")

    repeated_complaint = resolution != "resuelta" and rng.random() < 0.5
    if repeated_complaint:
        s.add("cliente", "Llevo días con este problema y nadie me da una solución clara.", "complaint")

    s.add("agente", outcome["agente"], "outcome")
    s.add("cliente", outcome["cliente"], "outcome")

    if compliance["despedida"]:
        s.add("agente", f"Resumiendo, hemos revisado su consulta sobre {topic.name.lower()} y le he indicado los siguientes pasos. "
                        "¿Puedo ayudarle en algo más?", "close")
        s.add("cliente", "No, eso es todo.", "close")
        s.add("agente", f"Gracias por confiar en {BANK_NAME}. Que tenga un buen día.", "close")
    else:
        s.add("agente", "Hasta luego.", "close")
    if channel == "chat":
        s.add("sistema", "La conversación ha finalizado.", "close")

    turns = _timed_turns(rng, s.turns, channel, topic, resolution)
    customer_sentiments = [t.sentiment for t in turns if t.speaker == "cliente"]
    mean = sum(customer_sentiments) / len(customer_sentiments)
    overall = round(_clamp(0.4 * mean + 0.6 * customer_sentiments[-1], -1, 1), 2)
    csat = round(_clamp(CSAT_BASE[resolution] + 1.2 * overall + rng.uniform(-0.3, 0.3), 1, 5), 1)
    effort = round(_clamp(EFFORT_BASE[resolution] + 0.08 * (len(turns) - 12) + rng.uniform(-0.3, 0.3), 1, 5), 1)
    if topic.code == "baja_cancelacion" or (overall < -0.4 and resolution != "resuelta"):
        churn = "alto"
    elif overall < 0 or resolution != "resuelta":
        churn = "medio"
    else:
        churn = "bajo"

    subject = "La clienta" if customer["gender"] == "f" else "El cliente"
    verb = "escribe" if channel == "chat" else "llama"
    summary_parts = [
        f"{subject} {verb} porque {scenario['motivo'].format(**values)}.",
        scenario["gestion"].format(**values),
        outcome["resultado"].format(**values),
    ]
    if overall < -0.4:
        summary_parts.append("Durante la conversación muestra un tono muy negativo.")

    secondary = rng.sample(topic.secondary, k=min(len(topic.secondary), rng.randint(1, 2)))
    if repeated_complaint:
        secondary.append(REPEATED_COMPLAINT_TOPIC)

    text = " ".join(t.text.lower() for t in turns)
    templates = " ".join(t for _, t in core) + scenario["motivo"] + scenario["gestion"]
    entities = [Entity(type=etype, value=values[key]) for etype, key in
                (("importe", "importe"), ("comercio", "comercio"), ("fecha", "fecha"), ("producto", "producto"))
                if "{" + key + "}" in templates and values[key]]
    keywords = [k for k in topic.keywords if k in text]

    return Conversation(
        id="",
        channel=channel,
        started_at=started_at,
        duration_s=turns[-1].offset_s + rng.randint(3, 12),
        queue_id=QUEUE_IDS[queue],
        queue=queue,
        agent_id=AGENT_IDS[agent],
        agent=agent,
        customer_id=customer["id"],
        turns=turns,
        analysis=Analysis(
            summary=" ".join(summary_parts),
            main_topic=topic.code,
            secondary_topics=secondary,
            sentiment=overall,
            sentiment_timeline=[t.sentiment for t in turns],
            resolution=resolution,
            csat=csat,
            effort=effort,
            churn_risk=churn,
            compliance=compliance,
            entities=entities,
            keywords=keywords,
        ),
    )


def _timed_turns(rng, script, channel, topic, resolution) -> list[Turn]:
    customer_total = sum(1 for speaker, _, _ in script if speaker == "cliente")
    start = _clamp(topic.base_sentiment + rng.uniform(-0.15, 0.15), -1, 1)
    end = _clamp(start + RESOLUTION_DELTA[resolution] + rng.uniform(-0.15, 0.15), -1, 1)
    turns, offset, customer_seen = [], 0, 0
    for speaker, text, role in script:
        if speaker == "cliente":
            progress = customer_seen / max(customer_total - 1, 1)
            sentiment = start + (end - start) * progress
            if role in ("violation", "complaint"):
                sentiment -= 0.3
            customer_seen += 1
        elif speaker == "agente":
            sentiment = -0.1 if role == "violation" else rng.uniform(0.15, 0.5)
        elif speaker == "bot":
            sentiment = 0.1
        else:
            sentiment = 0.0
        turns.append(Turn(speaker=speaker, text=text, offset_s=offset, sentiment=round(_clamp(sentiment, -1, 1), 2)))
        words = len(text.split())
        if channel == "voz":
            offset += max(2, round(words / 2.5)) + rng.randint(1, 3)
        elif speaker == "bot" or speaker == "sistema":
            offset += rng.randint(1, 3)
        else:
            offset += rng.randint(15, 60) if speaker == "cliente" else rng.randint(10, 45)
    return turns


def generate_dataset(seed: int, reference_date: date, size: int = 1000) -> list[Conversation]:
    rng = random.Random(seed)
    id_rng = random.Random(f"ids:{seed}")
    customers = _build_customers(rng, id_rng)
    pending_followups: list[tuple[dict, MainTopic, datetime]] = []
    conversations: list[Conversation] = []

    while len(conversations) < size:
        if pending_followups and rng.random() < 0.5:
            customer, topic, started_at = pending_followups.pop(0)
        else:
            customer = rng.choice(customers)
            started_at = _pick_start(rng, reference_date)
            topic = _pick_topic(rng, started_at, reference_date)
        channel = "chat" if rng.random() < topic.chat_share else "voz"
        resolution = rng.choices(RESOLUTIONS, weights=topic.resolution_weights)[0]
        conversation = _build_conversation(rng, customer, topic, started_at, channel, resolution)
        conversations.append(conversation)

        if resolution != "resuelta" and rng.random() < 0.35:
            follow_up = started_at + timedelta(days=rng.randint(1, 6), hours=rng.randint(-3, 3))
            if follow_up.date() < reference_date:
                pending_followups.append((customer, topic, follow_up))

    conversations.sort(key=lambda c: c.started_at)
    for conversation in conversations:
        conversation.id = ids.new_id(ids.CONVERSATION, id_rng)
    return conversations
