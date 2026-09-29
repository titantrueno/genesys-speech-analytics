# FE005 — Verificación

> Fase `/test`. Fecha: 2026-09-29. Artefactos: [spec](spec.md) · [plan](plan.md). Siguiente paso: `/review`.

## Resultado

**Verde.** Los 18 criterios tienen evidencia. La rutina de duda encontró un error real y una afirmación falsa en la documentación, y los dos quedan corregidos con regresión:

- **Error:** el enmascarado tomaba por DNI cualquier número de 8 cifras seguido de un espacio y de «y», «a» o «e», porque las tres son letras de DNI y el patrón aceptaba un espacio como separador sin validar la letra de control. «Expediente 20213570 y el 15/3/2026» pasaba a «expediente [DNI] el 15/3/2026»: perdía una palabra y ocultaba un dato que no era personal. Lo encontró una propiedad de 3.000 frases generadas: 372 fallos con la semilla 7, y 1.202 al añadir cuentas de 8 cifras. Ahora el DNI/NIE va pegado a su letra o con guion, y la letra de control debe cuadrar con el algoritmo oficial. Resultado: 0 fallos con 6 semillas.
- **Afirmación falsa:** el plan (T2), el glosario y el [ADR-007](../../vault/decisiones/adr-007-configuracion-global-y-enmascarado.md) decían «DNI/NIE con letra de control válida», pero el código no la validaba. Tras la corrección es cierto; el test de propiedad lo protege.

## Evidencia

| Comando o prueba | Resultado |
|---|---|
| `cd backend && .venv/bin/pytest` | **662 passed** (154 de FE005 en 5 ficheros, más los de FE001–FE004 adaptados) |
| `cd frontend && npm test` | **267 passed** (23 ficheros; 37 de FE005 en 3 ficheros) |
| `npm run lint` / `npm run build` | Código 0 / código 0 (por código de salida) |
| `python3 scripts/audit_vault.py` | Código 0: 42 archivos, 0 errores |
| `npm audit` / `pip-audit` | 0 vulnerabilidades |
| `./scripts/ci.sh` | **Código 0** |
| Fuzzing de las escrituras de configuración (6.000 cuerpos mutados con tipos erróneos, textos de 5.000 caracteres, `\u0000`, números extremos, campos desconocidos y cuerpos que no son objetos, en General, Privacidad, Modelos, KPIs, taxonomía, checks y borrados) | **0 respuestas `5xx`** en 5.579 peticiones (3.684 `422`, 1.129 `200/201`, 514 `409`, 168 `204`, 84 `404`; 421 cuerpos con `inf` no serializables). Todo `422` tiene `loc` y `msg`; lo aceptado se relee igual; **versión = entradas de auditoría (570)**; lecturas de métricas, catálogo, esquema, listado y catálogo de flujos en `200` después |
| Propiedad del enmascarado (3.000 frases con DNI/NIE válidos en 3 formatos, IBAN compacto o en grupos, teléfonos en 5 formatos, emails y tarjetas, junto a importes, fechas, horas, expedientes, referencias y cuentas de 8 cifras) | 0 fallos con las semillas 1, 2, 3, 7, 99 y 2026 (la 7 queda como test) |
| Concurrencia (16 hilos que crean temas a la vez con la ventana de la carrera ensanchada) | Ningún cambio ni entrada de auditoría perdidos; **falla si se quita el cerrojo** |
| Robustez frente al dataset (tests de FE005 con semilla y fecha 42/2026-09-27, 7/2026-11-10 y 123/2026-04-15, que cruzan los cambios de hora del 25 de octubre y el 29 de marzo, y 2026/2025-12-31) | Los 154 de FE005 pasan en las cuatro. Fallan 17–19 de `test_metrics.py` y `test_conversations.py` (FE001) por fechas absolutas; **fallan igual en `v0.4.0`**, así que es deuda previa (ver «Deuda encontrada»; en la suite completa son 53–64, de FE001 a FE003) |
| API real (uvicorn) | Configuración por defecto, resumen con estados verde/ámbar/`null`, detalle enmascarado con `started_at` en `+02:00`; configuración, resumen, detalle y búsqueda por debajo de 25 ms |
| Navegador | Recorrido del criterio 18 hecho por el usuario el 2026-09-29 con la lista de comprobación de T9 (en la sesión no había herramientas de Chrome) |

