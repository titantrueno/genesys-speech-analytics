---
title: "Catálogo de main topics bancarios"
type: knowledge
status: active
owners: [equipo-del-proyecto]
tags: [producto, main-topic, banca, taxonomia]
created: 2026-09-27
updated: 2026-09-27
---

# Catálogo de main topics bancarios

## Resumen

El **main topic** es el motivo principal de una conversación de atención al cliente del banco. Cada conversación tiene exactamente un main topic de este catálogo. Además, cada conversación tiene un **summary** de 2 a 4 frases: motivo, gestión y resultado.

## Conocimiento confirmado

| Código | Main topic | Colas habituales |
|---|---|---|
| `cargo_no_reconocido` | Cargo no reconocido | Fraude y seguridad, Tarjetas |
| `acceso_banca_digital` | Acceso a banca digital | Banca digital |
| `bloqueo_tarjeta` | Bloqueo de tarjeta | Tarjetas, Fraude y seguridad |
| `transferencias_bizum` | Transferencias y Bizum | Particulares, Banca digital, Empresas |
| `tarjeta_denegada` | Pago o tarjeta denegada | Tarjetas |
| `consulta_saldo_movimientos` | Consulta de saldo y movimientos | Particulares, Banca digital |
| `comisiones` | Reclamación de comisiones | Particulares, Empresas |
| `recibos_domiciliaciones` | Recibos y domiciliaciones | Particulares, Empresas |
| `prestamos_hipotecas` | Préstamos e hipotecas | Préstamos e hipotecas |
| `contratacion_producto` | Contratación de producto | Particulares, Inversión y ahorro, Préstamos e hipotecas |
| `baja_cancelacion` | Baja o cancelación | Particulares, Tarjetas |
| `cajeros` | Incidencia en cajero | Particulares, Tarjetas |
| `datos_personales` | Cambio de datos personales | Particulares |
| `alta_cliente` | Alta de cliente | Particulares, Banca digital |
| `reclamacion_queja` | Reclamación o queja general | Particulares, Empresas |

- **Hecho:** la fuente ejecutable del catálogo (pesos, colas, palabras clave y sentimiento de partida) es `backend/app/data/catalog.py`, y los diálogos por topic están en `backend/app/data/scenarios.py`.
- **Hecho:** el generador mock produce un pico de `cargo_no_reconocido` entre 18 y 24 días antes de la fecha de referencia, para simular una campaña de fraude.
- **Hipótesis:** la distribución de pesos refleja un contact center bancario típico; debe contrastarse con datos reales cuando existan.

## Límites y excepciones

Los valores de main topic y summary son mock generados por reglas, no la salida de un modelo. FE005 hará editable el catálogo desde la configuración.

## Fuentes

- [Spec FE001](../../features/FE001-base-dashboards-y-detalle-conversaciones/spec.md)
- [Catálogo ejecutable](../../backend/app/data/catalog.py)
- [Guiones por main topic](../../backend/app/data/scenarios.py)
