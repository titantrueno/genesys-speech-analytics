---
title: "Estado operativo inicial"
type: runbook
status: active
owners: [equipo-del-proyecto]
tags: [operaciones, runbook, local]
created: 2026-09-27
updated: 2026-10-13
---

# Estado operativo inicial

## Cuándo usarlo

Para arrancar, comprobar o revertir la plataforma en su estado actual: **demo local con datos mock**, más la ingesta de conversaciones reales de Genesys en PostgreSQL (FE011), que tiene su propio [runbook](runbook-ingesta-de-genesys.md). No existe entorno de producción, infraestructura desplegada ni telemetría.

## Prerrequisitos

- Python 3.11+ y Node 20+.
- Entorno del backend creado (`python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt`) y dependencias del front instaladas (`cd frontend && npm install`).

## Procedimiento

1. API: `cd backend && .venv/bin/uvicorn app.main:app --port 8000`. Para una demo fuera de local, define `AUTH_SECRET` (ver [ADR-003](../decisiones/adr-003-auth-mock-por-roles.md)).
2. Web: `cd frontend && npm run dev` (desarrollo), o `npm run build && npx vite preview` (build de producción, que reenvía `/api` y `/openapi.json` a la API).
3. Gate antes de entregar un cambio: `./scripts/ci.sh` debe terminar con código 0.

## Verificación

- **Salud de la API:** `curl -s localhost:8000/api/health` devuelve `{"status":"ok"}`. La API responde tras construir el índice de búsqueda semántica al arrancar (unos 2,5 s).
- **Humo funcional:** login con un usuario demo, abrir un dashboard y hacer drill-down al listado.
- **Datos:** con `DATA_SEED` y `DATA_REFERENCE_DATE` fijos, el dataset es reproducible. La suite del backend pasa con cualquier combinación (FE009); `./scripts/ci.sh` la ejecuta con la del `conftest.py` y con semilla 7 y referencia 2026-11-10.
- **Gate justo después de parar servidores de prueba:** el primer `./scripts/ci.sh` tras parar la API y la web puede fallar con timeouts dispersos en tests sin relación (la máquina sigue cargada); espera unos 10 s y vuelve a lanzarlo.
- **Ejecutar el gate en un portátil:** con batería, el reposo del sistema congela los procesos y hace fallar tests por tiempo; usa la corriente y `caffeinate -i ./scripts/ci.sh`.
- **Configuración (FE005):** la sección Configuración cambia taxonomía, checks, umbrales, zona horaria, enmascarado y modelo por defecto en caliente. General, Origen de datos, Privacidad y Modelos de IA se conservan al reiniciar (FE015, a través del servicio de ingesta; con `--no-db`, no); la taxonomía, los checks y los umbrales se pierden. Los conectores de «Fuentes de datos» son **mock**: «Sincronizar» solo actualiza la fecha. Debajo, la tarjeta «Genesys Cloud · datos reales» (FE011) muestra el estado real del servicio de ingesta y permite «Probar conexión». `curl -s localhost:8000/api/config/public` devuelve nombre, zona horaria e idioma sin sesión. **Idioma de la interfaz (FE016):** «Idioma de la interfaz» en General ofrece Español (España) e English (United States) y cambia menús y textos fijos de toda la plataforma, también el login; no cambia los datos (conversaciones, resúmenes, main topics, palabras clave). Los mensajes de la API salen siempre en inglés. Para probarlo en local sin base, arranca `./scripts/dev.sh --no-db` con la variable de entorno `INGESTION_TOKEN` vacía: con el valor del `.env` y sin servicio de ingesta, guardar el idioma responde `503`.
- **Usuarios y roles (FE006):** con `admin`, «Usuarios y roles» permite crear usuarios (contraseña demo compartida), roles personalizados y cambiar la matriz de permisos; todo se pierde al reiniciar la API. Si alguien no ve una sección que debería, revisa su rol en la matriz: el cambio se aplica en su siguiente petición, sin volver a entrar. Las protecciones impiden quedarse sin administrador. Con sesión, cada respuesta lleva `X-Auth-Version`, que sube con cada cambio de usuarios o roles.
- **Especificación de la API (FE010):** `curl -s localhost:8000/openapi.json` devuelve el OpenAPI (versión de la entrega y 72 operaciones) sin sesión. Con `config:view`, Configuración → «API» la muestra con Swagger UI. Si sale «No se ha podido cargar la especificación de la API.», comprueba que la API responde y que el proxy de Vite (o `VITE_API_URL` con `CORS_ORIGINS`) llega a `/openapi.json`. «Try it out» hace llamadas reales con la sesión: las escrituras cambian el estado en memoria y quedan en la auditoría; reiniciar la API lo restablece.
- **Origen de datos (FE012):** Configuración → Fuentes de datos cambia entre sintético y real. El real necesita `DATABASE_URL` en el `.env` (solo lectura) y conversaciones descargadas por la ingesta; si no hay conexión, las secciones de datos responden `503` y Configuración permite volver a sintético. Con datos reales el periodo por defecto acaba hoy. El origen vuelve a sintético al reiniciar la API.
- **Servicio de LLM (FE013):** Configuración → Modelos de IA muestra qué proveedores tienen clave y permite «Probar». Los prompts con un proveedor real necesitan el servicio de LLM ([runbook](runbook-servicio-llm.md)); «Guardar en campos» necesita además datos reales, PostgreSQL y el servicio de ingesta. Sin el servicio, los flujos simulados siguen funcionando. Desde FE014 puede guardar todo el análisis («Generar análisis completo») y cada dato se ve y cuenta en los KPIs en cuanto existe.
- **Flujos de insights (FE004):** crear un flujo, ejecutarlo y ver cómo avanzan los nodos. El ritmo de la ejecución simulada se ajusta con `FLOW_RUN_STEP_DELAY_MS` (15 ms por elemento por defecto; 0 en los tests). Los flujos se conservan al reiniciar (FE015, a través del servicio de ingesta; con `--no-db`, no); las ejecuciones viven en memoria y se pierden. Si el servicio de ingesta no responde, la lista de flujos y sus cambios dan `503`. **Caja «Genesys download» (FE017):** un flujo puede empezar descargando de Genesys (necesita el servicio de ingesta y el origen «Real») y programarse; la API lanza los programados con un hilo propio (`FLOW_SCHEDULER=0` lo apaga). Diagnóstico en el [runbook de la ingesta](runbook-ingesta-de-genesys.md).

## Rollback

- Cada entrega tiene una etiqueta de Git (por ejemplo `v0.1.0`). Para volver a la anterior: `git checkout <etiqueta>`, o revertir los commits con `git revert <desde>..<hasta>`.
- La API no tiene datos persistentes que migrar: reiniciarla regenera el dataset. Los datos reales de Genesys están en PostgreSQL; para revertirlos, ver el [runbook de la ingesta](runbook-ingesta-de-genesys.md).

## Escalado

El propietario del proyecto (`equipo-del-proyecto`).

**Pendiente, hipótesis:** cuando exista un despliegue real, este runbook debe incorporar señales de salud, logs estructurados, métricas, alertas y rollout escalonado.

## Fuentes

- [README del proyecto](../../README.md)
- [README del backend](../../backend/README.md)
- [Script de CI local](../../scripts/ci.sh)
- [Runbook de la ingesta de Genesys](runbook-ingesta-de-genesys.md)
- [Runbook del servicio de LLM](runbook-servicio-llm.md)
