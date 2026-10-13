---
title: "Runbook de la ingesta de Genesys"
type: runbook
status: active
owners: [equipo-del-proyecto]
tags: [operaciones, runbook, genesys, ingesta, postgresql, fe011]
created: 2026-10-12
updated: 2026-10-13
---

# Runbook de la ingesta de Genesys

## Cuándo usarlo

Para arrancar PostgreSQL y el servicio de ingesta, comprobar la conexión con Genesys Cloud y diagnosticar una descarga desde su log ([ADR-008](../decisiones/adr-008-postgresql-y-servicio-de-ingesta.md)).

## Prerrequisitos

- **Docker:** en la máquina de desarrollo no hay Docker Desktop; el daemon es Colima (`colima start`, o `brew services start colima` para que arranque solo).
- **`.env` en la raíz**, con las claves de `.env.example`: `GENESYS_CLIENT_ID`, `GENESYS_CLIENT_SECRET`, `GENESYS_REGION`, `POSTGRES_PASSWORD`, `DATABASE_URL` e `INGESTION_TOKEN`. Nunca se versiona ni se copia en el vault.

## Procedimiento

Atajo: `./scripts/dev.sh` ejecuta los pasos 1 a 3 (y la web) y lo para todo con Ctrl+C, incluidos el contenedor de PostgreSQL y Colima si lo arrancó él (ver el README, «Entorno local con un solo comando»). Los pasos manuales siguen siendo válidos:

1. **PostgreSQL:** `docker compose up -d --wait`, desde la raíz.
2. **Servicio de ingesta:** `cd backend && .venv/bin/uvicorn ingestion.main:app --port 8001`. Al arrancar:
   - aplica las migraciones pendientes;
   - da por interrumpidas las ejecuciones que quedaron activas;
   - recalcula la próxima ejecución de cada flujo programado;
   - arranca el programador, con un tic cada 30 s.
3. **API:** `.venv/bin/uvicorn app.main:app --port 8000`, con `INGESTION_URL` si el servicio no está en `http://localhost:8001`.
4. **Probar la conexión:** en la web, Configuración → Fuentes de datos → «Probar conexión» (con `config:edit`).
5. **Descargar:** en Flujos de insights, «Nuevo flujo» → «Descarga de transcripciones». Después, «Ejecutar ahora» o una programación.
6. **Redescargar (FE013):** sin «Sobrescribir», una conversación que ya está en la base no se descarga (log «Ya existe: no se descarga», recuento «Ya existentes»). Para recoger cambios o reprocesos de Genesys, ejecuta un flujo con «Sobrescribir»: sustituye la conversación y **borra** su summary y main topic generados por el LLM.

## Verificación

- **Servicio:** `curl -H "Authorization: Bearer <INGESTION_TOKEN>" localhost:8001/health` devuelve `{"status":"ok","database":"ok"}`. Sin el token, `401`.
- **Estado del conector:** la tarjeta «Genesys Cloud · datos reales» muestra «Disponible», la región, la última descarga y las conversaciones por canal y calidad.
- **Una conversación:** `GET localhost:8001/conversations/<id de Genesys o 1CO>` (con el token) devuelve la conversación normalizada.
- **Base de datos:** `docker compose exec postgres psql -U speech -d speech_analytics`.

### Diagnóstico con el log de una ejecución

| Entrada | Significa | Qué hacer |
|---|---|---|
| `error` · autenticación · «Credenciales de Genesys no válidas» | El cliente OAuth no es válido o le faltan permisos | Revisar `GENESYS_*` en el `.env` y el rol del cliente OAuth en Genesys; probar la conexión |
| `error` · «Sin permiso en Genesys para GET …» | Al cliente OAuth le falta un permiso de esa ruta | Añadir el permiso al rol del cliente en Genesys |
| `aviso` · «Conversación sin transcripción» | No hay frases (grabación o transcripción ausente) | Normal si la grabación falló; la conversación se guarda con su analítica |
| `aviso` · «Transcripción parcial: intervino …» | El agente o el bot hablaron y no tienen frases | Suele deberse a incidencias de grabación; una descarga posterior **con «Sobrescribir»** la actualiza si Genesys la completa |
| `info` · «Ya existe: no se descarga» | La conversación ya estaba en la base y el flujo no sobrescribe | Normal; usar «Sobrescribir» solo para redescargar |
| `aviso` · «N mensaje(s) no entregado(s)» | El agente escribió cuando el cliente ya se había ido | Informativo; el turno se guarda con su texto, marcado como no entregado |
| `aviso` · «Omitida: en curso» | La conversación no había terminado | Se recoge en una descarga posterior |
| `aviso` · «Ejecución programada de las HH:MM omitida…» | A esa hora seguía otra ejecución del mismo flujo | Si se repite, espaciar la programación |
| `error` · «No se pudo procesar: …» | Una conversación falló tras los reintentos | La ejecución sigue con las demás; se recoge en la siguiente descarga |

### Diagnóstico de un flujo de insights con caja «Genesys download» (FE017)

- **Dónde mirar:** en la ejecución del flujo, la sección «Descarga de Genesys» da el estado y los contadores, y «Ver log de la descarga» abre el mismo log que el de un flujo de descarga (tabla de arriba).
- **«The flow is not saved in the database: save it and try again»:** la ingesta no encuentra el flujo en `insight_flow`. Pasa si la API corre sin `INGESTION_TOKEN` (sin persistencia de FE015) o si el flujo no llegó a guardarse; guardarlo de nuevo con la ingesta disponible lo resuelve.
- **Todo `omitido` («The download returned no conversations»):** la descarga no insertó ni actualizó nada. Sin «Sobrescribir», las conversaciones que ya estaban no cuentan: es lo normal en una programación «hoy» cada hora sin conversaciones nuevas.
- **Ejecución programada en `error` sin descarga:** el flujo no validó a su hora (por ejemplo, el origen de datos estaba en «Sintético», `download_needs_real_origin`); los motivos están en las notas de la ejecución.
- **No se lanza a su hora:** la caja tiene que estar programada y activa, y la API con `FLOW_SCHEDULER` distinto de `0`. Tras reiniciar la API, la primera ejecución es la siguiente hora programada.

La API responde `503` («El servicio de ingesta no está disponible») cuando el servicio no responde o los tokens de la API y del servicio no coinciden.

## Rollback

- **Las migraciones solo añaden.** Para volver a una versión anterior del código, basta con `git checkout <etiqueta>`, y las tablas nuevas se ignoran. La `0008` (FE017) hace además opcional `download_run.flow_id`: el código anterior no ve las descargas de las cajas en el historial de los flujos de descarga, pero «Última descarga» del conector puede mostrar una sin flujo.
- **Vaciar los datos reales:** `docker compose down -v` borra el volumen de PostgreSQL con las conversaciones, los flujos de descarga y sus logs. No tiene vuelta atrás.
- **Parar las descargas programadas:** poner los flujos en «Solo manual» o desactivarlos, o parar el servicio de ingesta.

## Escalado

El propietario del proyecto (`equipo-del-proyecto`). Para permisos o credenciales del cliente OAuth, quien administra la organización de Genesys.

## Fuentes

- [README del backend, servicio de ingesta](../../backend/README.md)
- [Verificación de FE011](../../features/FE011-ingesta-de-conversaciones-genesys/VERIFY.md)
- [Ejecutor de descargas](../../backend/ingestion/runs.py)
- [Spec FE017](../../features/FE017-caja-genesys-en-flujos-insights/spec.md)
- [docker-compose.yml](../../docker-compose.yml)
