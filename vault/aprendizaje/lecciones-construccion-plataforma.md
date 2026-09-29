---
title: "Lecciones de la construcción de la plataforma"
type: lesson
status: active
owners: [equipo-del-proyecto]
tags: [aprendizaje, testing, fastapi, react, recharts]
created: 2026-09-27
updated: 2026-09-29
---

# Lecciones de la construcción de la plataforma

## Situación

Durante FE001, FE007, FE008, FE002, FE003 y FE004 aparecieron comportamientos de librerías y fallos de verificación que no eran evidentes a priori y que afectarán a las features siguientes.

## Resultado observado

1. **FastAPI 0.141** agrupa los routers incluidos en `_IncludedRouter` (interno). Recorrer `app.routes` ya no lista sus rutas.
2. **Recharts en jsdom** no dibuja las series (no hay tamaño) y exige un stub de `ResizeObserver`. Los clics sobre puntos no se pueden probar ahí.
3. **`scrollIntoView`** desplaza todos los ancestros con scroll, incluida la ventana, y ocultaba la cabecera del detalle.
4. **Generar identificadores con el mismo generador aleatorio** que los datos habría cambiado todo el dataset.
5. **Fijar `DATA_REFERENCE_DATE` en la fecha de hoy** en los tests ocultó un bug: las opciones rápidas de periodo usaban la fecha del navegador.
6. **Los widgets que solo comprueban `data`** se quedan cargando para siempre ante un 4xx/5xx.
7. **`hmac.compare_digest` con `str` no ASCII** lanza `TypeError` (y un token manipulado daba 500).
8. **Un `<header>` dentro de `<main>`** no tiene rol `banner`, sino `sectionheader`.
9. **FE002:** 15 frases de ejemplo no bastaron para el intérprete. El fuzzing con combinaciones de su vocabulario encontró un 500 y tres consultas no válidas con números extremos y citas vacías.
10. **FE002:** en una cadena `lint | grep && git commit`, los avisos de lint no bloquearon el commit.
11. **FE003:** con un IDF suavizado por fragmento, el saludo y la verificación pesaban más que el tema. Con un IDF sin suavizado por conversación, un fragmento que solo contiene una despedida plantillada con el nombre del tema pasaba a ser el «mejor fragmento».
12. **FE003:** comprobar que una frase no comparte palabras con los guiones de un tema no bastó: los guiones se rellenan con comercios reales («Eléctrica del Norte») y hay frases que aparecen en cualquier tema (el PIN). Dos frases «sin palabras en común» se encontraban sin diccionario.
13. **FE003:** aplicar un peso al ranking para arreglar qué fragmento se muestra hundió la relevancia (pares de 9/9 a 6/9). Separar la puntuación que ordena de la que elige el representante lo resolvió.
14. **FE003:** una mutación sobre un fichero aún no versionado se perdió porque la copia de seguridad se hizo después de mutar.
15. **FE003:** probar los cambios de UI en un navegador real reveló el problema de la despedida y del umbral vacío, que los tests con datos simulados no podían ver.
16. **FE004:** el mock de React Flow de su guía de testing no incluye `contentRect`, que la versión 12.12 lee; sin él, el lienzo lanzaba un error en jsdom. Y user-event no rellena `event.view` en `mousedown`, que d3-drag necesita.
17. **FE004:** Chrome reveló tres fallos que los tests no veían: `fitView` en un lienzo vacío cambiaba el zoom con el primer nodo soltado (los siguientes quedaban superpuestos), el tipo de nodo `output` heredaba el estilo del nodo integrado de React Flow y los botones «Añadir» apilaban los nodos.
18. **FE004:** tras guardar y lanzar una ejecución, `navigate` llegaba antes de que React pintara el estado guardado y el aviso de cambios sin guardar bloqueaba la salida.
19. **FE004:** `TestClient` ejecuta las `BackgroundTasks` antes de devolver la respuesta, así que los tests no ven la ejecución «en curso». El progreso se probó con un gancho por paso y un hilo real, y se comprobó con uvicorn.
20. **FE004:** una prueba de carrera sin forzar la ventana solo detectaba la mutación a veces; con un `active` lento es determinista.
21. **FE004:** filtrar la salida del build con `grep` volvió a ocultar un error de tipos (como en la lección 10).
22. **FE004:** en T7 y T8 el código se escribió antes que los tests. Las mutaciones encontraron dos tests débiles: uno no esperaba al debounce y otro miraba el DOM cuando el defecto solo estaba en el JSON.
23. **FE005:** una mutación de Python de la misma longitud que el original (`old` → `new`) «sobrevivía»: el `.pyc` en caché se valida por tamaño y marca de tiempo en segundos, así que el test ejecutaba el código sin mutar.
24. **FE005:** un commit se hizo con el gate en rojo: la cadena `ci.sh; grep … && git commit` comprobaba el `grep`, no el código de salida de `ci.sh` (como en las lecciones 10 y 21, esta vez con el propio gate).
25. **FE005:** una petición nueva al montar un dashboard dejó a la vista un test de FE001 intermitente (1 de cada 4) que buscaba un enlace de una tabla antes de que llegaran los datos.
26. **FE005:** la spec daba por hecho un único `GET /api/config`, pero exige `config:view`: la zona horaria y el nombre, que necesitan todos los roles y el login, no llegaban. Hubo que exponerlos en una ruta pública mínima.
27. **FE005:** el enmascarado pasaba el test del dataset completo, pero tomaba por DNI «20213570 y»: el dataset nunca pone un número de 8 cifras delante de una conjunción. Además, el plan afirmaba que se validaba la letra de control y no era así.

