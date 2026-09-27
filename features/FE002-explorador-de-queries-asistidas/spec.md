# FE002 — Explorador de queries asistidas

> Estado: **pendiente de aprobación** (revisada el 2026-09-27 tras la entrega de `v0.1.0`). Depende de FE001, FE007 y FE008.

## Objetivo

Permitir filtrar en tiempo real las conversaciones de un intervalo mediante un constructor de consultas asistido (visual y en lenguaje natural), con recuento, KPIs y listado que se actualizan al instante.

## Modelo de consulta

```json
{
  "from": "2026-09-01",
  "to": "2026-09-26",
  "root": {
    "op": "and",
    "conditions": [
      { "field": "channel", "operator": "is", "value": "chat" },
      { "op": "or", "conditions": [
        { "field": "sentiment", "operator": "lt", "value": -0.3 },
        { "field": "resolution", "operator": "is", "value": "escalada" }
      ]}
    ]
  }
}
```

- Un grupo (`and` / `or`) contiene condiciones o grupos, con un máximo de **2 niveles** de anidamiento.
- El intervalo es obligatorio. Por defecto son los últimos 30 días hasta la fecha de referencia del backend.

## Campos y operadores

| Tipo | Campos | Operadores |
|---|---|---|
| Categórico | canal, cola (`1QU-…`), agente (`1AG-…`), main topic, tema secundario, resolución, riesgo de abandono | `is`, `is_not`, `in`, `not_in` |
| Numérico | sentimiento (-1..1), CSAT predicho (1–5), esfuerzo (1–5), duración (s), nº de turnos | `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `between` |
| Check de cumplimiento | uno por check (saludo, verificación de identidad…) | `passes`, `fails`, `not_applicable` |
| Texto | summary; transcripción (opcionalmente limitada a un hablante: cliente, agente o bot) | `contains`, `not_contains` (sin distinguir mayúsculas ni tildes) |
| Booleano | recontacto en 7 días | `is` |

## Criterios de aceptación

### Backend

1. `GET /api/query/schema` devuelve los campos con tipo, etiqueta, operadores válidos y, en los categóricos, los valores posibles con etiqueta. Cola y agente muestran el nombre y guardan el identificador.
2. `POST /api/query/run` valida la consulta y devuelve `422` con un mensaje por condición si un campo, operador o valor no es válido (incluidos identificadores de otro tipo o más de 2 niveles de anidamiento). En caso contrario devuelve el total, los 13 KPIs de FE001 sobre el subconjunto y una página del listado (25, con el orden de FE001).
3. Cada operador de cada tipo y la combinación `and`/`or` con anidamiento dan el mismo resultado que un filtrado independiente del dataset escrito en el test.
4. `GET /api/query/suggest?field=&from=&to=` devuelve los valores de un campo categórico presentes en el intervalo, con su recuento y ordenados de mayor a menor.
5. `POST /api/query/interpret` convierte una frase en español en una consulta editable, sin ejecutarla, e indica qué partes de la frase no ha entendido. Es un intérprete mock basado en reglas y sinónimos del dominio bancario. Hay un test con **al menos 12 frases** y su consulta esperada; por ejemplo, «chats negativos de cargos no reconocidos escalados» → `canal is chat`, `sentimiento lt -0,3`, `main topic is cargo_no_reconocido` y `resolución is escalada`.
6. **Consultas guardadas:**
   - se pueden crear (nombre y consulta), listar, obtener, renombrar y borrar;
   - tienen identificador `1QY` (se activa en el registro de prefijos);
   - pertenecen al usuario que las crea: otro usuario recibe `404` al acceder a ellas;
   - se guardan en memoria.
7. Todas las rutas exigen el permiso `explorer:use`; los tests que recorren las rutas de FE001 lo verifican automáticamente.
8. `POST /api/query/run` responde en menos de 500 ms con 10 condiciones sobre el dataset completo.

### Front

9. La sección **Explorador** muestra el intervalo, el campo de lenguaje natural, el constructor de condiciones y el panel de resultados.
10. En el constructor se añaden, editan y quitan condiciones y grupos `Y`/`O`. Para cada campo solo se ofrecen los operadores válidos de su tipo, y el control de valor se adapta: selector con sugerencias y recuento, número, rango o texto.
11. **Tiempo real:** cualquier cambio vuelve a ejecutar la consulta sin pulsar un botón. Hay un debounce de 300 ms y las respuestas antiguas nunca sustituyen a una más reciente (test con respuestas desordenadas). Mientras se recalcula, se mantiene el resultado anterior atenuado.
12. **Lenguaje natural:** al enviar una frase, las condiciones interpretadas se cargan en el constructor para revisarlas, y las partes no entendidas se muestran como aviso.
13. La consulta se muestra en texto legible (`canal es Chat Y (sentimiento < -0,3 O resolución es Escalada)`) y se guarda en la URL, de modo que recargar o compartir el enlace reproduce la misma consulta.
14. El panel de resultados muestra el recuento, las tarjetas de KPI de FE001 y el listado de FE001, con paginación, orden y fila navegable (patrón de FE007). Volver desde el detalle restaura la consulta.
15. Las consultas guardadas se listan, se cargan en el constructor, se renombran y se borran desde la sección.
16. Estados: cargando, error de la API (aviso sin bloquear el constructor) y sin resultados (sugerencia de quitar la última condición).

### Calidad

17. `./scripts/ci.sh` en verde.
18. Verificación en Chrome contra la API real: construir, interpretar, guardar y recargar una consulta; el total del explorador coincide con el del listado de FE001 para una consulta expresable con sus filtros.

## Conocimiento afectado

- [Registro de identificadores](../../vault/ingenieria/registro-de-identificadores.md): activar `1QY`.
- [Arquitectura de la plataforma](../../vault/arquitectura/arquitectura-de-la-plataforma.md): añadir el motor de consultas, el modelo de consulta y el intérprete mock.
- [Glosario](../../vault/glosario/terminos-del-harness.md): añadir «query asistida», «condición» y «grupo».
- [Lecciones de la construcción](../../vault/aprendizaje/lecciones-construccion-plataforma.md): revisar al planificar (estados de error, fechas de referencia, respuestas desordenadas).
- [Revisión de FE001](../FE001-base-dashboards-y-detalle-conversaciones/REVIEW.md), hallazgo R9: el campo de check de cumplimiento permite ver las conversaciones que fallan un check concreto. Documentarlo al entregar.

## Alcance

- API de esquema, sugerencias, ejecución, interpretación y consultas guardadas.
- Sección Explorador con constructor visual, lenguaje natural, resultados en tiempo real y consultas guardadas.

## Fuera de alcance

- Intérprete basado en un LLM real.
- Lenguaje de consulta escrito a mano (tipo SQL).
- Compartir consultas entre usuarios, permisos por consulta y alertas programadas.
- Persistencia entre reinicios.
- Convertir una consulta en un dashboard.

## Riesgos y asunciones

- **Asunción:** «tiempo real» significa recalcular al cambiar la consulta, no recibir conversaciones nuevas en streaming.
- **Riesgo:** un intérprete por reglas solo cubre frases previsibles. Se mitiga porque nunca ejecuta directamente, siempre muestra las condiciones para revisarlas, e indica lo que no entendió.
- **Riesgo:** una consulta en la URL puede ser larga. Se serializa en JSON compacto codificado en base64url en un único parámetro `q`, y se valida al cargar.
