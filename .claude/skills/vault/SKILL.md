---
name: vault
description: "Inicializa, captura, consulta y audita el vault de conocimiento del proyecto."
argument-hint: "<init|capture|find|audit> [tema]"
---

# /vault — Gestión del conocimiento

Opera sobre el vault versionado del proyecto respetando `vault/Governance.md`. Determina la operación solicitada por el primer argumento. Si falta o no es válida, muestra las cuatro operaciones y pide elegir una; no asumas una operación destructiva.

## Reglas comunes

- Usa `vault/Home.md` como punto de entrada y consulta `vault/Governance.md` antes de modificar contenido.
- Busca por título, tags, términos equivalentes y enlaces antes de crear una entrada.
- Usa enlaces Markdown relativos y enlaza cada entrada desde el `Index.md` de su área.
- Distingue hechos confirmados, decisiones e hipótesis; no presentes una inferencia como hecho.
- Exige una fuente verificable y cítala en toda respuesta de consulta o captura.
- Nunca almacenes secretos, credenciales, tokens ni datos personales innecesarios.

## Operaciones

### `init`

1. Comprueba si existen `vault/Home.md`, `vault/README.md` y `vault/Governance.md`.
2. Si el vault ya está inicializado, informa de su estado y no sobrescribas contenido.
3. Si falta estructura, créala siguiendo la spec y las convenciones del repositorio.
4. Ejecuta `python scripts/audit_vault.py` y muestra el código de salida.

**Escenario `init`:** ejecutar `/vault init` sobre un repositorio que ya contiene el vault.

**Resultado `init`:** informa que está inicializado, no modifica archivos y devuelve la auditoría en verde.

### `capture`

1. Solicita o identifica `title`, `type`, propietario, área, resumen y fuente. No continúes si faltan `type`, fuente o propietario.
2. Busca duplicados por título, tags, sinónimos y contenido. Si existe una entrada canónica, actualízala en vez de crear otra.
3. Copia la plantilla correspondiente desde `vault/templates/`, completa el frontmatter y separa hecho, decisión e hipótesis.
4. Añade o actualiza la sección `## Fuentes` con enlaces verificables.
5. Enlaza la entrada desde el `Index.md` del área y actualiza `updated` en cualquier entrada modificada.
6. Ejecuta la auditoría y revierte la captura si introduce errores bloqueantes.

**Escenario `capture`:** ejecutar `/vault capture` con un concepto que ya está documentado y una fuente nueva.

**Resultado `capture`:** evita un duplicado, actualiza la entrada canónica y su `Index.md`, conserva la fuente y deja la auditoría en verde.

### `find`

1. Lee `vault/Home.md` y busca el tema por título, tags, contenido y términos equivalentes.
2. Prioriza entradas `active`; señala de forma explícita contenido `draft`, `deprecated` o `superseded`.
3. Reconcilia contradicciones usando fuentes y decisiones aceptadas. Si no hay evidencia suficiente, declara la incertidumbre.
4. Responde de forma concisa e incluye una cita mediante ruta o enlace para cada afirmación relevante.

**Escenario `find`:** ejecutar `/vault find arquitectura del harness`.

**Resultado `find`:** resume los componentes actuales y cita `vault/arquitectura/arquitectura-del-harness.md` sin inventar contexto ausente.

### `audit`

1. Ejecuta `python scripts/audit_vault.py` desde la raíz del repositorio.
2. Conserva y comunica el código de salida del comando.
3. Agrupa los hallazgos por severidad y archivo sin reproducir valores sensibles.
4. Si el código es distinto de cero, no declares el vault válido; propone corregir primero los errores bloqueantes.

**Escenario `audit`:** ejecutar `/vault audit` con un enlace roto en una entrada.

**Resultado `audit`:** devuelve código de salida distinto de cero, identifica el archivo y el tipo `broken-link`, y no declara la auditoría superada.

## Salida

Indica la operación ejecutada, archivos consultados o modificados, fuentes usadas y resultado de `python scripts/audit_vault.py` cuando la operación cambie o valide el vault.
