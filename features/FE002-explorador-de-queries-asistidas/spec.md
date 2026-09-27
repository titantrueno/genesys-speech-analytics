# FE002 — Explorador de queries asistidas

> Estado: **pendiente de aprobación**. Depende de FE001 (API, datos mock, listado y detalle).

## Objetivo

Permitir filtrar en tiempo real las conversaciones de un intervalo mediante un constructor de consultas asistido, con resultados y agregados que se actualizan al instante.

## Criterios de aceptación

1. La sección **Explorador** muestra un selector de intervalo, un constructor de condiciones y un panel de resultados.
2. Cada condición combina campo, operador y valor. Los campos cubren canal, cola, agente, main topic, tema secundario, summary (texto), sentimiento, resolución, CSAT predicho, esfuerzo, riesgo de abandono, duración, nº de turnos, check de cumplimiento, hablante y texto contenido.
3. Los operadores dependen del tipo del campo: numérico (`=`, `≠`, `>`, `≥`, `<`, `≤`, `entre`), categórico (`es`, `no es`, `en`) y texto (`contiene`, `no contiene`). `GET /api/query/schema` expone el esquema y un test valida que el front solo ofrece operadores válidos para cada tipo.
4. **Asistencia:** el valor de un campo categórico se autocompleta con los valores reales del intervalo y su recuento (`GET /api/query/suggest`).
5. Las condiciones se agrupan con `Y` / `O`, con al menos un nivel de anidamiento.
6. **Tiempo real:** al añadir, editar o quitar una condición, el recuento, el listado y los agregados se recalculan sin pulsar un botón, en menos de 1 s desde el último cambio (debounce ≤ 300 ms y respuesta de API < 500 ms).
7. **Consulta en lenguaje natural asistida:** un campo de texto convierte frases sencillas en condiciones editables antes de ejecutarlas. Por ejemplo, «chats negativos de cargos no reconocidos escalados» produce `canal = chat`, `sentimiento < -0,3`, `main topic = cargo_no_reconocido` y `resolución = escalada`. El intérprete es mock basado en reglas, y hay un test con al menos 10 frases de ejemplo y sus condiciones esperadas.
8. La consulta se muestra también en texto legible (p. ej. `canal = chat Y sentimiento < -0,3`) y se refleja en la URL, que se puede compartir.
9. El panel de resultados muestra el recuento, un mini-resumen de KPIs de FE001 sobre el subconjunto y el listado reutilizando el componente de FE001. Al pulsar una fila se abre el detalle tipo chat.
10. Las consultas se pueden guardar con un nombre, listar, cargar y borrar (persistencia en memoria del backend).
11. Una consulta sin resultados muestra un estado vacío con la sugerencia de quitar la última condición.
12. Las pruebas de backend cubren cada operador y la combinación `Y`/`O`, comparando con un filtrado independiente del dataset.

## Conocimiento afectado

- [Glosario](../../vault/glosario/terminos-del-harness.md): hay que añadir «query asistida» y la notación de condiciones.
- La nueva entrada de arquitectura de la plataforma (creada en FE001) debe incluir el motor de filtrado y el intérprete de lenguaje natural mock.

## Alcance

- API de esquema, sugerencias, ejecución de consultas y consultas guardadas.
- Constructor visual de condiciones con grupos, intérprete de lenguaje natural por reglas y panel de resultados en tiempo real.

## Fuera de alcance

- Intérprete de lenguaje natural basado en un LLM real.
- Lenguaje de consulta escrito a mano por el usuario (tipo SQL).
- Compartir consultas entre usuarios o gestionar permisos por consulta.
- Alertas programadas sobre una consulta.

## Riesgos y asunciones

- **Asunción:** «tiempo real» significa que el resultado se actualiza al cambiar el filtro, no streaming de conversaciones nuevas.
- **Riesgo:** un intérprete por reglas solo cubre frases previsibles. La UI siempre muestra las condiciones generadas para que el usuario las revise.
