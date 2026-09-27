# Vault de conocimiento

Este directorio es la fuente de conocimiento versionada del proyecto para el equipo y los agentes de IA. El punto de entrada es [Home.md](Home.md).

## Uso sin Obsidian

Todo el contenido usa Markdown estándar y puede recorrerse desde `Home.md` con cualquier editor o visor de repositorios.

## Uso con Obsidian

1. En Obsidian, selecciona **Open folder as vault**.
2. Abre el directorio `vault/`.
3. Empieza la navegación en `Home.md`.

La configuración personal de Obsidian no forma parte del proyecto.

## Convención de enlaces

Los enlaces internos usan exclusivamente Markdown con rutas relativas y extensión explícita: `[texto](ruta/relativa.md)`.

- La ruta se calcula desde el archivo que contiene el enlace.
- El nombre debe respetar mayúsculas y minúsculas del archivo de destino.
- Cada área se descubre desde `Home.md` y mantiene un `Index.md` propio.
- No se usan wikilinks como `[[Nota]]`, para que el vault siga siendo navegable fuera de Obsidian.

## Reglas iniciales

- Consulta el índice del área antes de crear contenido nuevo.
- Mantén los índices enlazados y evita documentos huérfanos.
- No almacenes secretos, credenciales ni datos sensibles.
