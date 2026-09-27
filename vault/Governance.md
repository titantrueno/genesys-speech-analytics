# Gobierno del vault

[Volver al inicio](Home.md)

## Esquema de metadatos

Todas las entradas, salvo `Home.md`, `README.md`, los índices y las plantillas, comienzan con frontmatter YAML.

| Campo | Regla |
|---|---|
| `title` | Título humano, único dentro de su área. |
| `type` | Uno de: knowledge, adr, runbook, delivery, lesson, artifact. |
| `status` | Uno de: draft, active, deprecated, superseded. |
| `owners` | Lista con al menos una persona, equipo o rol responsable. |
| `tags` | Lista corta de términos en minúsculas. |
| `created` | Fecha de creación en formato `YYYY-MM-DD`. |
| `updated` | Fecha de última revisión en formato `YYYY-MM-DD`. |

## Nombres y ubicación

- Usa nombres de archivo descriptivos en `kebab-case.md`, sin tildes ni espacios.
- Guarda cada entrada en el área que mejor represente su propósito principal y enlázala desde su `Index.md`.
- Antes de crear una entrada, busca por título, tags y conceptos equivalentes para evitar duplicados.
- Mantén una sola fuente canónica y enlázala desde las demás áreas cuando un tema sea transversal.

## Fuentes y trazabilidad

- Cada entrada incluye una sección `Fuentes` con enlaces a archivos, documentación oficial, issues, PRs u otra evidencia.
- Separa un **hecho** confirmado de una **decisión** adoptada y de una **hipótesis** pendiente de validar.
- Una decisión aceptada registra contexto, alternativas y consecuencias.
- Los artefactos temporales enlazan la spec, el plan, la verificación, la review y la entrega relacionadas cuando existan.

## Ciclo de vida

- `draft`: contenido incompleto que todavía no debe tratarse como fuente definitiva.
- `active`: conocimiento vigente y respaldado por evidencia.
- `deprecated`: contenido obsoleto conservado por valor histórico; debe enlazar su reemplazo o explicar por qué ya no aplica.
- `superseded`: contenido sustituido por otra entrada; ambas deben enlazarse.
- Al revisar una entrada, actualiza `updated` aunque la conclusión sea que sigue vigente.
- No borres historia útil para ocultar cambios de criterio.

## Contradicciones

Cuando aparezca una contradicción, no elijas una versión por intuición. Marca ambas entradas, reúne evidencia, identifica al propietario y crea o actualiza una decisión que establezca la fuente vigente. Después enlaza la resolución desde el contenido obsoleto.

## Seguridad

- Nunca almacenes un secreto, credencial, token, clave privada o contraseña.
- No incluyas un dato personal salvo que sea imprescindible y esté autorizado.
- Usa referencias al gestor seguro correspondiente en lugar de copiar valores sensibles.
- Si detectas información sensible, detén la captura, informa solo la ubicación y evita reproducir el valor.

## Plantillas

Las plantillas disponibles se describen en [templates/README.md](templates/README.md). Copia la adecuada, sustituye los marcadores y enlaza la nueva entrada desde el índice de su área.
