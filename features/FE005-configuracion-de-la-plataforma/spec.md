# FE005 — Configuración de la plataforma

> Estado: **pendiente de aprobación**. Depende de FE001.

## Objetivo

Centralizar la configuración funcional de la plataforma, de modo que sus cambios se reflejen en el resto de secciones.

## Criterios de aceptación

1. La sección **Configuración** tiene pestañas: General, Fuentes de datos, Taxonomía, KPIs y objetivos, Cumplimiento, Privacidad y Modelos de IA.
2. **General:** nombre de la plataforma, zona horaria e idioma por defecto. Cambiar la zona horaria cambia las fechas mostradas en el listado y en el detalle (test).
3. **Fuentes de datos:** muestra los conectores mock (Genesys Cloud voz transcrita y Genesys Cloud chat) con estado, última sincronización y nº de conversaciones. La acción «Sincronizar» simula una sincronización y actualiza la fecha.
4. **Taxonomía:** CRUD del catálogo de main topics bancarios (inicializado con el de FE001) y de los temas secundarios, con código, nombre, descripción y palabras clave. Un main topic nuevo aparece en los filtros de FE001 y FE002. Un main topic en uso no se puede borrar; solo desactivar (test).
5. **KPIs y objetivos:** por KPI, objetivo y umbrales verde, ámbar y rojo, además de si se muestra en cada dashboard. Las tarjetas de KPI de FE001 se colorean según esos umbrales, y cambiarlos cambia el color (test).
6. **Cumplimiento:** CRUD de checks de cumplimiento con nombre, descripción, frases esperadas y si aplica a voz, chat o ambos. Los checks activos son los que aparecen en el detalle y en el KPI de cumplimiento.
7. **Privacidad:** interruptor de enmascarado de PII (teléfonos, emails, DNI e IBAN detectados por patrones). Activado, el detalle muestra esos datos como `[TELÉFONO]`, etc. Hay un test con ejemplos de cada tipo.
8. **Modelos de IA:** proveedor y modelo por defecto (listas mock) que usará FE004, sin claves reales. La UI indica que la ejecución es simulada.
9. Cada cambio se valida en backend (Pydantic) y devuelve `422` con un mensaje por campo si es inválido; el front muestra el error junto al campo.
10. Solo `admin` puede modificar; el resto ve la configuración en solo lectura o no la ve, según su permiso. El backend devuelve `403` (test).
11. Cada cambio queda en un registro de auditoría (quién, cuándo, sección, valor anterior y nuevo) visible en la propia sección.

## Conocimiento afectado

- La nueva entrada de arquitectura de la plataforma debe incluir el modelo de configuración y su propagación.
- [Gobierno del vault](../../vault/Governance.md): su regla de no almacenar datos personales justifica el enmascarado; hay que enlazarla desde la entrada de arquitectura.
- [Estado operativo](../../vault/operaciones/estado-operativo.md): sigue en `draft`; se anota que los conectores son mock.

## Alcance

- API y UI de configuración de las siete pestañas, propagación a FE001–FE004, validación, permisos y registro de auditoría.

## Fuera de alcance

- Conexión real con Genesys Cloud (OAuth, APIs de grabación o transcripción).
- Persistencia entre reinicios del backend.
- Gestión de secretos o claves de proveedores de IA.
- Configuración por tenant o multi-organización.

## Riesgos y asunciones

- **Asunción:** la configuración es global a la plataforma, no por usuario.
- **Riesgo:** propagar cambios a otras secciones crea dependencias. Se mitiga con un único endpoint `GET /api/config` cacheado en el front e invalidado tras cada cambio.
