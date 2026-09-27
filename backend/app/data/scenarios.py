"""Guiones de diálogo por main topic.

Cada escenario define el motivo y la gestión que alimentan el summary y los turnos centrales.
Placeholders: {importe} {comercio} {fecha} {last4} {tel4} {iban} {producto}.
Cada outcome aporta el cierre del agente, la reacción del cliente y la frase de resultado del summary,
que debe empezar por el marcador de RESULT_MARKERS.
"""

C, A = "cliente", "agente"

SCENARIOS = {
    "cargo_no_reconocido": [
        {
            "motivo": "no reconoce un cargo de {importe} en {comercio} con su tarjeta terminada en {last4}",
            "gestion": "El agente revisa el movimiento del {fecha} y lo marca como posible fraude.",
            "turns": [
                (C, "Hola, me ha aparecido un cargo de {importe} en {comercio} que no reconozco."),
                (A, "Entiendo su preocupación. Veo el movimiento del {fecha} con la tarjeta terminada en {last4}. ¿Ha podido usarla otra persona de su entorno?"),
                (C, "No, nadie más la usa y la tengo aquí conmigo."),
                (A, "De acuerdo, voy a marcar el movimiento como posible fraude y abrir una reclamación."),
            ],
        },
        {
            "motivo": "detecta cargos recurrentes de {importe} de {comercio} que no reconoce",
            "gestion": "El agente identifica los cobros periódicos y propone bloquear el comercio y tramitar la devolución.",
            "turns": [
                (C, "Buenas, llevo tres meses viendo un cargo de {importe} de {comercio} y yo no me he suscrito a nada."),
                (A, "Vamos a revisarlo. Efectivamente aparecen cargos recurrentes de {comercio}. ¿Recuerda haber hecho alguna prueba gratuita?"),
                (C, "Que yo sepa no, no reconozco ese servicio."),
                (A, "Puedo bloquear los cargos futuros de ese comercio y tramitar la devolución de los últimos."),
            ],
        },
        {
            "motivo": "recibe un aviso de un cargo de {importe} en el extranjero que no reconoce",
            "gestion": "El agente confirma que la operación en {comercio} no encaja con sus hábitos de compra y la trata como fraude.",
            "turns": [
                (C, "Me ha llegado un SMS de una compra de {importe} en el extranjero y estoy en casa, no reconozco esa operación."),
                (A, "Veo una operación en {comercio} el {fecha}. No coincide con sus hábitos de compra, parece un fraude con la tarjeta."),
                (C, "Qué susto, ¿me van a devolver el dinero?"),
                (A, "Abrimos una disputa con la marca de la tarjeta; el plazo habitual de resolución es de hasta 45 días."),
            ],
        },
    ],
    "acceso_banca_digital": [
        {
            "motivo": "no puede acceder a la app porque su usuario está bloqueado",
            "gestion": "El agente comprueba que el bloqueo se debe a intentos fallidos de contraseña e inicia el proceso de nueva clave.",
            "turns": [
                (C, "No puedo entrar en la app, me dice que tengo el usuario bloqueado."),
                (A, "Veo que se ha bloqueado tras varios intentos fallidos de contraseña."),
                (C, "Es que no me acordaba y probé varias veces."),
                (A, "Le envío un SMS para que genere una nueva clave de acceso."),
            ],
        },
        {
            "motivo": "no recibe el SMS de confirmación en la banca online",
            "gestion": "El agente detecta que el teléfono asociado está desactualizado y explica cómo cambiarlo de forma segura.",
            "turns": [
                (C, "Estoy intentando hacer una operación en la banca online y no me llega el SMS de confirmación."),
                (A, "Compruebo el teléfono asociado: termina en {tel4}. ¿Es correcto?"),
                (C, "No, ese número es antiguo, cambié de teléfono."),
                (A, "Para actualizarlo por seguridad necesito que lo confirme en un cajero o en una oficina."),
            ],
        },
        {
            "motivo": "ha cambiado de móvil y necesita activar la app en el nuevo dispositivo",
            "gestion": "El agente guía el alta del nuevo dispositivo con la clave enviada por SMS.",
            "turns": [
                (C, "Me he cambiado de móvil y no sé cómo activar la app en el nuevo."),
                (A, "Tiene que descargarla, entrar con su usuario y validar el dispositivo con la clave que le enviamos por SMS."),
                (C, "Vale, ya me ha llegado el código."),
                (A, "Perfecto, introdúzcalo y el nuevo dispositivo quedará vinculado."),
            ],
        },
    ],
    "bloqueo_tarjeta": [
        {
            "motivo": "le han robado la cartera y necesita bloquear sus tarjetas",
            "gestion": "El agente identifica la tarjeta terminada en {last4} y procede a su bloqueo definitivo.",
            "turns": [
                (C, "Me acaban de robar la cartera y necesito bloquear la tarjeta."),
                (A, "Lo siento mucho. ¿Es la tarjeta de débito terminada en {last4}?"),
                (C, "Sí, esa misma, y también tenía la de crédito."),
                (A, "Procedo al bloqueo definitivo de ambas tarjetas; ninguna podrá volver a usarse."),
            ],
        },
        {
            "motivo": "ha perdido la tarjeta y solicita un bloqueo temporal",
            "gestion": "El agente aplica un bloqueo temporal a la tarjeta terminada en {last4} y explica cómo reactivarla desde la app.",
            "turns": [
                (C, "No encuentro la tarjeta, creo que la he perdido en el centro comercial."),
                (A, "Puedo aplicar un bloqueo temporal por si aparece, o bloquearla definitivamente."),
                (C, "Mejor temporal, a lo mejor está en el coche."),
                (A, "Hecho, la tarjeta terminada en {last4} queda bloqueada temporalmente; puede desbloquearla desde la app."),
            ],
        },
        {
            "motivo": "tiene la tarjeta bloqueada tras introducir mal el PIN",
            "gestion": "El agente le indica cómo consultar el PIN en la app y revisa la reactivación de la tarjeta terminada en {last4}.",
            "turns": [
                (C, "Tengo la tarjeta bloqueada, me equivoqué tres veces con el PIN en el cajero."),
                (A, "Por su seguridad no le voy a pedir el PIN; puede consultarlo en la app, en el apartado de tarjetas."),
                (C, "Vale, ¿y me la pueden desbloquear?"),
                (A, "Sí, puedo reactivar la tarjeta terminada en {last4} ahora mismo."),
            ],
        },
    ],
    "transferencias_bizum": [
        {
            "motivo": "una transferencia de {importe} no ha llegado a su destinatario",
            "gestion": "El agente comprueba que la transferencia se emitió correctamente a la cuenta de destino.",
            "turns": [
                (C, "Hice una transferencia de {importe} el {fecha} y el destinatario dice que no le ha llegado."),
                (A, "Veo la transferencia a la cuenta {iban}; está emitida correctamente."),
                (C, "Pues no le ha llegado nada."),
                (A, "Las transferencias ordinarias pueden tardar hasta un día hábil; si no llega, podemos pedir un seguimiento."),
            ],
        },
        {
            "motivo": "envió un bizum de {importe} a un número equivocado",
            "gestion": "El agente explica que el bizum no se puede anular y solicita la devolución al receptor.",
            "turns": [
                (C, "He enviado un bizum de {importe} a un número equivocado, ¿lo puedo recuperar?"),
                (A, "Un bizum es inmediato y no se puede anular, pero podemos solicitar la devolución al receptor."),
                (C, "Vaya, ¿y si no lo devuelve?"),
                (A, "Dependería de la voluntad del receptor; hacemos la solicitud formal ahora."),
            ],
        },
        {
            "motivo": "tiene retenida una transferencia de {importe} por un control de seguridad",
            "gestion": "El agente explica la retención preventiva y valida la operación con preguntas de seguridad.",
            "turns": [
                (C, "Me han retenido una transferencia de {importe} y no entiendo por qué."),
                (A, "Está en revisión por nuestro control de seguridad al ser un importe superior al habitual."),
                (C, "Es para pagar la reserva de un piso, es urgente."),
                (A, "Puedo confirmar la operación con usted ahora mismo tras unas preguntas de seguridad."),
            ],
        },
    ],
    "tarjeta_denegada": [
        {
            "motivo": "le han indicado que su tarjeta está denegada al pagar {importe} en {comercio}",
            "gestion": "El agente detecta que se ha alcanzado el límite diario de la tarjeta y ofrece ampliarlo.",
            "turns": [
                (C, "Estaba pagando en {comercio} y me han dicho que la tarjeta está denegada."),
                (A, "Veo que la operación de {importe} se rechazó porque ha alcanzado el límite diario de la tarjeta."),
                (C, "No sabía que tenía un límite tan bajo."),
                (A, "Puedo ampliarle el límite de forma temporal o permanente."),
            ],
        },
        {
            "motivo": "un pago online de {importe} en {comercio} le aparece rechazado",
            "gestion": "El agente comprueba que faltó la confirmación de seguridad en la app y revisa las notificaciones.",
            "turns": [
                (C, "Intento comprar en {comercio} y el pago de {importe} me sale rechazado."),
                (A, "La compra requiere confirmación en la app y no se completó a tiempo."),
                (C, "No me llegó ninguna notificación."),
                (A, "Revisemos que las notificaciones de la app estén activas; luego puede reintentar la compra."),
            ],
        },
    ],
    "consulta_saldo_movimientos": [
        {
            "motivo": "quiere conocer el saldo de su cuenta y sus últimos movimientos",
            "gestion": "El agente le informa del saldo disponible y detalla los movimientos recientes.",
            "turns": [
                (C, "Quería saber el saldo de mi cuenta y los últimos movimientos."),
                (A, "El saldo disponible es de {importe}. Los últimos movimientos son un recibo de luz y una compra en {comercio}."),
                (C, "Vale, ¿y el recibo de luz de cuánto era?"),
                (A, "De 64,30 euros, cargado el {fecha}."),
            ],
        },
        {
            "motivo": "necesita un certificado de titularidad y un extracto trimestral",
            "gestion": "El agente explica dónde descargar los documentos y ofrece enviarlos por correo.",
            "turns": [
                (C, "Necesito un certificado de titularidad y un extracto del último trimestre para un trámite."),
                (A, "Puede descargar ambos desde la banca online, en el apartado de documentos."),
                (C, "No lo encuentro, ¿me los pueden enviar?"),
                (A, "Se los envío a su correo electrónico registrado."),
            ],
        },
    ],
    "comisiones": [
        {
            "motivo": "reclama una comisión de mantenimiento de {importe}",
            "gestion": "El agente explica que la exención depende de la nómina domiciliada y estudia una devolución excepcional.",
            "turns": [
                (C, "Me han cobrado una comisión de mantenimiento de {importe} y pensaba que mi cuenta era sin comisiones."),
                (A, "La cuenta está exenta si tiene la nómina domiciliada, y este mes no se recibió la nómina."),
                (C, "Es que me cambié de empresa y cobro más tarde."),
                (A, "Entiendo. Puedo solicitar la devolución de la comisión de forma excepcional."),
            ],
        },
        {
            "motivo": "reclama una comisión por descubierto de {importe}",
            "gestion": "El agente revisa las condiciones de la cuenta y valora anular la comisión por su antigüedad como cliente.",
            "turns": [
                (C, "Tengo una comisión por descubierto de {importe} y solo estuve en negativo un día."),
                (A, "La comisión se aplica aunque el descubierto dure un solo día, según las condiciones de la cuenta."),
                (C, "Me parece abusivo, llevo veinte años en este banco."),
                (A, "Lo entiendo; voy a revisar si podemos anularla por su antigüedad."),
            ],
        },
        {
            "motivo": "reclama una comisión de {importe} por sacar dinero en un cajero de otra entidad",
            "gestion": "El agente explica el coste de los cajeros ajenos y le indica cómo localizar los gratuitos.",
            "turns": [
                (C, "He sacado dinero en un cajero de otra entidad y me han cobrado una comisión de {importe}."),
                (A, "Las retiradas en cajeros de otras entidades tienen coste; en los nuestros es gratuito."),
                (C, "Nadie me lo explicó cuando abrí la cuenta."),
                (A, "Le indico en la app dónde encontrar los cajeros gratuitos más cercanos."),
            ],
        },
    ],
    "recibos_domiciliaciones": [
        {
            "motivo": "quiere devolver un recibo duplicado de {importe} de {comercio}",
            "gestion": "El agente localiza los dos cargos del {fecha} y tramita la devolución del duplicado.",
            "turns": [
                (C, "Quiero devolver un recibo de {importe} de {comercio} que me han cobrado dos veces."),
                (A, "Veo los dos cargos del {fecha}; puede devolver el duplicado sin coste."),
                (C, "Sí, por favor, solo uno de ellos."),
                (A, "Tramito la devolución del recibo duplicado."),
            ],
        },
        {
            "motivo": "quiere domiciliar su nómina y sus recibos en la cuenta",
            "gestion": "El agente le facilita el IBAN y explica el traspaso de domiciliaciones desde la app.",
            "turns": [
                (C, "Quiero domiciliar la nómina y los recibos de casa en esta cuenta."),
                (A, "Puede hacerlo facilitando el IBAN a su empresa; le leo su cuenta: {iban}."),
                (C, "Perfecto, ¿y los recibos?"),
                (A, "Desde la app puede traer las domiciliaciones de otro banco en un solo paso."),
            ],
        },
    ],
    "prestamos_hipotecas": [
        {
            "motivo": "quiere amortizar {importe} de su hipoteca",
            "gestion": "El agente compara reducir cuota o plazo y le informa de la comisión aplicable.",
            "turns": [
                (C, "Quiero amortizar parte de la hipoteca, unos {importe}."),
                (A, "Puede reducir cuota o plazo; con esa cantidad su cuota bajaría de forma apreciable."),
                (C, "Prefiero reducir plazo, ¿hay comisión?"),
                (A, "Hay una comisión del 0,25 % durante los primeros años, que le detallo por escrito."),
            ],
        },
        {
            "motivo": "no puede pagar la cuota de su préstamo tras quedarse sin trabajo",
            "gestion": "El agente plantea una carencia o una reestructuración y prepara una simulación.",
            "turns": [
                (C, "Este mes no voy a poder pagar la cuota del préstamo, me he quedado sin trabajo."),
                (A, "Lamento la situación. Podemos estudiar un periodo de carencia o una reestructuración."),
                (C, "¿Eso me costaría más al final?"),
                (A, "Aumentaría ligeramente los intereses totales; le preparo una simulación."),
            ],
        },
    ],
    "contratacion_producto": [
        {
            "motivo": "quiere contratar {producto}",
            "gestion": "El agente explica las condiciones del producto y envía la oferta a la app.",
            "turns": [
                (C, "Me gustaría contratar {producto}, ¿qué condiciones tienen?"),
                (A, "Con su perfil puede contratar {producto} con condiciones preferentes; le detallo costes y requisitos."),
                (C, "¿Y lo puedo hacer ahora por teléfono?"),
                (A, "Sí, le envío la oferta a la app para que la firme."),
            ],
        },
        {
            "motivo": "compara ofertas antes de contratar {producto}",
            "gestion": "El agente ofrece una bonificación ligada a la nómina y envía la propuesta por escrito.",
            "turns": [
                (C, "He visto una oferta de otro banco y quería saber si me mejoran las condiciones para contratar {producto}."),
                (A, "Reviso su perfil. Puedo ofrecerle una bonificación si domicilia la nómina."),
                (C, "Me interesa, pero quiero verlo por escrito."),
                (A, "Le envío la propuesta detallada por correo."),
            ],
        },
    ],
    "baja_cancelacion": [
        {
            "motivo": "quiere cerrar la cuenta y cancelar sus tarjetas para irse a otro banco",
            "gestion": "El agente pregunta el motivo de la baja e intenta la retención con una cuenta sin comisiones.",
            "turns": [
                (C, "Quiero cerrar la cuenta y cancelar todas mis tarjetas, me voy a otro banco."),
                (A, "Siento escuchar eso. ¿Puedo preguntarle el motivo?"),
                (C, "Las comisiones, en el otro banco no pago nada."),
                (A, "Antes de tramitar la baja puedo revisar si le aplicamos una cuenta sin comisiones."),
            ],
        },
        {
            "motivo": "quiere cancelar su tarjeta de crédito por la cuota anual",
            "gestion": "El agente ofrece eliminar la cuota anual y, ante la negativa, tramita la baja de la tarjeta terminada en {last4}.",
            "turns": [
                (C, "Quiero cancelar la tarjeta de crédito, casi no la uso y pago cuota anual."),
                (A, "Puedo darla de baja ahora; antes le informo de que la cuota anual se elimina si la usa una vez al mes."),
                (C, "No, prefiero cancelarla."),
                (A, "De acuerdo, procedo a la baja de la tarjeta terminada en {last4}."),
            ],
        },
    ],
    "cajeros": [
        {
            "motivo": "el cajero no le entregó {importe} pero el importe aparece cargado",
            "gestion": "El agente localiza la retirada del {fecha} y abre una incidencia de arqueo del cajero.",
            "turns": [
                (C, "Saqué {importe} en un cajero y no me dio el dinero, pero me lo han cargado."),
                (A, "Veo la retirada del {fecha}; abro una incidencia para revisar el arqueo del cajero."),
                (C, "¿Cuánto tarda?"),
                (A, "El arqueo suele revisarse en cinco días hábiles."),
            ],
        },
        {
            "motivo": "el cajero le ha retenido la tarjeta",
            "gestion": "El agente anula la tarjeta terminada en {last4}, solicita una nueva y explica la retirada sin tarjeta.",
            "turns": [
                (C, "El cajero se ha tragado mi tarjeta y es la única que tengo."),
                (A, "Por seguridad la tarjeta terminada en {last4} queda anulada y le pedimos una nueva."),
                (C, "¿Y mientras tanto cómo saco dinero?"),
                (A, "Puede retirar efectivo sin tarjeta desde la app en cualquiera de nuestros cajeros."),
            ],
        },
        {
            "motivo": "un ingreso de {importe} en el cajero no aparece en su cuenta",
            "gestion": "El agente confirma la operación sin abonar y marca la revisión del cajero como urgente.",
            "turns": [
                (C, "Hice un ingreso de {importe} en efectivo en el cajero y no aparece en la cuenta."),
                (A, "Veo la operación registrada pero sin abonar; revisaremos el cajero."),
                (C, "Era el dinero del alquiler, lo necesito ya."),
                (A, "Lo marco como urgente."),
            ],
        },
    ],
    "datos_personales": [
        {
            "motivo": "se ha mudado y quiere cambiar su domicilio",
            "gestion": "El agente actualiza la dirección postal en su ficha.",
            "turns": [
                (C, "Me he mudado y quiero actualizar mis datos, el domicilio sobre todo."),
                (A, "Le cambio el domicilio ahora mismo; ¿me confirma la nueva dirección postal?"),
                (C, "Calle del Olmo 12, tercero B, en Valladolid."),
                (A, "Actualizado; las próximas cartas le llegarán allí."),
            ],
        },
        {
            "motivo": "recibe un aviso por tener el DNI caducado en su ficha",
            "gestion": "El agente explica cómo subir el DNI renovado y envía un enlace alternativo.",
            "turns": [
                (C, "Me ha llegado un aviso de que tengo el DNI caducado en el banco."),
                (A, "Así es; puede subir el documento renovado desde la app, en su perfil."),
                (C, "Lo intento pero la foto no se sube."),
                (A, "Le envío un enlace alternativo por correo electrónico."),
            ],
        },
    ],
    "alta_cliente": [
        {
            "motivo": "quiere abrir una cuenta y pregunta por los requisitos",
            "gestion": "El agente explica la apertura online con DNI y videoselfie y las condiciones sin comisiones.",
            "turns": [
                (C, "Quería abrir una cuenta con ustedes, ¿qué necesito?"),
                (A, "Puede hacerlo online en diez minutos con su DNI y un videoselfie."),
                (C, "¿Tiene comisiones?"),
                (A, "La cuenta online no tiene comisiones si recibe al menos un ingreso al mes."),
            ],
        },
        {
            "motivo": "tiene bloqueada la apertura de su cuenta online en la verificación",
            "gestion": "El agente comprueba que falta validar el documento de identidad y envía un enlace nuevo.",
            "turns": [
                (C, "Empecé el proceso online para hacerme cliente y se ha quedado a medias en la verificación."),
                (A, "Veo su solicitud de apertura pendiente de validar el documento de identidad."),
                (C, "Subí el DNI dos veces y me da error."),
                (A, "Le envío un enlace nuevo para repetir la verificación."),
            ],
        },
    ],
    "reclamacion_queja": [
        {
            "motivo": "quiere presentar una queja por la atención recibida en una oficina",
            "gestion": "El agente escucha lo ocurrido y registra la queja formal.",
            "turns": [
                (C, "Quiero poner una queja por el trato que recibí ayer en la oficina."),
                (A, "Lamento lo ocurrido. ¿Me puede contar qué pasó?"),
                (C, "Esperé una hora y al final me dijeron que volviera otro día."),
                (A, "Registro su queja y la trasladamos a la dirección de la oficina."),
            ],
        },
        {
            "motivo": "presenta una reclamación formal por las esperas para ser atendido",
            "gestion": "El agente registra la reclamación con número de seguimiento y anota la reiteración.",
            "turns": [
                (C, "Llevo tres días intentando hablar con alguien, quiero presentar una reclamación formal."),
                (A, "Siento mucho la espera. Puedo registrar la reclamación ahora y darle un número de seguimiento."),
                (C, "Sí, y quiero que conste que es la tercera vez."),
                (A, "Queda anotado en la reclamación."),
            ],
        },
    ],
}


