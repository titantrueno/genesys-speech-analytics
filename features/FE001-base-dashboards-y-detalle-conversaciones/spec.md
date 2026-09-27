# FE001 — Base, dashboards y detalle de conversaciones

> Estado: **pendiente de aprobación**. Fase `/spec`. Siguiente paso tras aprobar: `/plan`.

## Objetivo

Construir la base de una plataforma web de speech & text analytics para la atención al cliente de un banco (front, API mock y acceso por rol) y permitir analizar conversaciones transcritas desde dashboards de KPIs, con drill-down a un listado filtrado y a un detalle de conversación mostrado como un chat.

## Decisiones transversales (aplican a FE001–FE006)

| Tema | Decisión |
|---|---|
| Dominio | Atención al cliente de un banco. Todas las conversaciones, colas, main topics y ejemplos son del ámbito bancario. |
| Front | SPA con Vite + React + TypeScript + Tailwind CSS, React Router, TanStack Query y Recharts. Carpeta `frontend/`. |
| Back | Python 3.11+ con FastAPI y Pydantic. Carpeta `backend/`. Solo datos mock en memoria; no hay base de datos. |
| Datos mock | Conjunto generado de forma determinista con semilla fija: 1.000 conversaciones (voz transcrita y chat) de los últimos 90 días respecto a la fecha de arranque, en español, con nombres, DNI, IBAN y números de tarjeta ficticios. |
| Contrato | API REST JSON bajo `/api`, con documentación OpenAPI en `/docs`. El front lee la URL base de `VITE_API_URL`. |
| Acceso | Login mock con token firmado simple. Roles base: `admin`, `supervisor`, `analista` y `viewer`. El backend aplica permisos y el front oculta lo no permitido. |
| Idioma de la UI | Español. Diseño para escritorio (≥ 1280 px) que no se rompe en tablet. |
| Tests | Backend con `pytest`; front con Vitest + Testing Library. |
| Fuente de datos | Solo transcripciones de llamadas y chats; nunca audio. |

## Modelo de datos mock

**Conversación:** `id`, `channel` (`voz` \| `chat`), `started_at`, `duration_s`, `queue`, `agent`, `customer_id` (seudónimo), `turns[]` y `analysis`.

**Turno:** `speaker` (`cliente` \| `agente` \| `bot` \| `sistema`), `text`, `offset_s` y `sentiment` (-1..1).

**Análisis:** `summary`, `main_topic`, temas secundarios, sentimiento global y su evolución, resolución (`resuelta` \| `no_resuelta` \| `escalada`), CSAT predicho (1–5), esfuerzo del cliente predicho (1–5), riesgo de abandono (`bajo` \| `medio` \| `alto`), checks de cumplimiento, entidades (importe, producto, fecha, comercio) y palabras clave.

**Colas:** Particulares, Tarjetas, Fraude y seguridad, Banca digital, Préstamos e hipotecas, Inversión y ahorro, y Empresas.

**Checks de cumplimiento:** saludo e identificación del agente, verificación de identidad del cliente antes de dar información, aviso de protección de datos, no solicitar PIN ni claves completas, ofrecimiento del bloqueo preventivo en casos de fraude y despedida con resumen de la gestión.

## KPIs y métricas

| KPI | Definición |
|---|---|
| Volumen | Nº de conversaciones del periodo, por canal. |
| Duración media (AHT) | Media de `duration_s`. |
| Sentimiento medio | Media del sentimiento global y % de conversaciones negativas (< -0,3). |
| Tasa de resolución | % de conversaciones `resuelta`. |
| Tasa de escalado | % de conversaciones `escalada`. |
| FCR | % de clientes sin otro contacto en los 7 días siguientes. |
| CSAT predicho | Media del CSAT predicho. |
| Esfuerzo del cliente | Media del esfuerzo predicho. |
| Cumplimiento | % de conversaciones que superan todos los checks, más el % por check. |
| Riesgo de abandono | % de conversaciones con riesgo `alto`. |
| Primera respuesta (solo chat) | Media de segundos hasta el primer turno del agente. |
| Turnos medios | Media de turnos por conversación. |
| Distribución por main topic | Volumen y % por main topic, y el resto de KPIs desglosados por main topic. |

## Datos por conversación (no son KPIs)

Además de los KPIs, cada conversación tiene dos datos descriptivos que la plataforma muestra y permite usar como filtro:

| Dato | Definición |
|---|---|
| **Summary** (`summary`) | Resumen de 2 a 4 frases: motivo del contacto, gestión realizada y resultado. Por ejemplo: «La clienta llama por un cargo de 89,90 € en Amazon que no reconoce. El agente verifica su identidad, bloquea la tarjeta y abre una reclamación. Recibirá una tarjeta nueva en 5 días hábiles.» |
| **Main topic** (`main_topic`) | Motivo principal del contacto, con un único valor del catálogo bancario de abajo. |

