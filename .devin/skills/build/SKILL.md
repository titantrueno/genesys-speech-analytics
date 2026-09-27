---
name: build
description: "Harness starter — Build. Implementa UNA tarea como slice vertical con TDD (test primero, luego código)."
---

# /build — Build

> Fase 3 del ciclo `Define → Plan → Build → Verify → Review → Ship`.
> El test escrito **antes** define el objetivo; el código verde lo cumple. El test *demuestra*, no afirma.

## Cuándo se invoca

- `/build` con `plan.md` listo. Trabaja **una tarea a la vez** (la primera no completada).

## Pasos

1. **Elige una sola tarea** de `features/FEXXX-descripcion-breve/plan.md` (la siguiente por dependencias).
2. **Test primero (rojo).** Escribe el test que prueba el criterio de aceptación de esa tarea.
   Ejecútalo y confirma que **falla** por la razón correcta.
3. **Código mínimo (verde).** Implementa lo justo para que el test pase. Nada más.
4. **Context-engineering.** Si tocas una parte del sistema que no conoces, léela primero; no alucines
   APIs ni contratos.
5. **Captura conocimiento emergente.** Si descubres una decisión o aprendizaje no previsto, busca primero en el vault. Actualiza la entrada canónica cuando exista; si no existe, usa `/vault capture` con propietario y fuente. No crees un duplicado.
6. **Commit atómico** con un mensaje que describa el cambio. Una tarea = un commit.

## Gate (default-FAIL)

- ⏸ No marques la tarea como hecha sin un test que **pasaría de rojo a verde**. Un test que pasa
  siempre no prueba nada.
- Si el test no falla antes de implementar, está mal escrito: arréglalo.

## Salida

- Código + test verde + commit, para una tarea.
- Repite `/build` hasta agotar `plan.md`; luego **`/test`**.