## Matriz de trazabilidad

| # | Criterio | Evidencia |
|---|---|---|
| 1 | API | `test_config_api.py` (lectura, versión, opciones, `404` de conector), rutas de taxonomía, checks y KPIs en sus ficheros |
| 2 | Validación con error por campo | Un test por pestaña: General (4 casos y todos a la vez), Modelos (2), KPIs (10), taxonomía (8), checks (8); fuzzing: todo `422` con `loc` y `msg` |
| 3 | Permisos | `admin` escribe; `supervisor` lee y recibe `403` en cada escritura sin cambiar nada; `analista` y `viewer` `403`; recorrido del OpenAPI en `test_auth.py` (la ruta pública, declarada) |
| 4 | Auditoría | Entrada por cambio con usuario, fecha, sección, elemento, antes y después; ninguna por `403`, `422`, `409` o sin cambios; filtro por sección; concurrencia; fuzzing (versión = entradas) |
| 5 | General | Nombre, zona IANA e idioma con errores; nombre en cabecera y login (front); zona horaria en listado, explorador, KPIs y series con 4 zonas; fechas en listado, detalle, búsqueda y flujos (front) y test estructural de formateo |
| 6 | Fuentes de datos | Conectores con nº de conversaciones por canal; «Sincronizar» actualiza la fecha sin cambiar el dataset y se audita |
| 7 | Taxonomía | `test_config_taxonomy.py` (26): catálogo inicial, crear y propagar a catálogo, explorador y Sampling, renombrar, código inmutable, `409` en uso, desactivar sin cambiar KPIs ni drill-down, intérprete, temas secundarios y test estructural |
| 8 | KPIs y objetivos | `test_config_kpis_timezone.py`: estados al mover umbrales, igualdad al umbral, incoherencia, rangos, dashboards; front: color, objetivo, KPIs ocultos y añadidos |
| 9 | Cumplimiento | `test_config_compliance.py` (25): evaluación por frases contra el análisis en 60 conversaciones, solo turnos del agente, canal, desactivar, `409` de los de FE001 y **contrato de drill-down** tras cada tipo de cambio |
| 10 | Privacidad | `test_privacy.py` (43): cada tipo, falsos positivos, propiedad de 3.000 frases, dataset completo sin falsos positivos, API sin datos personales, índice y prompts siempre enmascarados, rendimiento |
| 11 | Modelos de IA | Validación contra el proveedor, sin campos de secretos; `default_model` en el catálogo de flujos; Prompt nuevo con ese modelo (front); aviso de ejecución simulada |
| 12 | Sección y pestañas | `ConfigPage.test.tsx`: siete pestañas, URL, flechas, carga y error |
| 13 | Error junto al campo | `aria-describedby` y `aria-invalid` con el mensaje del `422`, conservando lo escrito (General, taxonomía y KPIs) |
| 14 | Confirmación | Desactivar y borrar temas y checks; «Borrar» no se ofrece en temas en uso ni en checks del análisis |
| 15 | Auditoría en cada pestaña | Registro por sección y «Sin cambios registrados» |
| 16 | Propagación sin recargar | Main topic creado en Configuración visible en el filtro de un dashboard ya visitado (invalidación de todas las consultas) |
| 17 | CI y rendimiento | `./scripts/ci.sh` con código 0; tests de 500 ms para detalle, búsqueda y resumen con checks por frases |
| 18 | Navegador | Recorrido del usuario (ver el [plan](plan.md#progreso)) |

## Fundamentación

| Decisión | Fuente |
|---|---|
| Letra de control del DNI y del NIE (X, Y, Z = 0, 1, 2) | [Ministerio del Interior · Cálculo del dígito de control del NIF-NIE](https://www.interior.gob.es/opencms/es/servicios-al-ciudadano/tramites-y-gestiones/dni/calculo-del-digito-de-control-del-nif-nie/) |
| Zonas IANA y conversión con `zoneinfo` | [Python · zoneinfo](https://docs.python.org/3/library/zoneinfo.html) |
| Errores por campo (`loc`, `msg`) y `ValidationError.from_exception_data` | [Pydantic · Validation errors](https://docs.pydantic.dev/latest/errors/validation_errors/) y [FastAPI · Handling errors](https://fastapi.tiangolo.com/tutorial/handling-errors/) |
| `extra="forbid"` y `StringConstraints` | [Pydantic · Models](https://docs.pydantic.dev/latest/concepts/models/) y [Pydantic · Types](https://docs.pydantic.dev/latest/api/types/) |
| Invalidar todas las consultas al guardar | [TanStack Query · Query invalidation](https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation) |
| Zona horaria al formatear | [MDN · Intl.DateTimeFormat (`timeZone`)](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/DateTimeFormat/DateTimeFormat) |
| Test estructural con `import.meta.glob` y `?raw` | [Vite · Glob import](https://vite.dev/guide/features#glob-import) |
| Pestañas accesibles | [WAI-ARIA APG · Tabs](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/) |
| Error de campo accesible | [MDN · aria-invalid](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Attributes/aria-invalid) y [MDN · aria-describedby](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Attributes/aria-describedby) |

## Registro de duda

| Afirmación | Duda | Reconciliación | Conclusión |
|---|---|---|---|
| El enmascarado no tiene falsos positivos | ¿Solo en el dataset, que nunca pone un número de 8 cifras antes de «y»? | Propiedad con datos generados junto a textos seguros | **Bug corregido**: separador y letra de control; 0 fallos con 6 semillas |
| Se valida la letra de control | Lo dice el plan; ¿lo hace el código? | Lectura del patrón: no la validaba | **Documentación falsa**, ahora cierta y protegida por test |
| Ningún cambio aceptado queda sin auditar | ¿Con escrituras concurrentes? | 16 hilos con la ventana ensanchada; sin cerrojo, falla | Se cumple |
| Las escrituras nunca dan `500` | ¿Solo con los casos de los tests? | Fuzzing de 5.579 peticiones | Se cumple (0 `5xx`) |
| Los días se calculan bien en cualquier zona | ¿Y en los cambios de hora? | Datasets que cruzan el 29 de marzo y el 25 de octubre, con 4 zonas | Se cumple |
| Los tests de FE005 no dependen del dataset | Semilla 42 y fecha fija | 4 combinaciones: los 154 pasan | Se cumple; los de FE001 no (deuda previa) |
| El drill-down de cumplimiento cuadra con checks por frases | ¿Tras editar y desactivar? | `compliant=true` + `false` = volumen y el % coincide, tras cada tipo de cambio | Se cumple |
| Un check por frases replica al del análisis | ¿O solo lo parece? | Réplica de «saludo» igual al análisis en 60 conversaciones de voz | Se cumple (aproximación léxica; ver ADR-007) |
| Todos los roles ven la zona y el nombre | `GET /api/config` exige `config:view` | Encontrado en T8 | **Cambio de diseño**: ruta pública mínima |
| El front aplica la zona en todas las fechas | Había formateadores sueltos | Test estructural sobre el código fuente | Se cumple |

## Bugs encontrados

| Bug | Causa raíz | Regresión |
|---|---|---|
| Falso DNI en «20213570 y» (y cualquier número de 8 cifras + «y/a/e») | Espacio aceptado como separador y sin validar la letra de control | 4 falsos positivos fijos, `test_property_generated_personal_data_is_masked_and_nothing_else` y el NIE con su letra real |
| Commit de T8 con el gate en rojo | Commit encadenado a un `grep`, no al código de salida de `ci.sh` | Lección 24; desde entonces, commit solo si `ci.sh` termina con código 0 |
| Test intermitente de drill-down (FE001) al añadir una petición | Buscaba el enlace antes de los datos | `findByRole`; 10/10 y 3 suites completas |
| Zona y nombre invisibles sin `config:view` (T8) | La spec daba por hecho un solo `GET /api/config` | Ruta pública y 2 tests |

## Deuda encontrada (fuera de alcance)

- **Tests atados al dataset por defecto:** con otra semilla o fecha de referencia fallan entre 53 y 64 tests del backend de FE001, FE002 y FE003 (fechas absolutas, datasets propios con semilla 42 y hechos de una semilla), igual en `v0.4.0`. Queda especificado como [FE009 — Tests independientes del dataset mock](../FE009-tests-independientes-del-dataset-mock/spec.md).