### Catálogo de main topics

| Código | Main topic | Ejemplos |
|---|---|---|
| `alta_cliente` | Alta de cliente | Apertura de cuenta, alta online, documentación necesaria. |
| `baja_cancelacion` | Baja o cancelación | Cancelar la cuenta o la tarjeta, portabilidad a otro banco. |
| `contratacion_producto` | Contratación de producto | Tarjeta de crédito, préstamo personal, seguro, depósito. |
| `cargo_no_reconocido` | Cargo no reconocido | Compra desconocida, posible fraude, suscripción no autorizada. |
| `bloqueo_tarjeta` | Bloqueo de tarjeta | Robo o pérdida, bloqueo preventivo, desbloqueo. |
| `acceso_banca_digital` | Acceso a banca digital | Usuario bloqueado, claves, firma o SMS de confirmación, app. |
| `transferencias_bizum` | Transferencias y Bizum | Transferencia no recibida, errónea o retenida, límites de Bizum. |
| `comisiones` | Reclamación de comisiones | Comisión de mantenimiento, de descubierto o por uso de cajero. |
| `recibos_domiciliaciones` | Recibos y domiciliaciones | Devolución de recibo, domiciliar nómina o recibos. |
| `prestamos_hipotecas` | Préstamos e hipotecas | Cuota, amortización anticipada, subrogación, carencia. |
| `tarjeta_denegada` | Pago o tarjeta denegada | Pago rechazado, límite de tarjeta, compra online bloqueada. |
| `cajeros` | Incidencia en cajero | Dinero no entregado, tarjeta retenida, ingreso no abonado. |
| `datos_personales` | Cambio de datos personales | Domicilio, teléfono, email, actualización del DNI. |
| `consulta_saldo_movimientos` | Consulta de saldo y movimientos | Saldo, extractos, certificados. |
| `reclamacion_queja` | Reclamación o queja general | Mala atención, esperas, queja formal al Servicio de Atención al Cliente. |

## Criterios de aceptación

### Base y acceso

1. `uvicorn` levanta la API y `GET /api/health` responde `200`. `npm run dev` levanta el front, que carga contra esa API.
2. Dos arranques con la misma semilla y la misma fecha de referencia generan exactamente el mismo conjunto de 1.000 conversaciones (test de backend).
3. `POST /api/auth/login` con un usuario demo válido devuelve un token; con credenciales inválidas devuelve `401`. Cualquier endpoint de datos sin token devuelve `401`.
4. Un rol sin un permiso recibe `403` en el endpoint correspondiente (test por rol), y el menú del front no muestra la sección.
5. La navegación lateral incluye Dashboards, Conversaciones, Explorador, Búsqueda semántica, Flujos de insights, Configuración y Usuarios y roles. Las secciones aún no implementadas muestran un estado vacío «Próximamente».

### Datos mock bancarios, summary y main topic

6. Cada conversación tiene un `main_topic` del catálogo y un `summary` no vacío de 2 a 4 frases (test sobre todo el dataset).
7. La transcripción es coherente con su main topic: contiene al menos una expresión característica de ese topic, y el summary menciona el motivo y el resultado de la gestión (test con palabras clave por topic).
8. Todos los main topics del catálogo aparecen en el dataset, con una distribución realista y no uniforme; por ejemplo, `cargo_no_reconocido` y `acceso_banca_digital` están entre los cinco con más volumen. Cada topic se asocia a sus colas habituales; por ejemplo, `cargo_no_reconocido` va sobre todo a «Fraude y seguridad».
9. Los datos sensibles de las transcripciones (DNI, IBAN, tarjeta) son ficticios y con formato válido pero inventado; ninguna tarjeta aparece completa, solo los últimos 4 dígitos.

### Dashboards

10. Hay al menos tres dashboards predefinidos: **Visión general**, **Calidad y cumplimiento** y **Experiencia de cliente**. Cada uno muestra tarjetas de KPI y gráficos (serie temporal y desgloses).
11. **Visión general** incluye la distribución por main topic (barras ordenadas por volumen) y una tabla con los KPIs principales desglosados por main topic.
12. Cada tarjeta de KPI muestra el valor del periodo, el valor del periodo anterior equivalente y la variación en %. El backend calcula ambos valores, y un test compara el resultado con un cálculo independiente sobre el dataset.
13. Los filtros globales (rango de fechas, canal, cola, agente y main topic) recalculan todos los widgets del dashboard y se reflejan en la URL, de modo que recargar la página conserva la vista.
14. La serie temporal permite granularidad día o semana.

### Drill-down

