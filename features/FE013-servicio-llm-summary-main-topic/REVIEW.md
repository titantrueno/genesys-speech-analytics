# FE013 — Revisión

> Fase `/review`. Spec: [spec.md](spec.md) · Plan: [plan.md](plan.md) · Verificación: [VERIFY.md](VERIFY.md). Siguiente paso: `/ship`.

## Veredicto

**Aprobada.** Tres hallazgos **major**, resueltos en esta fase con su test; ningún critical. Los minor y nits quedan resueltos o aceptados con su justificación.

## Alcance y tamaño

- 13 commits desde `33b83d3`, unas 1.940 líneas de código de producción (más tests, OpenAPI y vault). Supera con mucho las ~100 líneas revisables: no se puede partir a posteriori, así que se revisó **por tarea**, un commit cada vez (T1–T9 y `/test`), con la lógica crítica delante: proveedores, runner, ejecutor, reglas, escritura, carga y lectura.
- **Evidencia previa:** [VERIFY.md](VERIFY.md) existe y está al día: auditoría del vault con código 0 (54 archivos, 0 errores), gate con código 0, 30 de 30 mutaciones detectadas y trazabilidad de los 31 criterios.

## Hallazgos

### Corrección

| # | Sev. | Hallazgo | Decisión |
|---|---|---|---|
| C1 | **major** | La API esperaba como mucho 90 s cada `/complete`, pero el servicio puede tardar 3 intentos de hasta 60 s más las esperas (~181 s) y además encolar por `LLM_MAX_CONCURRENCY`. Ante un proveedor lento, la API cortaba y el nodo se detenía con «El servicio de LLM no está disponible»: diagnóstico falso. | **Resuelto:** `COMPLETE_TIMEOUT_S = 240` (`app/llm_client.py`) y test que liga el valor al peor caso del servicio (`test_the_api_waits_longer_than_the_service_worst_case`). Nota en el [runbook](../../vault/operaciones/runbook-servicio-llm.md). |
| C2 | minor | `FlowExecutor` sin escritor fallaba un Output «campo» con «Error inesperado: 'NoneType'…». Solo el router lo construye y siempre pasa el escritor, pero el mensaje no ayudaría. | **Resuelto:** `NodeFailure` «No hay dónde guardar los campos: falta el servicio de ingesta.» y test. |
| C3 | minor | Si un nodo Prompt se detiene (servicio caído, clave rechazada), las llamadas ya en curso del pool terminan; solo se cancelan las pendientes. | **Aceptado:** como mucho 3 llamadas más; la cancelación de ejecuciones está fuera de alcance (spec). |
| C4 | minor | El catálogo de flujos se cachea sin caducidad en el front; si otra persona cambia el origen de datos, el editor no lo ve hasta recargar. | **Aceptado:** guardar la configuración invalida todas las consultas en la sesión que la cambia, y la validación del backend sigue bloqueando la ejecución. |

### Adherencia a la spec

| # | Sev. | Hallazgo | Decisión |
|---|---|---|---|
| S1 | — | Criterios 1–31 con evidencia ([VERIFY.md](VERIFY.md)). Cambios de la spec durante la implementación registrados en ella: una llamada para los dos campos (criterio 16), `llm_meta` como columna de trazabilidad (20) y plantillas sin fechas (23). | Conforme. |
| S2 | — | Fuera de alcance respetado: la ingesta no analiza con el LLM, no hay gestión de claves en la interfaz, ni control de coste, ni cancelación, ni escritura en datos sintéticos. | Conforme. |
| S3 | nit | La spec pedía columnas de trazabilidad «nuevas» en plural; se usó una sola columna `jsonb` por campo. | **Aceptado:** cubre los mismos datos y escala a más campos; anotado en el criterio 20 y en ADR-009. |

### Simplicidad

