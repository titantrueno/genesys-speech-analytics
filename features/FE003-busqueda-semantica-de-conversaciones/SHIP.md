# FE003 — Ship

> Fase `/ship`. Fecha: 2026-09-28. Entrega: [Plataforma v0.3.0](../../vault/entregas/2026-09-28-plataforma-v0-3-0.md).

## Trazabilidad

| Artefacto | Estado |
|---|---|
| [spec.md](spec.md) | Aprobada (revisada tras v0.2.0; ampliada con los criterios 18–20) |
| [plan.md](plan.md) | T1–T7 hechas, más T5b y T5c, con evidencia |
| [VERIFY.md](VERIFY.md) | Verde; limitación de robustez medida y documentada |
| [REVIEW.md](REVIEW.md) | Aprobado; sin critical ni major abiertos |

## Resumen del cambio

Integración trunk-based en `main`, de `v0.2.0` a `v0.3.0`:

- **Backend:**
  - motor `TfidfEngine` detrás de la interfaz `SearchEngine`, con índice construido al arrancar;
  - diccionario de sinónimos del dominio;
  - `GET /api/search/semantic` (filtros, umbral, agrupación y `max_score`) y `GET /api/search/similar/{id}`.
- **Front:**
  - sección Búsqueda semántica con resultados por fragmento, resaltado, umbral en contexto y agrupación;
  - detalle abierto en el turno del fragmento;
  - «Volver a la búsqueda» y «Buscar conversaciones similares».
- **Ajustes surgidos al verificar en el navegador:**
  - el fragmento mostrado prioriza lo que dice el cliente (T5b);
  - el umbral muestra la mejor puntuación de cada búsqueda (T5c);
  - las limitaciones del enfoque léxico están documentadas en [ADR-005](../../vault/decisiones/adr-005-busqueda-vectorial-ligera.md).

## Pipeline con gates

`./scripts/ci.sh` termina con código 0:

- vault;
- 317 tests de backend;
- 149 tests de front, lint y build;
- `npm audit` y `pip-audit` sin vulnerabilidades.

No hay dependencias nuevas: `requirements.txt` y `package.json` no cambian desde `v0.2.0`. `.github/workflows/ci.yml` sigue preparado y sin ejecutar, porque no hay remoto.

## Observabilidad

- `GET /api/health` responde cuando el índice ya está construido (unos 2,5 s tras arrancar).
- Códigos HTTP explícitos: `422` en parámetros no válidos, `404` en similares inexistentes y `403` sin `search:use`.
- La UI muestra avisos de error, de búsqueda vacía y de umbral excesivo.
- **Pendiente con despliegue real:** registrar latencia, número de resultados y búsquedas sin resultados como señal para ampliar el diccionario o migrar a embeddings.

## Rollout y rollback

- **Rollout:** etiqueta local `v0.3.0`. No afecta a FE001, FE002, FE007 ni FE008, que siguen verificadas en la misma suite (la extracción de `useRowNavigation` la cubren los tests de FE007).
- **Rollback:** `git checkout v0.2.0`. No hay datos persistentes; el índice se reconstruye en cada arranque.

## Pendiente tras la entrega

- R1: migrar a embeddings detrás de `SearchEngine` y compararlos con `backend/tests/search_relevance.py` como línea base.
- R4: FE005 debe enmascarar DNI e IBAN también en el índice de búsqueda.
- R6: con datos reales, construir el índice fuera del proceso de la API.