15. Al pulsar una tarjeta de KPI, un punto o barra de un gráfico o un segmento de desglose, se navega al listado de conversaciones con los filtros del dashboard más el filtro del elemento pulsado. Por ejemplo, la barra «Cargo no reconocido» del 3 de marzo aplica `main_topic=cargo_no_reconocido` y esa fecha.
16. El número de conversaciones del listado coincide con el valor de volumen que tenía el elemento pulsado (test end-to-end de componente o de API).
17. El listado muestra los filtros activos como chips eliminables, paginación (25 por página), orden por fecha, duración y sentimiento, y columnas con fecha, canal, cola, agente, main topic, summary (primera frase truncada, completo al pasar el ratón), sentimiento, resolución y CSAT predicho.

### Detalle de conversación

18. El detalle muestra la transcripción como un chat tipo WhatsApp: burbujas del cliente a la izquierda, del agente a la derecha, el bot con un color distinto y los mensajes de sistema centrados. Cada burbuja lleva su marca de tiempo relativa, y un icono indica si es voz transcrita o chat.
19. Cada burbuja muestra un indicador de sentimiento, y las palabras clave del análisis aparecen resaltadas.
20. La cabecera del detalle muestra el main topic como etiqueta destacada y el summary completo, por encima del chat.
21. Un panel lateral muestra temas secundarios, gráfico de evolución del sentimiento por turno, checklist de cumplimiento, resolución, CSAT y esfuerzo predichos, riesgo de abandono y entidades.
22. Al pulsar un punto de la evolución del sentimiento, el chat se desplaza a ese turno.
23. Desde el detalle se vuelve al listado conservando filtros, página y orden.

### Calidad

24. `pytest` y `npm test` pasan en verde. `npm run build` y `npm run lint` terminan sin errores.
25. Con el dataset completo, los endpoints de métricas y del listado responden en menos de 500 ms en local (test de backend con umbral).

## Conocimiento afectado

- [Propósito del proyecto](../../vault/producto/proposito-del-proyecto.md): está en `draft`. Hay que actualizarlo con la definición de producto (plataforma web de speech & text analytics para la atención al cliente de un banco, solo sobre transcripciones) y pasarlo a `active`.
- [Arquitectura del harness](../../vault/arquitectura/arquitectura-del-harness.md): describe solo el harness. Hay que crear una entrada nueva, `vault/arquitectura/arquitectura-de-la-plataforma.md`, con front, API, modelo de datos y flujo de auth.
- [Decisiones](../../vault/decisiones/Index.md): hay que crear ADR-002 (stack Vite + FastAPI con datos mock) y ADR-003 (auth mock por roles).
- [Glosario](../../vault/glosario/terminos-del-harness.md): hay que añadir AHT, FCR, CSAT, summary, main topic, drill-down y riesgo de abandono.
- Hay que crear `vault/producto/catalogo-de-main-topics.md` como fuente canónica del catálogo bancario.
- [Ciclo de entrega](../../vault/ingenieria/ciclo-de-entrega.md): hay que añadir los comandos de arranque y de test de front y back.

## Alcance

- Estructura `frontend/` y `backend/` con scripts de arranque y test, y un README de uso.
- Generador de datos mock bancarios con summary y main topic, cálculo de KPIs y API de métricas, catálogo, conversaciones y auth.
- Shell de la app (login, layout y navegación por permisos).
- Tres dashboards predefinidos, filtros globales, drill-down, listado y detalle tipo chat.

## Fuera de alcance

- Integración real con Genesys, base de datos o persistencia entre reinicios.
- Audio, reproducción de grabaciones y métricas acústicas (silencios, solapamientos, tono).
- Generación real del summary o clasificación real del main topic con un modelo; aquí vienen del generador mock.
- Constructor de dashboards personalizados por el usuario.
- Exportaciones (CSV/PDF), alertas y notificaciones.
- Las funcionalidades de FE002–FE006; aquí solo aparecen sus entradas de menú.
- Despliegue, CI y observabilidad de producción.

## Riesgos y asunciones

- **Asunción:** la lista de KPIs y el catálogo de main topics cubren lo que necesitas. Si falta algo, conviene añadirlo ahora; después cambia el generador de datos.
- **Asunción:** summary, main topic, sentimiento, CSAT y demás análisis son mock generados con reglas coherentes, no salidas de un modelo real.
- **Riesgo:** las conversaciones generadas por plantillas pueden resultar repetitivas. Para mitigarlo, cada main topic tendrá varias plantillas de diálogo con variaciones de importes, comercios, productos y desenlace, y el generador usará distribuciones sesgadas por cola y main topic, con correlación entre sentimiento, resolución y CSAT.
- **Riesgo:** un token simple no es seguro para producción; se acepta solo para demo (ADR-003).
