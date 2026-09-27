# Instrucciones del proyecto

## Vault de conocimiento

- Consulta `vault/Home.md` antes de asumir contexto relevante sobre producto, arquitectura, decisiones, ingeniería u operación.
- Busca por índice, título, tags y términos equivalentes antes de crear conocimiento nuevo.
- Trata las entradas `active` como vigentes; identifica explícitamente contenido `draft`, `deprecated` o `superseded`.
- Distingue hechos, decisiones e hipótesis y cita la ruta de cada entrada usada para justificar una afirmación.
- Usa `/vault capture` para conservar conocimiento reutilizable y `/vault audit` para validar el vault.
- No almacenes ni reproduzcas un secreto, credencial, token o dato personal innecesario.

## Documentación de features

- Toda la documentación de una feature (`spec.md`, `plan.md`, `VERIFY.md`, `REVIEW.md`, `SHIP.md`) vive en su propia carpeta dentro de `features/`.
- La carpeta se llama `FEXXX-descripcion-breve`:
  - `XXX` es un número incremental de tres dígitos: toma el mayor `FE` existente en `features/` y súmale uno. La primera feature es `FE001`.
  - La descripción resume la feature en 4 o 5 palabras, en `kebab-case`, minúsculas, sin tildes ni espacios.
  - Ejemplo: `features/FE001-transcripcion-de-llamadas-genesys/spec.md`.
- `/spec` crea la carpeta; el resto de fases escriben sus artefactos en esa misma carpeta. No reutilices ni renumeres un `FE` existente.

## Identificadores

- Todo identificador de entidad usa el formato `PREFIJO-UUID` en mayúsculas (por ejemplo `1CO-4B2E9A7F-3D1C-4A9B-8E5D-8F0A6C3E71AB`).
- Antes de crear una entidad nueva, consulta `vault/ingenieria/registro-de-identificadores.md`. Si su prefijo no existe, regístralo allí y en `backend/app/ids.py` en el mismo cambio.
- Genera y valida identificadores solo con `backend/app/ids.py`; nunca los construyas a mano.

## Skills

- Los skills del ciclo viven en `.devin/skills/<nombre>/SKILL.md`: `spec → plan → build → test → review → ship`, más `vault`.

## Verificación

- Ejecuta `python -m unittest discover -v` para correr las pruebas del proyecto cuando existan tests.
- Ejecuta `python scripts/audit_vault.py` para validar enlaces, metadatos, entradas huérfanas y posibles secretos. Un código distinto de `0` bloquea el avance.
