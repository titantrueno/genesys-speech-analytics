"""Servicio de ingesta de Genesys Cloud (FE011): un proceso aparte de la API que descarga, normaliza y guarda
conversaciones reales en PostgreSQL. Es el único que lee las credenciales de Genesys.

Solo comparte con la API `app.ids` (los identificadores se generan en un único sitio), `app.clock` y `app.envfile`.
"""
