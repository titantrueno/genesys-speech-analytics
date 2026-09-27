# FE001 — Revisión

> Fase `/review`. Fecha: 2026-09-27. Artefactos: [spec](spec.md) · [plan](plan.md) · [verificación](VERIFY.md). Siguiente paso: `/ship`.
> Alcance: FE001 junto con [FE007](../FE007-fila-completa-abre-detalle-conversacion/REVIEW.md) y [FE008](../FE008-identificadores-con-prefijo-y-uuid/REVIEW.md).

## Resultado

**Aprobado.** No quedan hallazgos critical ni major sin resolver. Los major encontrados se corrigieron con test de regresión; los minor y nits están resueltos o aceptados de forma explícita.

## Tamaño del cambio

Unas 4.900 líneas en `backend/app` y `frontend/src` desde la base (`03de25a`), por encima de las ~100 que recomienda el skill. Se mitigó construyendo en **commits atómicos por tarea** (9 de FE001, 4 de FE008, 3 de FE007 y 1 de corrección), cada uno con su evidencia rojo → verde en el plan correspondiente. La revisión se hizo por tareas y además sobre el conjunto.

## Evidencia de verificación

[VERIFY.md](VERIFY.md) contiene la auditoría del vault en verde (código 0). Tras los cambios de esta revisión, el resultado es 108 tests de backend y 72 de front, lint 0 y auditoría 0.

## Hallazgos

| # | Eje | Severidad | Hallazgo | Decisión |
|---|---|---|---|---|
| R1 | Seguridad / corrección | **major** | Un token con caracteres no ASCII (`Bearer abc.ñ`) provocaba **500**: `hmac.compare_digest` lanza `TypeError` con `str` no ASCII y solo se capturaba `ValueError` | **Resuelto:** se comparan `bytes`; test `test_malformed_or_non_ascii_token_returns_401_not_500` (6 casos, rojo → verde) |
| R2 | Corrección | **major** | Opciones rápidas de periodo calculadas con la fecha del navegador en lugar de la de referencia del backend | **Resuelto en `/test`** (`a0d6512`), con test de regresión |
| R3 | Corrección | **major** | Widgets sin estado de error: carga infinita ante 4xx/5xx | **Resuelto en `/test`** (`a0d6512`), con test de regresión |
| R4 | Conocimiento | **major** | Lecciones reutilizables sin capturar (FastAPI `_IncludedRouter`, Recharts en jsdom, `scrollIntoView`, generadores aleatorios aislados, fechas de test, estados de error, `compare_digest`, ARIA) | **Resuelto:** [lecciones de la construcción](../../vault/aprendizaje/lecciones-construccion-plataforma.md) |
| R5 | Seguridad | minor | El secreto HMAC tiene un valor por defecto de desarrollo, no hay límite de intentos de login y el token vive en `sessionStorage` (expuesto a XSS) | **Aceptado para demo local** ([ADR-003](../../vault/decisiones/adr-003-auth-mock-por-roles.md)); el README exige `AUTH_SECRET` fuera de local. Pasa a **major** antes de cualquier despliegue compartido |
| R6 | Seguridad | minor | DNI e IBAN ficticios visibles sin enmascarar en las transcripciones | **Aceptado:** el enmascarado está especificado en FE005 |
| R7 | Seguridad | minor | Sin restricción de datos por cola o equipo: todo usuario con `conversations:view` ve todas las conversaciones | **Aceptado:** fuera de alcance según la spec de FE006 |
| R8 | Seguridad | minor | `StarletteDeprecationWarning`: el `TestClient` con `httpx` está obsoleto | **Aceptado:** solo afecta a los tests; revisar al actualizar FastAPI o Starlette |
| R9 | Adherencia a la spec | minor | «Cumplimiento por check» no permite drill-down (criterio 15 habla de «segmento de desglose») | **Aceptado:** requiere un filtro por check en la API; queda anotado en el plan como pendiente |
| R10 | Adherencia a la spec | minor | La tarjeta «Cumplimiento» lleva a las conversaciones que **cumplen** (numerador), no a las que fallan | **Aceptado:** es consistente con el criterio 16 (el recuento coincide). Decisión de producto pendiente de confirmar |
| R11 | Adherencia a la spec | minor | A 1280 px la tabla del listado tiene 80 px de scroll horizontal | **Aceptado:** el scroll queda dentro de la tabla y la página no se rompe (lo que exige la spec); a 1440 px cabe entera |
| R12 | Adherencia a la spec | nit | Columna extra «Duración» y oxlint en lugar de ESLint | **Justificado:** la columna es necesaria para ordenar por duración (criterio 17); oxlint es el linter de la plantilla de Vite 8 |
| R13 | Corrección | minor | El FCR de los últimos 7 días es optimista porque la ventana de recontacto no está completa | **Aceptado y documentado** en la [arquitectura de la plataforma](../../vault/arquitectura/arquitectura-de-la-plataforma.md) |
| R14 | Simplicidad | nit | Formateadores `Intl` duplicados en 4 componentes | **Resuelto:** `formatDecimal` y `formatSigned` en `lib/format.ts` |
| R15 | Simplicidad | nit | `useDashboardFilters` también lo usa el listado; el nombre refleja su origen | **Aceptado:** renombrarlo tocaría muchos ficheros sin cambiar el comportamiento |
| R16 | Rendimiento | nit | Cada petición filtra linealmente las 1.000 conversaciones | **Aceptado:** menos de 500 ms comprobado; con datos reales hará falta un índice o una base de datos (fuera de alcance, ADR-002) |
| R17 | Mantenibilidad | minor | Los scripts de navegador (Playwright) usados como evidencia no están versionados | **Aceptado por ahora:** no hay CI ni navegador gestionado. La evidencia está descrita en VERIFY; se propone versionarlos cuando exista CI |

## Revisión por ejes

- **Corrección:** los cálculos se contrastan con un cálculo independiente y los drill-downs con tests cruzados y en navegador. Los casos límite de periodo vacío, parámetros no válidos, ID mal formado, error de API y token malformado tienen test.
- **Adherencia a la spec:** los 25 criterios están trazados en [VERIFY](VERIFY.md#matriz-de-trazabilidad). Se respeta el fuera de alcance: sin audio, sin persistencia, sin constructor de dashboards.
- **Simplicidad:** un módulo por responsabilidad (filtros, KPIs, identificadores, drill-down); sin abstracciones sin uso.
- **Seguridad (OWASP Top 10):**
  - control de acceso centralizado (`require_permission`) y verificado recorriendo todas las rutas;
  - HMAC con comparación en tiempo constante;
  - sin SQL ni `innerHTML`; React escapa el contenido y el resaltado escapa los términos de la regex;
  - CORS con orígenes explícitos;
  - `window.open` con `noopener`;
  - dependencias sin vulnerabilidades conocidas (`npm audit` y `pip-audit`);
  - mensajes de login que no revelan si el usuario existe.
- **Rendimiento:** menos de 500 ms por endpoint (con test), bundle principal de 397 kB y dashboard en diferido, datos previos visibles durante las recargas.
- **Conocimiento:** propósito, arquitectura, ADR-002 a ADR-004, registro de identificadores, patrones de interfaz, glosario, catálogo y lecciones al día; auditoría en verde.
