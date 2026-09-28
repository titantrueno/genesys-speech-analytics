"""Diccionario de sinónimos y expresiones del dominio bancario para expandir las consultas (FE003).

Cada grupo reúne expresiones equivalentes. Si la consulta contiene una, se añaden las demás con menos peso
que los términos originales. Las expresiones con `*` (prefijo) solo disparan el grupo: no se añaden.
La coincidencia no distingue mayúsculas ni tildes y respeta los límites de palabra.
"""
import re

from app.query.fields import normalize_text

SYNONYMS: list[list[str]] = [
    # Cargos y fraude
    ["cargo", "cargos", "cobr*", "adeud*"],
    ["no reconozco", "no reconoce", "fraude", "no he comprado", "no he hecho", "no es mía", "no es mío",
     "yo no he sido", "no autoric*"],
    ["online", "internet", "por internet"],
    # Tarjetas
    ["tarjeta", "visa", "mastercard", "plástico"],
    ["bloquear", "bloqueo", "inutiliz*", "congel*", "desactiv*", "anular la tarjeta"],
    ["perdido", "robado", "extravi*", "no la encuentro", "rob*", "hurt*"],
    ["denegada", "rechazado", "rechaz*", "deneg*", "no acept*", "no pasa la tarjeta", "no funciona la tarjeta"],
    ["comercio", "tienda", "datáfono", "tpv", "establecimiento"],
    # Banca digital
    ["app", "aplicación", "banca online", "banca digital", "web del banco"],
    ["contraseña", "clave", "credencial*", "password"],
    ["acceder", "entrar", "iniciar sesión", "logu*", "conectar*"],
    ["no me acordaba", "olvid*"],
    # Transferencias y Bizum
    ["transferencia", "bizum", "mand*", "enviar dinero", "pasar dinero"],
    ["dinero", "pasta", "plata", "pelas"],
    ["destinatario", "beneficiario", "colega", "amig*", "familiar"],
    ["no le ha llegado", "llegado", "no la ha recibido", "no lo ha recibido", "no le llega"],
    # Cajeros
    ["cajero", "máquina", "dispensador", "cajero automático"],
    ["efectivo", "billetes", "metálico"],
    ["no me dio", "no solt*", "no entreg*", "no me ha dado"],
    # Recibos
    ["recibo", "factura", "gir*", "adeudo"],
    ["duplicado", "repetid*", "dos veces", "doble cobro"],
    ["empresa", "compañía", "eléctrica", "suministro", "luz", "agua", "gas"],
    # Préstamos e hipotecas
    ["cuota", "mensualidad", "letra"],
    ["hipoteca", "préstamo", "vivienda", "piso", "financiación", "crédito personal"],
    ["reducir", "rebajar", "bajar", "disminuir", "pagar menos"],
    # Comisiones
    ["comisión", "comisiones", "recargo", "penalizaci*", "gastos de mantenimiento", "mantenimiento"],
    # Saldo y movimientos
    ["saldo", "cuánto dinero tengo", "dinero disponible", "balance"],
    ["movimientos", "extracto", "historial", "operaciones"],
    # Baja
    ["baja", "cerrar la cuenta", "cancelar", "otro banco", "irme", "competencia", "abandon*", "marcho",
     "cambiarme de banco", "darme de baja"],
    # Datos personales y alta
    ["domicilio", "dirección", "mud*", "cambié de casa", "nueva dirección"],
    ["alta", "abrir una cuenta", "apertura", "hacerme cliente", "nuevo cliente"],
    # Quejas y contratación
    ["queja", "reclamación", "quejarme", "protestar", "nadie me atiende", "hoja de reclamaciones"],
    ["contratar", "contratación", "me interesa", "fondo", "inversión", "seguro", "depósito"],
]


def _pattern(expression: str) -> re.Pattern:
    return re.compile(r"\b" + re.escape(normalize_text(expression)).replace(r"\*", r"\w*") + r"\b")


_COMPILED = [[(e, _pattern(e)) for e in group] for group in SYNONYMS]


def expand(text: str, groups: list[list[str]] | None = None) -> list[str]:
    """Expresiones añadidas a la consulta, en el orden del diccionario y sin repetir ni incluir las presentes."""
    compiled = _COMPILED if groups is None else [[(e, _pattern(e)) for e in group] for group in groups]
    normalized = normalize_text(text)
    added: list[str] = []
    for group in compiled:
        present = [bool(p.search(normalized)) for _, p in group]
        if not any(present):
            continue
        for (expression, _), found in zip(group, present):
            if not found and "*" not in expression and expression not in added:
                added.append(expression)
    return added
