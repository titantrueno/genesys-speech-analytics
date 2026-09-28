---
title: "Lecciones de la construcción de la plataforma"
type: lesson
status: active
owners: [equipo-del-proyecto]
tags: [aprendizaje, testing, fastapi, react, recharts]
created: 2026-09-27
updated: 2026-09-28
---

# Lecciones de la construcción de la plataforma

## Situación

Durante FE001, FE007, FE008, FE002 y FE003 aparecieron comportamientos de librerías y fallos de verificación que no eran evidentes a priori y que afectarán a las features siguientes.

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

## Acción preventiva

- Tests de regresión añadidos para los puntos 5, 6, 7 y 9 (propiedad de 500 frases).
- Patrón de tabla navegable en [patrones de interfaz](../ingenieria/patrones-de-interfaz.md).
- Revisar esta lista en `/plan` de FE004 a FE006.
- FE003: test de despedidas en los representantes (< 10 %) y test de pares contra los turnos reales del dataset.

## Fuentes

- [Verificación de FE001](../../features/FE001-base-dashboards-y-detalle-conversaciones/VERIFY.md)
- [Revisión de FE001](../../features/FE001-base-dashboards-y-detalle-conversaciones/REVIEW.md)
- [Verificación de FE002](../../features/FE002-explorador-de-queries-asistidas/VERIFY.md)
- [Plan y evidencia de FE003](../../features/FE003-busqueda-semantica-de-conversaciones/plan.md)
- [HTML-AAM](https://www.w3.org/TR/html-aam-1.0/)