| # | Sev. | Hallazgo | Decisión |
|---|---|---|---|
| P1 | minor | `llm/security.py` duplica las 15 líneas de `ingestion/security.py`. | **Aceptado:** el test estructural prohíbe que los servicios se importen entre sí y que `app` aloje código de servicios; copiar es más simple que crear un paquete compartido. |
| P2 | nit | Un test usaba `__import__("app.flows.rules", …)` en vez de importar `validate`. | **Resuelto.** |
| P3 | — | Interfaz de proveedores pequeña (`build` + `parse`, errores comunes en `HttpProvider`); añadir un proveedor es una clase y una línea del registro. | Conforme. |

### Seguridad (OWASP Top 10)

| # | Sev. | Hallazgo | Decisión |
|---|---|---|---|
| X1 | **major** | Un Prompt **Simulado** conectado a «Guardar en campos» escribía resultados simulados en conversaciones reales sin avisar: integridad de datos (A04, diseño inseguro). | **Resuelto:** aviso `simulated_values_to_real_data` (no bloquea, porque sirve para probar la cadena sin clave) y test. La trazabilidad `llm_meta` ya registraba `provider: simulado`. |
| X2 | minor | `GET /health` del servicio de LLM no exige token y dice qué proveedores tienen clave (sí/no). | **Aceptado:** nunca devuelve la clave; es la misma información que Configuración → Modelos de IA; uvicorn escucha en `127.0.0.1`. |
| X3 | — | Secretos: lista blanca por proceso, `repr` sin claves, la clave de Gemini va en cabecera y nunca en la URL, los errores no repiten el cuerpo del proveedor, logs sin prompt, respuesta ni claves (tests con clave ficticia y revisión de los logs reales). | Conforme. |
| X4 | — | Inyección: el modelo de Gemini va en la URL y está acotado por patrón (`../../v1/files` da `422`); los nombres de columna de la escritura salen de una lista blanca; todo el SQL va parametrizado. | Conforme. |
| X5 | — | Control de acceso: «Probar» (llamada de pago) exige `config:edit`; ejecutar exige `flows:edit`; el servicio de LLM y `/analysis/fields` exigen token interno con comparación en tiempo constante. | Conforme. |
| X6 | minor | Inyección de instrucciones en la transcripción. | **Aceptado:** el resultado solo se guarda tras validarlo (main topic acotado a la taxonomía), el summary se pinta escapado por React y el LLM no tiene herramientas. Las transcripciones salen enmascaradas (ADR-007). |
| X7 | — | Validación de entrada: `POST /analysis/fields` rechaza lotes de más de 100, valores vacíos y campos fuera de la lista blanca (resuelto en `/test`). | Conforme. |

### Rendimiento

| # | Sev. | Hallazgo | Decisión |
|---|---|---|---|
| R1 | minor | El paralelismo de la API (4 por nodo) es fijo aunque `LLM_MAX_CONCURRENCY` se configure más bajo: las llamadas sobrantes esperan en el servicio. | **Aceptado** con C1 (la API espera lo suficiente) y documentado en el runbook. |
| R2 | — | Medido en Gemini real: 3 conversaciones en 2 s con 4 llamadas en paralelo. La validación consulta `/health` una sola vez por validación y solo si algún Prompt usa un proveedor real. | Conforme. |

### Conocimiento

| # | Sev. | Hallazgo | Decisión |
|---|---|---|---|
| K1 | **major** | La sección «Flujos de insights (FE004)» de la arquitectura seguía diciendo que el Prompt tiene «modelo mock»: podía inducir a creer que no hay LLM real. | **Resuelto.** |
| K2 | — | ADR-009 y runbook nuevos; ampliaciones de ADR-006, 007 y 008 (también la migración `0005`); contrato de la API (72 operaciones), estado operativo, primeros pasos, runbook de la ingesta, README y lecciones 45–47; todo con fuentes y enlazado desde sus índices. Hipótesis explícitas: adaptadores de OpenAI y Anthropic sin probar contra sus APIs. | Conforme. |

## Gate

- Sin hallazgos critical ni major abiertos.
- `python scripts/audit_vault.py`: código 0 (54 archivos, 0 errores).
- `./scripts/ci.sh`: código 0 tras las correcciones (ver el commit de esta revisión).
