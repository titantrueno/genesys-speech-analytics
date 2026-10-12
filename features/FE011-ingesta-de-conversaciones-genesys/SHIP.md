# FE011 — Ship

> Fase `/ship`. Fecha: 2026-10-12. Entrega: [Plataforma v0.8.0](../../vault/entregas/2026-10-12-plataforma-v0-8-0.md).

## Trazabilidad

| Artefacto | Estado |
|---|---|
| [spec.md](spec.md) | Aprobada el 2026-10-12, tras dividir la petición original (el cambio de origen de datos pasa a [FE012](../FE012-switch-entre-datos-sinteticos-reales/spec.md)) |
| [plan.md](plan.md) | T1–T9 hechas (la T7 en T7a y T7b), cada una con rojo a verde, mutaciones y pruebas reales |
| [VERIFY.md](VERIFY.md) | Verde: 28 de 28 criterios con evidencia. Dos fallos encontrados y corregidos: el tope de resultados y el uso de `xmax` |
| [REVIEW.md](REVIEW.md) | Aprobado, sin critical ni major abiertos: R1 (texto de turnos en el log por un error de PostgreSQL) y R2 (ejecución bloqueada) resueltos |

## Resumen del cambio

Integración trunk-based en `main`, de `v0.7.0` a `v0.8.0`.

- **Infraestructura:** PostgreSQL 16 en Docker (`docker-compose.yml`) y `.env.example`. El gate (`ci.sh` y `ci.yml`) levanta PostgreSQL y exige los tests `pg`.
- **Servicio de ingesta** (`backend/ingestion/`, proceso aparte en el 8001):
  - cliente de Genesys (OAuth, reintentos, redacción de secretos);
  - pipeline `extraer → normalizar → analizar → cargar`;
  - flujos de descarga con intervalo relativo o específico, ejecución manual y programada, historial y log;
  - lectura interna de conversaciones y estado del conector.
- **API:**
  - `/api/download-flows` (9 operaciones) y `/api/config/connectors/genesys` (estado y «Probar conexión»), que delegan en el servicio de ingesta con un token interno y responden `503` si no está disponible;
  - el OpenAPI pasa de 58 a 69 operaciones y a la versión `0.8.0`.
- **Front:**
  - el listado de Flujos de insights une los dos tipos y añade las columnas «Tipo» y «Próxima ejecución»;
  - formulario del flujo de descarga, ejecución con log en vivo e historial;
  - tarjeta de Genesys en Configuración → Fuentes de datos.
- **Datos de prueba:** 10 fixtures saneadas de conversaciones reales del 2026-10-12, una por tipo, y `scripts/capture_genesys_fixtures.py` para volver a capturarlas.
- **Dependencia:** `psycopg[binary]` 3.3 (LGPL-3.0).

## Pipeline con gates

`./scripts/ci.sh` termina con código 0:

- vault sin errores;
- 854 tests de backend con cada una de las dos combinaciones de dataset;
- **57 tests con PostgreSQL** (`REQUIRE_PG=1`; si no hay base de datos, el gate falla en lugar de saltarlos);
- OpenAPI al día y válido;
- 352 tests de front, lint y build;
- `pip-audit` y `npm audit --audit-level=high` sin vulnerabilidades.

`.github/workflows/ci.yml` ejecuta lo mismo, con un contenedor de servicio `postgres:16`. Con esta entrega se sube a GitHub, así que se ejecutará por primera vez con estos cambios.

## Observabilidad

- **Salud:** `GET /health` del servicio de ingesta (con el token) informa del servicio y de PostgreSQL. `GET /api/config/connectors/genesys` lo resume para la UI: disponible o no, región, credenciales, última prueba, última descarga y conversaciones por canal y calidad.
- **Por ejecución:** estado, contadores (encontradas, descargadas, insertadas, actualizadas, omitidas, con error, calidad y mensajes no entregados), duración y un log por etapas con nivel, sin texto de turnos ni secretos. Se puede consultar en la UI y descargar en texto.
- **Proceso:** los fallos inesperados de una ejecución y de los tics del programador se registran con el logger `ingestion` (R2 y R3).
- **Pendiente con despliegue real:** métricas agregadas (descargas por día, errores, latencia de Genesys), alertas sobre ejecuciones en `error` y un log estructurado en JSON.

## Rollout y rollback

- **Rollout:** etiqueta `v0.8.0` en `main`, subida a GitHub. No hay despliegue. La ingesta es opcional: sin PostgreSQL ni servicio de ingesta, la plataforma funciona como en `v0.7.0` y solo las rutas de descargas responden `503`. Las conversaciones reales todavía no se ven en la plataforma (eso es FE012).
- **Rollback:**
  - **Código:** `git checkout v0.7.0`, o revertir los commits de FE011.
  - **Base de datos:** las migraciones solo añaden tablas y columnas, así que el código anterior no las toca.
  - **Datos reales:** se borran con `docker compose down -v`, que elimina el volumen de PostgreSQL y no tiene vuelta atrás.
  - **Descargas programadas:** se paran poniendo los flujos en «Solo manual» o parando el servicio ([runbook](../../vault/operaciones/runbook-ingesta-de-genesys.md)).

## Pendiente tras la entrega

- **FE012:** cambiar entre datos sintéticos y reales en toda la plataforma (spec en borrador).
- **Fase con LLM:** análisis de las conversaciones reales detrás de `Analyzer`.
- **Descarga en paralelo:** respetando el *rate limit* de Genesys (R13).
- **Hipótesis abiertas:** sentimiento neutro por defecto y «sin `userIds` = bot» ([datos de Genesys para STA](../../vault/producto/datos-de-genesys-para-sta.md)).
- **Publicación:** sin mención de coautoría, según la decisión de la persona propietaria ([ciclo de entrega](../../vault/ingenieria/ciclo-de-entrega.md)).
