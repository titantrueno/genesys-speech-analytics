"""Conjunto de relevancia de FE003, redactado antes del diccionario de sinónimos (spec, «Riesgos y asunciones»).

- PARAPHRASE_PAIRS: frases sin ninguna palabra con contenido en común con los turnos de su main topic en el
  dataset, incluidos los valores que rellenan los guiones (comercios, productos…) (criterio 3). Deben encontrar su main topic con el diccionario y no sin él.
- LABELLED_QUERIES: consultas como las diría un cliente, etiquetadas con su main topic (criterio 8).
"""

PARAPHRASE_PAIRS = [
    ("me han cobrado algo que no he comprado", "cargo_no_reconocido"),
    ("abandono la entidad y traslado mis ahorros a la competencia", "baja_cancelacion"),
    ("la máquina no soltó los billetes", "cajeros"),
    ("he extraviado la visa, inutilízala", "bloqueo_tarjeta"),
    ("olvidé mis credenciales de la aplicación y no logro iniciar sesión", "acceso_banca_digital"),
    ("mandé pasta a un colega con el móvil y no la ha recibido", "transferencias_bizum"),
    ("el datáfono no aceptó mi visa en la tienda", "tarjeta_denegada"),
    ("la compañía de la luz me giró la factura repetida", "recibos_domiciliaciones"),
    ("necesito rebajar la mensualidad de la vivienda", "prestamos_hipotecas"),
]

LABELLED_QUERIES = [
    ("me han hecho un cargo raro en la tarjeta que yo no he hecho", "cargo_no_reconocido"),
    ("hay una compra en internet que no es mía", "cargo_no_reconocido"),
    ("no me deja entrar en la banca online", "acceso_banca_digital"),
    ("me he quedado sin acceso a la aplicación del móvil", "acceso_banca_digital"),
    ("me han robado el bolso con las tarjetas", "bloqueo_tarjeta"),
    ("quiero congelar la tarjeta porque no la encuentro", "bloqueo_tarjeta"),
    ("hice una transferencia a una cuenta equivocada", "transferencias_bizum"),
    ("el bizum que envié no le llega a mi hija", "transferencias_bizum"),
    ("no me dejan pagar con la tarjeta en las compras por internet", "tarjeta_denegada"),
    ("al pagar en el supermercado me dice operación denegada", "tarjeta_denegada"),
    ("necesito un certificado de mis movimientos del último año", "consulta_saldo_movimientos"),
    ("cuánto dinero tengo disponible en la cuenta", "consulta_saldo_movimientos"),
    ("me están cobrando comisiones que no entiendo", "comisiones"),
    ("por qué me cobran mantenimiento si tengo la nómina domiciliada", "comisiones"),
    ("me han devuelto un recibo del gimnasio", "recibos_domiciliaciones"),
    ("quiero domiciliar el recibo de la luz", "recibos_domiciliaciones"),
    ("quiero amortizar parte de la hipoteca", "prestamos_hipotecas"),
    ("me interesa pedir un préstamo para comprar un coche", "prestamos_hipotecas"),
    ("quiero contratar un fondo de inversión", "contratacion_producto"),
    ("quiero darme de baja del banco", "baja_cancelacion"),
    ("el cajero se quedó con mi tarjeta", "cajeros"),
    ("cambié de casa y quiero actualizar mi dirección", "datos_personales"),
    ("quiero abrir una cuenta porque soy nuevo cliente", "alta_cliente"),
    ("llevo semanas esperando y nadie me atiende, quiero poner una queja", "reclamacion_queja"),
]