def _o(agente, cliente, resultado):
    return {"agente": agente, "cliente": cliente, "resultado": resultado}


OUTCOMES = {
    "cargo_no_reconocido": {
        "resuelta": _o("Ya tiene la reclamación abierta y le abonaremos provisionalmente el importe en 48 horas.", "Perfecto, muchas gracias.",
                       "Queda resuelta con una reclamación abierta y el abono provisional de {importe} en 48 horas."),
        "no_resuelta": _o("Para abrir la reclamación necesito que presente una denuncia y la envíe desde la app.", "Pues vaya, tendré que ir a comisaría.",
                          "Queda pendiente de que aporte la denuncia para abrir la reclamación."),
        "escalada": _o("Voy a pasar su caso al departamento de fraude, que le contactará en 24 horas.", "Espero que lo solucionen pronto.",
                       "Se escala al departamento de fraude, que contactará en 24 horas."),
    },
    "acceso_banca_digital": {
        "resuelta": _o("Ya puede acceder con normalidad a la app.", "Sí, ya he entrado, gracias.",
                       "Queda resuelta y el acceso a la app vuelve a funcionar."),
        "no_resuelta": _o("Hay una incidencia general en la app; le recomiendo intentarlo más tarde.", "Siempre igual con la app, es la segunda vez esta semana.",
                          "Queda pendiente por una incidencia general en la app."),
        "escalada": _o("Paso la incidencia al soporte técnico de banca digital, que le llamará hoy.", "Vale, espero la llamada.",
                       "Se escala al soporte técnico de banca digital para revisar el acceso."),
    },
    "bloqueo_tarjeta": {
        "resuelta": _o("Todo listo, la tarjeta ya está protegida. Si necesita una nueva, le llegará en 5 días hábiles.", "Genial, gracias por la rapidez.",
                       "Queda resuelta con la tarjeta protegida y los siguientes pasos explicados."),
        "no_resuelta": _o("El sistema de tarjetas no responde ahora mismo; le recomiendo bloquearla desde la app o volver a llamar en una hora.", "¿Y si la usan mientras tanto? No me deja nada tranquilo.",
                          "Queda pendiente porque el sistema de tarjetas no responde y se recomienda el bloqueo desde la app."),
        "escalada": _o("Paso su caso a Fraude y seguridad para revisar si ha habido operaciones posteriores.", "De acuerdo, estaré pendiente.",
                       "Se escala a Fraude y seguridad para revisar posibles operaciones posteriores."),
    },
    "transferencias_bizum": {
        "resuelta": _o("La operación queda gestionada; recibirá una notificación en la app.", "Gracias, eso me tranquiliza.",
                       "Queda resuelta la gestión de la operación con aviso en la app."),
        "no_resuelta": _o("Necesitamos esperar la respuesta de la otra entidad, que puede tardar hasta 10 días.", "Es mucho tiempo para un dinero que necesito.",
                          "Queda pendiente de la respuesta de la otra entidad, con un plazo de hasta 10 días."),
        "escalada": _o("Abro una incidencia con el departamento de operaciones para que la revisen con prioridad.", "Vale, espero noticias.",
                       "Se escala al departamento de operaciones para su revisión prioritaria."),
    },
    "tarjeta_denegada": {
        "resuelta": _o("Ya puede volver a intentar el pago, debería funcionar.", "Acabo de probar y ha funcionado.",
                       "Queda resuelta y el pago con tarjeta vuelve a funcionar."),
        "no_resuelta": _o("No puedo modificar el límite por teléfono; tiene que solicitarlo desde la app.", "Qué complicado todo, necesitaba pagar ya.",
                          "Queda pendiente de que solicite el cambio de límite desde la app."),
        "escalada": _o("Traslado la incidencia al equipo de medios de pago para revisar la tarjeta.", "Vale, pero que sea rápido.",
                       "Se escala al equipo de medios de pago para revisar la tarjeta."),
    },
    "consulta_saldo_movimientos": {
        "resuelta": _o("Ya tiene toda la información que necesitaba.", "Sí, perfecto, gracias.",
                       "Queda resuelta con la información facilitada."),
        "no_resuelta": _o("El sistema de documentos no está disponible ahora; inténtelo mañana.", "Lo necesitaba hoy.",
                          "Queda pendiente porque el sistema de documentos no está disponible."),
        "escalada": _o("Solicito el documento al departamento de administración, que se lo enviará en 48 horas.", "De acuerdo.",
                       "Se escala a administración para el envío del documento en 48 horas."),
    },
    "comisiones": {
        "resuelta": _o("He tramitado la devolución de la comisión; la verá en su cuenta en 48 horas.", "Muchas gracias, así sí.",
                       "Queda resuelta con la devolución de la comisión en 48 horas."),
        "no_resuelta": _o("Lo siento, según las condiciones la comisión es correcta y no puedo devolverla.", "Pues me estoy planteando cambiar de banco.",
                          "Queda pendiente sin devolución porque la comisión se ajusta a las condiciones del contrato."),
        "escalada": _o("Voy a trasladar su reclamación al Servicio de Atención al Cliente para que la estudien.", "Espero una respuesta pronto.",
                       "Se escala la reclamación al Servicio de Atención al Cliente."),
    },
    "recibos_domiciliaciones": {
        "resuelta": _o("Todo queda gestionado, verá el cambio en unos días.", "Estupendo, gracias.",
                       "Queda resuelta la gestión y los cambios se verán en unos días."),
        "no_resuelta": _o("El recibo supera el plazo de devolución de ocho semanas, así que no puedo devolverlo.", "No me parece justo.",
                          "Queda pendiente porque se supera el plazo de devolución y debe reclamarse al emisor."),
        "escalada": _o("Envío la solicitud al departamento de domiciliaciones para que la revise.", "Vale, gracias.",
                       "Se escala al departamento de domiciliaciones para su revisión."),
    },
    "prestamos_hipotecas": {
        "resuelta": _o("Le envío la simulación y el documento para firmar desde la app.", "Muy bien, lo reviso esta tarde.",
                       "Queda resuelta con la simulación y la documentación enviadas a la app."),
        "no_resuelta": _o("Para esa operación necesita cita con su gestor en oficina.", "Otra vez a la oficina, no tengo tiempo para eso.",
                          "Queda pendiente de una cita con el gestor en oficina."),
        "escalada": _o("Traslado su solicitud al equipo de riesgos, que le contactará en tres días.", "De acuerdo, esperaré.",
                       "Se escala al equipo de riesgos, que contactará en tres días."),
    },
    "contratacion_producto": {
        "resuelta": _o("La contratación queda completada; recibirá la documentación en la app.", "Perfecto, gracias.",
                       "Queda resuelta con la contratación completada y la documentación en la app."),
        "no_resuelta": _o("Ahora mismo no cumple los requisitos de riesgo para esta contratación.", "Qué decepción, llevo años con ustedes.",
                          "Queda pendiente porque no cumple los requisitos de riesgo para la contratación."),
        "escalada": _o("Paso su solicitud a un gestor especializado, que le llamará mañana.", "De acuerdo.",
                       "Se escala a un gestor especializado para completar la contratación."),
    },
    "baja_cancelacion": {
        "resuelta": _o("La baja queda tramitada y recibirá la confirmación por correo.", "Gracias.",
                       "Queda resuelta con la baja tramitada y la confirmación por correo."),
        "no_resuelta": _o("Para cerrar la cuenta primero debe cancelar el préstamo asociado.", "Me están poniendo trabas para irme.",
                          "Queda pendiente porque hay productos asociados que impiden completar la baja."),
        "escalada": _o("Paso su solicitud al equipo de retención, que le llamará con una propuesta.", "Me da igual la propuesta, quiero irme.",
                       "Se escala al equipo de retención para gestionar la baja."),
    },
    "cajeros": {
        "resuelta": _o("La incidencia del cajero queda gestionada y le avisaremos por SMS.", "Gracias.",
                       "Queda resuelta la incidencia del cajero con aviso por SMS."),
        "no_resuelta": _o("Hasta que termine el arqueo no puedo hacer nada más.", "Cinco días sin mi dinero, es increíble.",
                          "Queda pendiente del resultado del arqueo del cajero."),
        "escalada": _o("Traslado el caso al departamento de cajeros como urgente.", "Por favor, que lo miren hoy.",
                       "Se escala al departamento de cajeros como urgente."),
    },
    "datos_personales": {
        "resuelta": _o("Sus datos quedan actualizados.", "Perfecto.",
                       "Queda resuelta con los datos personales actualizados."),
        "no_resuelta": _o("Para ese cambio necesitamos un documento acreditativo que no tenemos.", "Pues no sé de dónde lo voy a sacar.",
                          "Queda pendiente de recibir el documento acreditativo."),
        "escalada": _o("Envío la solicitud a administración para que la validen manualmente.", "Vale.",
                       "Se escala a administración para validar el cambio manualmente."),
    },
    "alta_cliente": {
        "resuelta": _o("Su cuenta ya está operativa; le damos la bienvenida a Banco Horizonte.", "Genial, gracias.",
                       "Queda resuelta con la cuenta abierta y operativa."),
        "no_resuelta": _o("La verificación sigue fallando; tendrá que acudir a una oficina con su DNI.", "Si es tan complicado igual me voy a otro banco.",
                          "Queda pendiente de completar la verificación en una oficina."),
        "escalada": _o("Paso su caso al equipo de alta de clientes para revisión manual.", "Vale, espero.",
                       "Se escala al equipo de alta de clientes para revisión manual."),
    },
    "reclamacion_queja": {
        "resuelta": _o("Le he dado el número de seguimiento y recibirá respuesta en 15 días.", "Gracias por escucharme.",
                       "Queda resuelta la tramitación con número de seguimiento y respuesta en 15 días."),
        "no_resuelta": _o("No puedo darle una solución inmediata a lo que me plantea.", "Pues iré al Banco de España.",
                          "Queda pendiente sin una solución inmediata."),
        "escalada": _o("Traslado su reclamación al Servicio de Atención al Cliente con prioridad alta.", "Espero que esta vez me hagan caso.",
                       "Se escala al Servicio de Atención al Cliente con prioridad alta."),
    },
}
