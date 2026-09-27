from dataclasses import dataclass, field

BANK_NAME = "Banco Horizonte"

QUEUES = [
    "Particulares",
    "Tarjetas",
    "Fraude y seguridad",
    "Banca digital",
    "Préstamos e hipotecas",
    "Inversión y ahorro",
    "Empresas",
]

AGENTS_BY_QUEUE = {
    "Particulares": ["Lucía Márquez", "Andrés Toledo", "Carmen Rivas", "Javier Ortega"],
    "Tarjetas": ["Elena Campos", "Raúl Serrano", "Marta Iglesias"],
    "Fraude y seguridad": ["Sergio Molina", "Paula Crespo", "Diego Navarro"],
    "Banca digital": ["Irene Vidal", "Óscar Peña", "Nuria Castro"],
    "Préstamos e hipotecas": ["Alberto Lozano", "Silvia Moreno", "Hugo Prieto"],
    "Inversión y ahorro": ["Beatriz Santos", "Tomás Herrera"],
    "Empresas": ["Clara Domínguez", "Víctor Gallego", "Rocío Medina"],
}

COMPLIANCE_CHECKS = {
    "saludo": "Saludo e identificación del agente",
    "verificacion_identidad": "Verificación de identidad del cliente",
    "proteccion_datos": "Aviso de protección de datos",
    "no_solicitar_pin": "No solicitar PIN ni claves completas",
    "bloqueo_preventivo": "Ofrecimiento de bloqueo preventivo en casos de fraude",
    "despedida": "Despedida con resumen de la gestión",
}

RESULT_MARKERS = {
    "resuelta": "Queda resuelta",
    "no_resuelta": "Queda pendiente",
    "escalada": "Se escala",
}

PRODUCTS_BY_QUEUE = {
    "Particulares": ["una tarjeta de crédito", "un seguro de hogar", "una cuenta de ahorro"],
    "Tarjetas": ["una tarjeta de crédito", "una tarjeta de débito adicional"],
    "Préstamos e hipotecas": ["un préstamo personal", "un préstamo para el coche"],
    "Inversión y ahorro": ["un depósito a plazo fijo", "un plan de pensiones", "un fondo de inversión"],
}


@dataclass(frozen=True)
class MainTopic:
    code: str
    name: str
    weight: float
    queues: dict[str, float]
    chat_share: float
    resolution_weights: tuple[float, float, float]
    base_sentiment: float
    keywords: list[str]
    secondary: list[str]
    amount_range: tuple[float, float, float] = (10, 500, 0.01)
    merchants: list[str] = field(default_factory=list)


ONLINE_MERCHANTS = ["TiendaYa Online", "StreamPlus", "Viajes Brisa", "GameZone Store", "ModaExpress", "AppMarket Global"]
UTILITY_MERCHANTS = ["Eléctrica del Norte", "Gimnasio FitPlus", "Seguros Alba", "Telefonía Nova", "Aguas del Valle"]
RETAIL_MERCHANTS = ["Supermercados Día a Día", "Farmacia Central", "Gasolinera Ruta 7", "Librería Papiro", "ElectroHogar"]

