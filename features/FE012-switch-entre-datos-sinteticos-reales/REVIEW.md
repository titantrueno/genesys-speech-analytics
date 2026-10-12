# FE012 — Revisión

> Fase `/review` (2026-10-12). Artefactos: [spec](spec.md) · [plan](plan.md) · [VERIFY](VERIFY.md). Siguiente paso: `/ship`.

## Resultado

**Aprobada, sin critical ni major abiertos.** Un hallazgo major (R1) se resolvió en la revisión; el resto son minor o nit aceptados con justificación.

**Alcance.** El diff desde `v0.8.0` es grande (la feature toca el repositorio de datos, 14 módulos de servicios y 6 secciones del front), así que no se propone partirlo: ya llegó en commits atómicos, uno por tarea del plan (T1–T9), más los de corrección y `/test`, cada uno con su suite en verde. `VERIFY.md` contiene la auditoría del vault en verde (código 0, 51 archivos).

## Hallazgos

| Id | Eje | Severidad | Hallazgo | Decisión |
|---|---|---|---|---|
| R1 | Corrección | **major** | `GET /api/search/similar/{id}` devolvía `500` (`KeyError` en el motor) para una conversación recién descargada: el índice anterior sigue sirviendo mientras se reconstruye y aún no la conoce. Reproducido con un test antes de corregir (`test_similar_for_a_conversation_the_serving_index_does_not_know_yet_is_empty_not_a_500`). | **Resuelto**: el router responde `200` con lista vacía si el índice que sirve no conoce la conversación. |
| R2 | Seguridad | minor | La API se conecta con el mismo usuario de PostgreSQL que el servicio de ingesta. La solo lectura se impone en la sesión (`default_transaction_read_only=on`, con test y mutación), no con un rol de base de datos. | **Aceptado** en este desarrollo (una sola base local). Para producción, un rol `SELECT` propio para la API; anotado en la arquitectura. |
| R3 | Rendimiento | minor | La instantánea carga todas las conversaciones con sus turnos en memoria y se recarga entera cuando llega una descarga. Medido con 1.000 conversaciones (< 500 ms en régimen estable); con decenas de miles crecería la memoria y el coste de cada recarga. | **Aceptado**: el volumen de la fase es el de un día de Genesys (13) a unos miles. La spec ya lo anticipaba como riesgo y ADR-005 documenta la reconstrucción; la solución a escala (consultas paginadas en SQL) queda para cuando el volumen la justifique. |
| R4 | Rendimiento | nit | Mientras se reconstruye el índice (unos 2,5 s con 1.000 conversaciones) las peticiones tardan más porque comparten procesador. | **Aceptado y documentado** en ADR-005. |
| R5 | Corrección | nit | `RealRepository` conserva la instantánea anterior si cambia la URL de la base, pero responde `503` en cuanto no puede comprobar el testigo (incluso con datos en memoria). | **Aceptado**: es lo que pide el criterio 3 (si PostgreSQL no responde, `503`). |
| R6 | Simplicidad | nit | `DataUnavailableBanner` y `DataUnavailable` conviven con los errores propios de cada sección, que en `503` seguirán diciendo «No se han podido cargar…» debajo del aviso. | **Aceptado**: el aviso único explica la causa y cómo salir; unificar los mensajes de cada sección sería una refactorización fuera de alcance. |
| R7 | Spec | nit | El criterio 15 pide recorrer en Chrome el chat con mensaje no entregado, el de reconexión y el rol `supervisor`; solo se hicieron con tests. | **Aceptado**: está anotado en `VERIFY.md` y los tests cubren su comportamiento (`ConversationDetailReal.test.tsx`, `DataOrigin.test.tsx`). |

## Ejes sin hallazgos

- **Adherencia a la spec:** los 15 criterios tienen evidencia (tabla de `VERIFY.md`) y se respeta el fuera de alcance: no hay análisis con LLM, ni dashboards nuevos, ni vistas mixtas, ni persistencia del origen (vuelve a `sintetico` al reiniciar).
- **Seguridad (OWASP):**
  - *Control de acceso:* el cambio de origen exige `config:edit`, y los datos reales exigen los mismos permisos que los sintéticos; el recorrido de `test_auth.py` incluye la ruta nueva.
  - *Inyección:* el SQL de la API no recibe entrada del usuario (lee tablas completas) y los filtros `phone` y `external_tag` se evalúan en memoria.
  - *Secretos:* la API lee `DATABASE_URL`, nunca `GENESYS_*` (test existente); los errores de conexión se reducen al nombre de la excepción y no llevan la URL.
  - *Datos personales:* texto y frases de temas enmascarados; ANI, DNIS y `externalTag` visibles por decisión explícita de la spec (ADR-007).
- **Conocimiento:** ADR-002, 005, 006 y 007, arquitectura, contrato de la API, patrones de interfaz, glosario, propósito y lecciones actualizados con enlaces a este plan; la auditoría del vault está en verde. La nota sobre un rol de solo lectura (R2) se añade a la arquitectura al cerrar la revisión.
