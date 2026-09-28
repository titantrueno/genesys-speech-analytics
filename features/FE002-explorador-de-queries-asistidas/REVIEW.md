# FE002 — Revisión

> Fase `/review`. Fecha: 2026-09-28. Artefactos: [spec](spec.md) · [plan](plan.md) · [verificación](VERIFY.md). Siguiente paso: `/ship`.

## Resultado

**Aprobado.** Sin hallazgos critical ni major abiertos.

## Tamaño del cambio

El cambio supera las ~100 líneas recomendadas. Se entregó en 13 commits atómicos (T1–T9, T7 dividida en a/b, más correcciones), cada uno con su evidencia rojo → verde en el [plan](plan.md#progreso).

## Hallazgos

| # | Eje | Severidad | Hallazgo | Decisión |
|---|---|---|---|---|
| R1 | Corrección | **major** | El intérprete devolvía consultas no válidas y un 500 con números extremos o citas vacías | **Resuelto en `/test`** (`a4553bd`), con propiedad de fuzzing en la suite |
| R2 | Seguridad | **major** | Sin límite de tamaño de consulta: cientos de condiciones o listas enormes permitían abusar de la API | **Resuelto:** máximo de 50 condiciones y 200 valores por lista (`test_query_size_is_limited`, rojo → verde) |
| R3 | Corrección | minor | Los errores `422` sin condición asociada no se mostraban | **Resuelto en `/test`**, con test |
| R4 | Corrección | minor | Al cambiar de campo se arrastraba el valor anterior | **Resuelto en `/build`** (`replaceCondition`) |
| R5 | Proceso | minor | Un commit de T7a entró con avisos de lint | **Resuelto** en el commit siguiente; lección capturada (validar con códigos de error, no con `grep`) |
| R6 | Seguridad | minor | El almacén de consultas guardadas no es seguro ante concurrencia (endpoints síncronos en un pool de hilos) | **Aceptado:** mock en memoria de un solo usuario demo por sesión; con persistencia real se usará una base de datos transaccional |
| R7 | Seguridad | — | Consultas guardadas privadas (`404`), identificadores no adivinables, texto de entrada ≤ 500 caracteres, regex lineales, sin `innerHTML`, `q` decodificado como JSON y validado | Correcto |
| R8 | Adherencia a la spec | nit | El explorador muestra 6 de los 13 KPIs que devuelve la API | **Justificado:** son los de la fila de «Visión general»; los 13 están en la respuesta para usos futuros |
| R9 | Adherencia a la spec | nit | El hook de URL se llama `useExplorerState` y se implementó en T7, no en T6 | **Justificado** en el plan |
| R10 | Simplicidad | nit | Tipado de orden con `Parameters<typeof nextSort>` | **Resuelto:** `SortState` |
| R11 | Rendimiento | — | < 500 ms con 10 condiciones; caché de textos normalizados; sugerencias cacheadas por clave | Correcto |
| R12 | Conocimiento | — | Arquitectura (motor de consultas), glosario, registro (`1QY` activo), lecciones 9 y 10, R9 de FE001 resuelto | Correcto |

## Revisión por ejes

- **Corrección:** 31 operadores contra un cálculo independiente, mutaciones detectadas, fuzzing del intérprete y cruces con el listado de FE001.
- **Adherencia a la spec:** los 18 criterios trazados; el fuera de alcance se respeta (sin LLM, sin SQL, sin compartir, sin persistencia).
- **Simplicidad:** módulos pequeños por responsabilidad (`model`, `fields`, `engine`, `interpreter`, `saved`); tabla y paginación compartidas con el listado en lugar de duplicarlas.
- **Seguridad:** ver R2, R6 y R7.
- **Rendimiento:** ver R11.
- **Conocimiento:** ver R12.