MAIN_TOPICS = {
    t.code: t
    for t in [
        MainTopic("cargo_no_reconocido", "Cargo no reconocido", 14,
                  {"Fraude y seguridad": 0.75, "Tarjetas": 0.2, "Particulares": 0.05},
                  0.35, (0.55, 0.2, 0.25), -0.5,
                  ["no reconozco", "no reconoce", "fraude"],
                  ["fraude", "compras online", "devolución"], (9.99, 450, 0.01), ONLINE_MERCHANTS),
        MainTopic("acceso_banca_digital", "Acceso a banca digital", 13,
                  {"Banca digital": 0.8, "Particulares": 0.1, "Empresas": 0.1},
                  0.6, (0.65, 0.2, 0.15), -0.3,
                  ["app", "banca online", "usuario bloqueado", "sms"],
                  ["app móvil", "claves de acceso", "sms"]),
        MainTopic("bloqueo_tarjeta", "Bloqueo de tarjeta", 10,
                  {"Tarjetas": 0.6, "Fraude y seguridad": 0.3, "Particulares": 0.1},
                  0.25, (0.8, 0.1, 0.1), -0.4,
                  ["bloquear", "bloqueo", "bloqueada"],
                  ["robo", "tarjeta nueva", "seguridad"]),
        MainTopic("transferencias_bizum", "Transferencias y Bizum", 10,
                  {"Particulares": 0.6, "Banca digital": 0.2, "Empresas": 0.2},
                  0.45, (0.55, 0.25, 0.2), -0.3,
                  ["transferencia", "bizum"],
                  ["plazos", "seguridad", "cuenta de destino"], (50, 3000, 0.01)),
        MainTopic("tarjeta_denegada", "Pago o tarjeta denegada", 8,
                  {"Tarjetas": 0.8, "Particulares": 0.2},
                  0.35, (0.7, 0.2, 0.1), -0.3,
                  ["denegada", "rechazado", "límite"],
                  ["límites de tarjeta", "compras online", "notificaciones"], (15, 900, 0.01),
                  ONLINE_MERCHANTS + RETAIL_MERCHANTS),
        MainTopic("consulta_saldo_movimientos", "Consulta de saldo y movimientos", 7,
                  {"Particulares": 0.6, "Banca digital": 0.25, "Inversión y ahorro": 0.15},
                  0.55, (0.9, 0.07, 0.03), 0.1,
                  ["saldo", "movimientos", "extracto", "certificado"],
                  ["documentación", "movimientos"], (200, 8000, 0.01), RETAIL_MERCHANTS),
        MainTopic("comisiones", "Reclamación de comisiones", 7,
                  {"Particulares": 0.7, "Empresas": 0.2, "Inversión y ahorro": 0.1},
                  0.35, (0.45, 0.35, 0.2), -0.5,
                  ["comisión", "comisiones"],
                  ["nómina", "condiciones de la cuenta", "descubierto"], (5, 60, 0.01)),
        MainTopic("recibos_domiciliaciones", "Recibos y domiciliaciones", 6,
                  {"Particulares": 0.8, "Empresas": 0.2},
                  0.4, (0.7, 0.2, 0.1), -0.2,
                  ["recibo", "domiciliar", "domiciliaciones"],
                  ["devolución", "nómina", "suministros"], (20, 120, 0.01), UTILITY_MERCHANTS),
        MainTopic("prestamos_hipotecas", "Préstamos e hipotecas", 5,
                  {"Préstamos e hipotecas": 0.85, "Particulares": 0.15},
                  0.3, (0.5, 0.25, 0.25), -0.1,
                  ["préstamo", "hipoteca", "cuota", "amortizar"],
                  ["simulación", "intereses", "carencia"], (3000, 30000, 1000)),
        MainTopic("contratacion_producto", "Contratación de producto", 5,
                  {"Particulares": 0.4, "Inversión y ahorro": 0.3, "Préstamos e hipotecas": 0.2, "Tarjetas": 0.1},
                  0.5, (0.6, 0.2, 0.2), 0.2,
                  ["contratar", "contratación"],
                  ["condiciones", "bonificación", "firma digital"]),
        MainTopic("baja_cancelacion", "Baja o cancelación", 4,
                  {"Particulares": 0.8, "Tarjetas": 0.2},
                  0.35, (0.5, 0.3, 0.2), -0.3,
                  ["cancelar", "baja", "cerrar la cuenta"],
                  ["retención", "competencia", "comisiones"]),
        MainTopic("cajeros", "Incidencia en cajero", 4,
                  {"Particulares": 0.6, "Tarjetas": 0.4},
                  0.2, (0.5, 0.25, 0.25), -0.5,
                  ["cajero"],
                  ["efectivo", "arqueo"], (20, 600, 10)),
        MainTopic("datos_personales", "Cambio de datos personales", 3,
                  {"Particulares": 0.8, "Banca digital": 0.2},
                  0.45, (0.8, 0.12, 0.08), 0.0,
                  ["domicilio", "dirección postal", "caducado"],
                  ["documentación", "verificación"]),
        MainTopic("alta_cliente", "Alta de cliente", 2.5,
                  {"Particulares": 0.7, "Banca digital": 0.3},
                  0.6, (0.65, 0.2, 0.15), 0.1,
                  ["abrir una cuenta", "apertura", "hacerme cliente"],
                  ["verificación", "documentación"]),
        MainTopic("reclamacion_queja", "Reclamación o queja general", 2.5,
                  {"Particulares": 0.8, "Empresas": 0.2},
                  0.3, (0.3, 0.3, 0.4), -0.7,
                  ["queja", "reclamación"],
                  ["tiempo de espera", "atención en oficina"]),
    ]
}

FRAUD_SPIKE_DAYS = range(18, 25)
FRAUD_TOPICS = {"cargo_no_reconocido"}