## Causa

Supuestos implícitos sobre librerías y sobre el entorno de test que no se contrastaron con el código instalado ni con el runtime real.

## Aprendizaje

- Enumera las rutas con el esquema OpenAPI (API pública), no con estructuras internas del framework.
- Todo gráfico debe tener una vista de tabla enlazable. Así la interacción se prueba en jsdom y el navegador cubre el gráfico.
- Para desplazar un contenedor, usa `container.scrollTo`, no `scrollIntoView`.
- Aísla los generadores aleatorios por propósito (datos e identificadores) y fija una huella del contenido en un test.
- Para evitar coincidencias con «hoy», en los tests fija fechas de referencia distintas de la actual, y expón desde la API la fecha que usa el backend.
- Todo componente con datos remotos maneja tres estados: cargando, error y vacío.
- Compara secretos como `bytes` (`.encode()`) y prueba entradas no ASCII en todo lo que parsea cabeceras.
- Comprueba la semántica ARIA en la especificación antes de escribir tests por rol.
- Todo componente que transforma texto libre en estructura (intérpretes o parsers) lleva un test de propiedad con semilla fija, además de los ejemplos.
- Valida con `./scripts/ci.sh`, o con comandos que devuelvan código de error, antes de cada commit; no te fíes de salidas filtradas con `grep`.
- En búsqueda o ranking, revisa qué texto concreto produce las mejores coincidencias, no solo si el tema es correcto: el texto plantillado del dataset mock puede explicar el acierto.
- Mide las condiciones de un test de relevancia contra el texto real del dataset, no contra sus plantillas.
- Si una puntuación sirve para dos cosas (ordenar y elegir qué se muestra), sepáralas antes de ajustar pesos.
- Antes de una prueba de mutación, copia el fichero; con ficheros sin versionar no hay `git checkout` que lo recupere.
- Verifica con datos reales cualquier umbral o escala que vaya a ver el usuario.
- Contrasta cada mock de librería con el código instalado, no solo con su guía.
- En editores visuales, verifica en el navegador el arrastre, las posiciones y el encuadre: jsdom no tiene layout.
- Si una navegación sigue a una mutación que cambia el estado que la bloquea, márcala como intencionada en lugar de confiar en el orden de los renders.
- Para probar trabajo en segundo plano, expón un gancho por paso y prueba también con un servidor real.
- Comprueba el build y el lint por su código de salida, nunca por una salida filtrada.
- Si el código precede al test, demuestra el rojo con mutaciones y comprueba qué mira el test (DOM o datos).
- Encadena el commit al gate por su código de salida (`if ./scripts/ci.sh; then git commit …; fi`), nunca a un `grep` de su salida.
- En tests de componentes, busca con `findBy…` todo lo que depende de datos remotos, aunque su contenedor ya esté en pantalla; repite un test sospechoso varias veces antes de darlo por estable.
- Un test sobre el dataset mock solo cubre lo que el generador produce: para lo que convierte texto libre (enmascarado, parsers) añade una propiedad con datos generados junto a textos seguros, y contrasta cada afirmación del plan con el código.
- Al diseñar una configuración global, separa lo que necesitan todos los roles (y el login) de lo que solo ve quien la administra.
- Ejecuta las mutaciones de Python sin caché de bytecode (`python -B` y `PYTHONDONTWRITEBYTECODE=1`); una mutación que sobrevive se confirma a mano antes de tocar el test.

## Acción preventiva

- Tests de regresión añadidos para los puntos 5, 6, 7 y 9 (propiedad de 500 frases).
- Patrón de tabla navegable en [patrones de interfaz](../ingenieria/patrones-de-interfaz.md).
- Revisar esta lista en `/plan` de FE004 a FE006.
- FE005: tests estructurales (ningún módulo importa el catálogo fijo fuera de `app/data/` y `app/config/`; ningún componente formatea fechas fuera de `lib/format.ts`) y test de enmascarado sobre el dataset completo.
- FE003: test de despedidas en los representantes (< 10 %) y test de pares contra los turnos reales del dataset.
- FE004: mock de React Flow con `contentRect` en `frontend/src/test/reactFlow.ts`, tests de ida y vuelta, test de arranque concurrente determinista y patrón de lienzo en [patrones de interfaz](../ingenieria/patrones-de-interfaz.md).

## Fuentes

- [Verificación de FE001](../../features/FE001-base-dashboards-y-detalle-conversaciones/VERIFY.md)
- [Revisión de FE001](../../features/FE001-base-dashboards-y-detalle-conversaciones/REVIEW.md)
- [Verificación de FE002](../../features/FE002-explorador-de-queries-asistidas/VERIFY.md)
- [Plan y evidencia de FE003](../../features/FE003-busqueda-semantica-de-conversaciones/plan.md)
- [Plan y evidencia de FE004](../../features/FE004-disenador-de-flujos-de-insights/plan.md)
- [Plan y evidencia de FE005](../../features/FE005-configuracion-de-la-plataforma/plan.md)
- [HTML-AAM](https://www.w3.org/TR/html-aam-1.0/)
