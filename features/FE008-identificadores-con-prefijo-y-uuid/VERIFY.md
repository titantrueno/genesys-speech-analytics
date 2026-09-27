# FE008 — Verificación

> Fase `/test`. Fecha: 2026-09-27. Artefactos: [spec](spec.md) · [plan](plan.md). La evidencia global (suites, auditorías, prueba de humo) está en [FE001/VERIFY](../FE001-base-dashboards-y-detalle-conversaciones/VERIFY.md#evidencia).

## Resultado

**Verde.** Los 11 criterios tienen evidencia. La verificación de las fuentes obligó a corregir la referencia normativa: RFC 4122 → RFC 9562.

## Matriz de trazabilidad

| # | Criterio | Evidencia |
|---|---|---|
| 1 | Módulo único y sin identificadores construidos a mano | `test_ids.py` (6 tests); `test_no_hand_built_legacy_identifiers_in_code` |
| 2 | `1CO` v4, únicos, deterministas y sin cambiar el contenido | `test_size_ids_and_date_range`, `test_generation_is_deterministic`, `test_content_is_unchanged_by_the_identifier_format` (huella previa a FE008) |
| 3 | `1CU` y FCR intacto | `test_size_ids_and_date_range`; `fcr_rate` en `test_summary_matches_independent_calculation` |
| 4 | `1US` v5 en login, `/me` y `sub` | `test_login_with_valid_credentials_returns_token_and_user`; los tests de token siguen en verde |
| 5 | Agentes y colas con identificador en modelo, catálogo, filtros y desgloses | `test_agents_and_queues_have_stable_ids`, `test_catalog_lists_filter_values`, `test_breakdown_sums_to_total_and_matches[queue\|agent]`, `test_invalid_parameters_return_422` (nombres → 422) |
| 6 | Cruces listado = desglose | `test_list_total_equals_breakdown_volume` × 4 dimensiones |
| 7 | Detalle sin distinguir mayúsculas; 404 si está mal formado | `test_detail_accepts_lowercase_id`, `test_detail_unknown_or_malformed_id_returns_404` × 4 |
| 8 | Prefijos del código = registro del vault | `test_prefixes_match_vault_registry` |
| 9 | Identificador abreviado en el listado y completo en el detalle | «muestra el identificador abreviado y el completo al pasar el ratón»; Chrome: h1 con el identificador completo |
| 10 | Nombres en controles y chips, identificadores en la URL | «los chips de cola y agente muestran el nombre…», «al montar con filtros en la URL…» |
| 11 | Drill-down exacto en navegador | Chrome 7/7 con los mismos valores que antes de FE008, más el drill-down por cola (57 = 57) |

## Fundamentación

| Decisión | Fuente |
|---|---|
| Versión 4 (aleatoria), versión 5 (SHA-1 de namespace + nombre), variante `0b10` | [RFC 9562](https://www.rfc-editor.org/rfc/rfc9562), que sustituye a RFC 4122 |
| `uuid.UUID(int=…, version=4)` fija los bits de versión y variante; `uuid5` | [Python · uuid](https://docs.python.org/3/library/uuid.html) |
| El prefijo va separado porque O, U y S no son hexadecimales | RFC 9562 (representación en dígitos hexadecimales); [ADR-004](../../vault/decisiones/adr-004-identificadores-con-prefijo-y-uuid.md) |

## Registro de duda

| Afirmación | Duda | Reconciliación | Conclusión |
|---|---|---|---|
| Cambiar los identificadores no altera los datos | Generar UUID consume el generador aleatorio | Se usa un generador independiente; huella idéntica y drill-downs con los mismos valores | Se cumple |
| La norma es RFC 4122 | ¿Sigue vigente? | La documentación de Python remite a RFC 9562, que declara obsoleta la RFC 4122 | Referencias corregidas en el vault y en la spec |
| Un enlace antiguo con nombres de cola sigue funcionando | La API ahora exige identificadores | Devuelve 422 y, tras la corrección de FE001, el front muestra un aviso en lugar de quedarse cargando | Se cumple; enlaces antiguos no soportados, según la spec |
