# FE005 — Revisión

> Fase `/review`. Fecha: 2026-09-29. Artefactos: [spec](spec.md) · [plan](plan.md) · [verificación](VERIFY.md). Siguiente paso: `/ship`.

## Resultado

**Aprobado.** No hay hallazgos critical ni major abiertos.

- **Resueltos en `/test`:** un major de privacidad (R1).
- **Resueltos en esta revisión:** un minor de corrección (R2) y una desviación de la spec, que queda documentada (R3).
- **Aceptados de forma justificada:** cinco minor.

## Tamaño del cambio

El diff desde `v0.4.0` ocupa 74 ficheros y unas 2.900 líneas, muy por encima de las ~100 recomendadas. Se entregó en commits atómicos: spec y plan, T1–T9 (T8 con su arreglo de test), la verificación y esta revisión. Cada uno lleva su evidencia de rojo a verde y sus mutaciones en el [plan](plan.md#progreso). `VERIFY.md` incluye la auditoría del vault en verde.

## Hallazgos

| # | Eje | Severidad | Hallazgo | Decisión |
|---|---|---|---|---|
| R1 | Seguridad / corrección | major | El enmascarado tomaba por DNI un número de 8 cifras seguido de «y», «a» o «e»: ocultaba datos que no eran personales, perdía una palabra y no validaba la letra de control que afirmaba el plan | **Resuelto en `/test`**: separador solo con guion y letra de control oficial; propiedad de 3.000 frases con 6 semillas y 4 falsos positivos fijos |
| R2 | Corrección | minor | Editar o borrar un tema o un check busca el elemento fuera del cerrojo y lo relee dentro. Si otro administrador lo borraba entre medias, `KeyError` → `500` | **Resuelto**: dentro del cerrojo, si ya no existe, `404`; 4 tests que simulan el borrado concurrente |
| R3 | Adherencia a la spec | minor | La spec preveía un único `GET /api/config`, pero exige `config:view` y la zona horaria y el nombre los necesitan todos los roles y el login | **Resuelto en T8 y documentado**: `GET /api/config/public` (solo nombre, zona e idioma) y `default_model` en el catálogo de flujos; anotado como desviación aceptada en la spec y en ADR-007 |
| R4 | Seguridad | minor | Un check por frases se evalúa sobre el texto original: quien tenga `config:edit` podría crear uno con un DNI como frase y deducir por el KPI si aparece en las conversaciones | **Aceptado**: solo `admin` tiene `config:edit` y puede desactivar el enmascarado igualmente; el cambio queda en la auditoría. Con roles editables (FE006) conviene revisarlo |
| R5 | Rendimiento | minor | Un dashboard pide el resumen dos veces: con `dashboard` (tarjetas) y sin él (reparto por canal y checks, que no deben depender de qué tarjetas se muestran) | **Aceptado**: unos 5 ms por petición medidos con uvicorn; separar los widgets de la configuración de tarjetas es más importante que ahorrar una petición |
| R6 | Simplicidad | minor | `routers/config.py` (unas 340 líneas) agrupa General, conectores, taxonomía, checks y KPIs, y el CRUD de temas y el de checks se parecen | **Aceptado**: cada sección es corta y comparte `_parse`, `apply_change` y los errores; partirlo en cinco routers o unificar temas y checks (con reglas de borrado distintas) añadiría indirección sin quitar lógica. A revisar si FE006 añade más secciones |
| R7 | Corrección | minor | `lib/format.ts` fija la zona horaria durante el render de `AppLayout` (efecto en el render) | **Aceptado**: es idempotente (doble render de StrictMode sin efecto) y hace que la primera pintada ya use la zona; la `key` del contenido lo vuelve a montar si la zona cambia. Alternativa descartada: un contexto que obligaría a convertir en hooks todos los formateadores |
| R8 | Conocimiento | minor | La configuración se pierde al reiniciar, y con dos administradores gana la última escritura | **Aceptado por la spec** (fuera de alcance: persistencia); documentado en arquitectura, ADR-007 y estado operativo |
| R9 | Corrección | nit | Deuda previa: 53–64 tests de FE001–FE003 dependen del dataset por defecto | **Fuera de alcance**: especificado y planificado como [FE009](../FE009-tests-independientes-del-dataset-mock/spec.md) |
| R13 | Corrección | minor | Durante la revisión, dos tests del explorador (FE002) fallaron una vez cada uno solo con la suite completa y la máquina cargada (media de carga de 6 a 9): `waitFor` esperaba como máximo 1 s y la consulta tiene un debounce de 300 ms. Aislados pasan siempre | **Mitigado**: `asyncUtilTimeout` a 3 s en `src/test/setup.ts` (espera el mismo estado con más margen, sin coste para los tests que pasan); 5 de 6 suites completas en verde después. Un fallo de 20 s no se pudo reproducir para ver su causa; queda anotado como fragilidad bajo carga |
| R10 | Seguridad | — | Permisos por ruta (`config:view` / `config:edit`), probados por rol y con el recorrido del OpenAPI; la ruta pública solo expone nombre, zona e idioma; `extra="forbid"` en todos los cuerpos (la configuración de IA no admite claves); longitudes y rangos limitados; fuzzing de 5.579 peticiones sin `5xx`; enmascarado al serializar sin tocar el dataset, e índice y prompts siempre enmascarados; entidades del análisis sin datos personales (importe, comercio, fecha, producto); React escapa todos los textos (sin `innerHTML`); auditoría atómica probada con 16 hilos | Correcto |
| R11 | Rendimiento | — | Cachés por instantánea de configuración (campos del explorador y cumplimiento efectivo); enmascarar el dataset añade 0,11 s al arranque; resumen con dos checks por frases, detalle y búsqueda por debajo de 500 ms (tests) y de 25 ms con uvicorn; `/configuracion` en diferido (27 kB), carga inicial de 312 a 314 kB | Correcto |
| R12 | Conocimiento | — | ADR-007 nuevo; ADR-005, ADR-006, arquitectura, registro de identificadores (`1TP`, `1TS`, `1CK`, `1CN`, `1AU`), catálogo, estado operativo, glosario, patrones de interfaz, lecciones 23–27 y READMEs actualizados; auditoría del vault con código 0 | Correcto |

## Revisión por ejes

- **Corrección:**
  - ver R1, R2, R7 y R9;
  - mutaciones detectadas en todas las tareas (del orden de 15 por tarea);
  - contrato de drill-down de cumplimiento tras cada tipo de cambio;
  - días en cuatro zonas horarias y en datasets que cruzan los cambios de hora.
- **Adherencia a la spec:** los 18 criterios están trazados en [VERIFY](VERIFY.md#matriz-de-trazabilidad). El fuera de alcance se respeta: sin Genesys real, sin persistencia, sin secretos, sin configuración por tenant o usuario, sin reclasificar conversaciones ni traducir la UI. Ver R3.
- **Simplicidad:** ver R6. La lectura en caliente se apoya en tres funciones (`topic_name`, `get_fields`, `effective_compliance`) y dos tests estructurales impiden saltársela. El front reutiliza el patrón de pestañas de FE004 y un único `useSectionForm`.
- **Seguridad:** ver R1, R4 y R10.
- **Rendimiento:** ver R5 y R11.
- **Conocimiento:** ver R8 y R12.
