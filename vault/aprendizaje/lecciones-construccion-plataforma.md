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

Durante FE001, FE007 y FE008 aparecieron comportamientos de librerías y fallos de verificación que no eran evidentes a priori y que afectarán a las features siguientes.

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

## Acción preventiva

- Tests de regresión añadidos para los puntos 5, 6, 7 y 9 (propiedad de 500 frases).
- Patrón de tabla navegable en [patrones de interfaz](../ingenieria/patrones-de-interfaz.md).
- Revisar esta lista en `/plan` de FE002 a FE006.

## Fuentes

- [Verificación de FE001](../../features/FE001-base-dashboards-y-detalle-conversaciones/VERIFY.md)
- [Revisión de FE001](../../features/FE001-base-dashboards-y-detalle-conversaciones/REVIEW.md)
- [Verificación de FE002](../../features/FE002-explorador-de-queries-asistidas/VERIFY.md)
- [HTML-AAM](https://www.w3.org/TR/html-aam-1.0/)
