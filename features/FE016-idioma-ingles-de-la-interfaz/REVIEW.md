# FE016 — Review

> Fase `/review`, 2026-10-13. Spec: [spec.md](spec.md). Verificación: [VERIFY.md](VERIFY.md). Siguiente paso: `/ship`.

## Alcance del cambio

El diff completo es grande (214 archivos, unas 6.500 líneas añadidas) porque migra toda la interfaz y todos los mensajes de la API. Ya llegó partido en diez commits revisables, uno por tarea (T1 a T9 y `/test`), cada uno con el gate en verde:

| Commit | Contenido |
|---|---|
| `251d530` | Spec, plan y `en-US` en el backend (T1) |
| `a403c96`, `b8dcc6a` | Capa i18n, login y navegación; idioma solo en Configuración (T2) |
| `172b9b9` | Dashboards y conversaciones (T3) |
| `b168332` | Replanteo: la API solo en inglés |
| `66ed258` | Explorador y búsqueda (T4) |
| `5083ab6` | Flujos de insights (T5) |
| `0492288` | Descargas de Genesys y usuarios (T6) |
| `05fb352` | Configuración (T7) |
| `2203596` | API solo en inglés (T8) |
| `6e13354`, `eba7022` | Vault, ADR-010 y `/test` (T9) |

## Evidencia comprobada

- `VERIFY.md` existe, contiene la auditoría del vault en verde (`audit_vault.py`, código 0) y está al día; se le añadió una nota de actualización.
- Tras las correcciones de esta review: `./scripts/ci.sh` termina con código 0 (572 tests de front, 1.159 + 192 de backend, OpenAPI al día y válido, vault sin errores).

## Hallazgos por eje

Severidades: critical / major / minor / nit. No hay hallazgos critical.

### Corrección

| # | Severidad | Hallazgo | Decisión |
|---|---|---|---|
| C1 | minor | `translate` y `tOr` resolvían claves con `in` y con el índice del objeto: una clave como `constructor` o `__proto__` se habría tomado por una traducción (los textos reales llevan prefijo, por eso no ocurría) | **Resuelto:** `Object.hasOwn` en `translate.ts`, `context.ts` e `I18nProvider.tsx`, con test nuevo que falló sin la corrección y pasa con ella |
| C2 | nit | Clave `cfg.tax.title` sin uso (la pestaña usa `cfg.tab.taxonomia`) | **Resuelto:** eliminada de `es` y `en` |
| C3 | nit | Condición redundante al buscar las llamadas `log` de ingesta en `test_api_messages_english.py` | **Resuelto:** simplificada |
| C4 | minor | Al cambiar el idioma se vuelve a montar el contenido de la página (se pierde el estado local, como ya ocurre al cambiar la zona horaria) | **Aceptado:** es lo buscado; un cambio de idioma afecta a todos los textos |
| C5 | minor | Los datos en español (transcripciones, resúmenes, palabras clave) dentro de una interfaz inglesa no llevan `lang="es"` (WCAG 3.1.2): un lector de pantalla los leería con la voz del idioma de la página | **Aceptado, documentado:** límite recogido en ADR-010 como mejora futura |

Revisado sin hallazgos: la sustitución masiva de nombres de etapa en `ingestion/runs.py` (solo toca las llamadas a `log`, `step` y `on_step`, comprobado en el diff); los textos de `GenesysClient` siguen pasando por `redact`; las claves dinámicas (`exp.value.<campo>.<valor>`, `kpi.<código>.label`) llevan siempre prefijo.

### Adherencia a la spec

| # | Severidad | Hallazgo | Decisión |
|---|---|---|---|
| S1 | — | Los 15 criterios tienen evidencia (tabla de `VERIFY.md`); se respeta el fuera de alcance (sin idioma por persona, sin `Accept-Language`, sin traducir datos) | Conforme |
| S2 | minor | La spec cambió durante la construcción por decisión de la persona usuaria (se retiró el selector personal y la API pasó a solo inglés) | **Aceptado:** ambos cambios están en la spec, el plan y ADR-010 con su fecha; el criterio 3 y el 12 a 13 ya no describen lo antiguo |

### Simplicidad

| # | Severidad | Hallazgo | Decisión |
|---|---|---|---|
| Sm1 | nit | Cerca de 1.100 claves planas por idioma en nueve archivos por idioma | **Aceptado:** el diccionario plano con prefijo por área es lo más simple que cumple paridad tipada y no añade dependencias; la alternativa (librería de i18n) se descartó en el ADR |
| Sm2 | nit | Los diccionarios se generaron con un script temporal que no está en el repositorio | **Aceptado:** no es parte del producto; los archivos generados son TypeScript normal, mantenidos a mano |

### Seguridad (OWASP Top 10)

| # | Severidad | Hallazgo | Decisión |
|---|---|---|---|
| Sec1 | — | Inyección: la interpolación de parámetros usa una función de reemplazo (sin patrones `$`) y React escapa lo que se muestra; no hay HTML ni `dangerouslySetInnerHTML` nuevos | Conforme |
| Sec2 | — | Control de acceso: no hay rutas nuevas; el idioma se guarda con `config:edit` como el resto de General; `GET /api/config/public` sigue exponiendo solo nombre, zona horaria e idioma | Conforme |
| Sec3 | — | Secretos y datos sensibles: los mensajes traducidos conservan la redacción de secretos (`redact`) y el test del servicio de ingesta comprueba que no aparecen tokens ni URLs firmadas | Conforme |
| Sec4 | nit | `Missing permission config:view` revela el nombre del permiso que falta | **Aceptado:** ya ocurría con el texto en español y los permisos son públicos en el contrato |

### Rendimiento

| # | Severidad | Hallazgo | Decisión |
|---|---|---|---|
| P1 | minor | Los dos diccionarios entran juntos en la carga inicial: +135 kB (unos 40 kB comprimidos) sobre los 440 kB del paquete principal (medido con `npm run build`) | **Aceptado, documentado:** cargar `en` bajo demanda ahorraría la mitad a costa de un estado de carga y de parpadeo en el login; con dos idiomas no compensa. El coste está en ADR-010 y en la arquitectura |
| P2 | — | `t` se recrea solo al cambiar de idioma y los formateadores `Intl` se cachean por idioma | Conforme |

### Conocimiento

| # | Severidad | Hallazgo | Decisión |
|---|---|---|---|
| K1 | **major** | La arquitectura afirmaba una carga inicial de unos 448 kB: tras FE016 son unos 575 kB; habría inducido a una decisión de rendimiento equivocada | **Resuelto:** cifra y causa actualizadas en `arquitectura-de-la-plataforma.md` |
| K2 | minor | El README no decía cómo probar el inglés en local con `--no-db` (guardar el idioma da 503 con el token del `.env`) | **Resuelto:** nota en el README; también en el estado operativo y en ADR-010 |
| K3 | minor | ADR-010 no recogía el límite de accesibilidad ni el coste en tamaño | **Resuelto:** añadidos a sus consecuencias |
| K4 | — | ADR-010, arquitectura, patrones de interfaz, contrato de la API, estado operativo y lecciones enlazados desde sus índices; auditoría del vault en verde | Conforme |

## Resumen

- Resueltos: C1, C2, C3, K1, K2, K3 (el único **major**, K1, ya corregido).
- Aceptados con justificación: C4, C5, S2, Sm1, Sm2, Sec4, P1.
- Sin hallazgos critical ni major abiertos; el gate está en verde.
