# FE015 — Persistencia de flujos de insights y preferencias

> Estado: **construida y verificada** el 2026-10-13, pendiente de review y ship. Corrige un fallo que reportó la persona usuaria y amplía FE004, FE005 y FE012. Aplica ADR-008.

## Problema

- Al parar y volver a levantar el entorno, los **flujos de descarga** se conservan (los guarda el servicio de ingesta en PostgreSQL, FE011), pero los **flujos de insights** desaparecen: vivían solo en la memoria de la API (ADR-002).
- El **origen de datos** (Configuración → Fuentes de datos) también vivía en memoria: tras reiniciar volvía a «Sintético» aunque se hubiera elegido «Real».

## Decisiones

| Pregunta | Decisión |
|---|---|
| ¿Dónde se guarda? | En PostgreSQL, **a través del servicio de ingesta**, como los flujos de descarga: la API sigue sin escribir en la base (ADR-008). |
| ¿Por persona o global? | **Global.** El origen de datos ya era una sección de la configuración global (FE012) que afecta a toda la plataforma; se persiste tal cual. Un origen por persona sería otra feature. |
| ¿Qué preferencias? | Las secciones simples de la configuración: General (nombre, zona horaria, idioma), Origen de datos, Privacidad y Modelos de IA. La taxonomía, los checks y los KPIs siguen en memoria: tienen valores base que evolucionan con el código. |
| ¿Y las ejecuciones de los flujos de insights? | Siguen en memoria (resultados de hasta ~1 MB y estado en vivo). |
| ¿Si el servicio de ingesta no responde? | Un cambio que no se puede guardar **no se aplica** (`503`), en vez de quedarse en memoria y perderse en silencio. Sin `INGESTION_TOKEN` (`dev.sh --no-db`) todo vive en memoria, como antes. |

## Criterios de aceptación

1. Un flujo de insights creado, renombrado, con el grafo guardado o duplicado sigue igual (nombre, grafo, autoría, fechas y estado) tras reiniciar la API y el servicio de ingesta; uno borrado no vuelve.
2. El origen de datos y las secciones General, Privacidad y Modelos de IA se recuperan tras reiniciar. El índice de búsqueda se construye al arrancar con el origen guardado.
3. Si no se puede guardar un cambio de un flujo o de una sección, la API responde `503` y el estado (y la auditoría) no cambian.
4. Si al arrancar no se pueden leer los flujos guardados, la lista de flujos responde `503` (no una lista vacía) hasta que se puedan leer.
5. Si al arrancar no se puede leer la configuración guardada, la API sigue con los valores por defecto y lo reintenta cada 5 s, sin intentarlo en cada petición.
6. Un flujo o una sección guardados que ya no encajan en el modelo se ignoran sin impedir cargar el resto.
7. El servicio de ingesta solo acepta estado bien formado: identificador `1FL` que coincide con la ruta, campos conocidos, claves de sección en minúsculas y objetos JSON como valor; todo con el token interno.
8. El contrato OpenAPI documenta los `503` nuevos y la persistencia.

## Diseño

- **Migración `0007_platform_state.sql`:** tablas `insight_flow` (grafo en `jsonb`) y `platform_setting` (una fila por sección).
- **Servicio de ingesta (`backend/ingestion/state.py`):** `GET /insight-flows`, `PUT /insight-flows/{id}` (crea o sustituye), `DELETE /insight-flows/{id}` (idempotente), `GET /settings` y `PUT /settings/{key}`.
- **API (`backend/app/state_backend.py`):** `IngestionStateBackend` con el token interno; `StateUnavailable` se traduce a `503`.
- **`FlowStore`:** carga perezosa bajo cerrojo; cada cambio se guarda antes de aplicarse en memoria.
- **`ConfigStore`:** carga al arrancar (en el `lifespan`, antes del índice de búsqueda) con reintento; `apply_change` guarda las secciones persistidas antes de aplicar y auditar.

## Evidencia

- `backend/tests/test_platform_state.py` (criterios 1–6, con un doble en memoria) y `backend/tests/test_platform_state_pg.py` (criterios 1, 2 y 7, con el servicio de ingesta real y PostgreSQL, reiniciando los dos procesos).
- Prueba manual del 2026-10-13 con `./scripts/dev.sh` en puertos propios: crear el flujo «Prueba persistencia FE015» y elegir «Real»; parar todo (también PostgreSQL) y volver a levantar. La API y la página «Flujos de insights» del navegador mostraron el flujo y el origen seguía en `real`. Después se borró el flujo y se restableció «Sintético».
