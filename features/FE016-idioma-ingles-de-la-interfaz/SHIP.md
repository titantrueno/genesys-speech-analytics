# FE016 — Ship

> Fase `/ship`. Fecha: 2026-10-13. Entrega: [Plataforma v0.12.0](../../vault/entregas/2026-10-13-plataforma-v0-12-0.md).

## Trazabilidad

| Artefacto | Estado |
|---|---|
| [spec.md](spec.md) | Entregada. Cambió durante la obra por decisión de la persona usuaria: sin selector personal y API solo en inglés (ver [ADR-010](../../vault/decisiones/adr-010-idioma-de-la-interfaz-y-api-en-ingles.md)) |
| [plan.md](plan.md) | T1–T9 hechas, una por commit; T8 replanteada (de `Accept-Language` a «API solo en inglés») |
| [VERIFY.md](VERIFY.md) | Verde: 15 criterios con evidencia, 9 de 9 mutaciones detectadas, fuentes oficiales citadas y tres defectos corregidos |
| [REVIEW.md](REVIEW.md) | Aprobada, sin critical ni major abiertos: K1 (cifra de carga inicial desactualizada en el vault) resuelto |

## Qué se entrega

Integración trunk-based en `main`, de `v0.11.0` a `v0.12.0`.

- **Una decisión sobre la entrega:** FE015 (persistencia de flujos y preferencias) ya estaba en `main` sin `/test` ni `/review`. Por decisión de la persona usuaria viaja en esta versión; su gate completo está en verde, pero **queda como deuda hacerle su verificación y revisión**. Está anotado en la entrega del vault, en su spec y en el README.
- **FE016, interfaz:** capa i18n propia, 1.100 claves por idioma, formatos por idioma y el ajuste «Idioma de la interfaz» en Configuración → General.
- **FE016, API:** mensajes, validación, logs y OpenAPI solo en inglés; `en-US` como idioma de la plataforma; versión `0.12.0`.
- **Dependencias:** ninguna nueva.

## Pipeline con gates

`./scripts/ci.sh` termina con código 0:

- vault sin errores;
- backend: 1.159 tests con cada dataset y 192 con PostgreSQL;
- OpenAPI al día y válido;
- front: 572 tests, lint y build;
- `pip-audit` y `npm audit --audit-level=high` sin vulnerabilidades «high».

`.github/workflows/ci.yml` ejecuta lo mismo. Ningún test usa red ni claves reales.

## Observabilidad

- **Idioma efectivo:** `GET /api/config/public` y `<html lang>`.
- **Mensajes de la API:** el test `test_api_messages_english.py` y el log de una descarga con sus etapas en inglés son la señal de salud de la feature.
- **Persistencia (FE015):** un `503` al guardar indica que el servicio de ingesta no responde; su `/health` y el [estado operativo](../../vault/operaciones/estado-operativo.md) dicen cómo comprobarlo.

## Rollout y rollback

- **Rollout:** etiqueta `v0.12.0` en `main`, sin despliegue. La migración `0007` (FE015) es aditiva y se aplica al arrancar el servicio de ingesta. El idioma por defecto sigue siendo `es-ES`: sin tocar nada, la interfaz no cambia.
- **Blast radius:** toda la interfaz y todos los mensajes de la API. Se acota porque el inglés de la interfaz es opcional y reversible desde Configuración.
- **Rollback de la interfaz:** «Idioma de la interfaz» en Español y guardar; inmediato.
- **Rollback de código:** volver a `v0.11.0`; la migración `0007` queda sin usar y no estorba. El inglés de la API solo se deshace volviendo al código anterior.
