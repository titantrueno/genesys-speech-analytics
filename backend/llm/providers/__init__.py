"""Registro de proveedores de LLM (FE013, criterio 4).

Añadir un proveedor es escribir su clase (`HttpProvider` si llama a una API) y darlo de alta aquí; su clave, en
`app/envfile.LLM_KEYS` y `llm/settings.PROVIDER_KEYS`, y sus modelos, en el catálogo de la API.
"""
from llm.providers.anthropic import Anthropic
from llm.providers.base import LlmProvider
from llm.providers.gemini import Gemini
from llm.providers.openai import OpenAI
from llm.providers.simulated import Simulated

REGISTRY: dict[str, LlmProvider] = {p.name: p for p in (Gemini(), OpenAI(), Anthropic(), Simulated())}
