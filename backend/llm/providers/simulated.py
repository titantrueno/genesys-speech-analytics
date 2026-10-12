"""Proveedor simulado (FE013): sin red ni clave, determinista. Sirve para los tests y para trabajar sin clave.

El resultado depende solo del modelo y del prompt (`sha256`, estable entre procesos) y respeta el formato pedido.
"""
import hashlib
import json

from llm.providers.base import Completion, CompletionRequest

_DEFAULTS = {"string": "texto simulado", "number": 0, "integer": 0, "boolean": False}


class Simulated:
    name, label, needs_key, key_env = "simulado", "Simulado (sin LLM)", False, None

    def complete(self, request: CompletionRequest, key=None, http=None) -> Completion:
        digest = int(hashlib.sha256(f"{request.model}\n{request.prompt}".encode()).hexdigest(), 16)
        output = request.output
        if output.type == "etiqueta" and output.labels:
            text = output.labels[digest % len(output.labels)]
        elif output.type == "json":
            properties = (output.schema or {}).get("properties", {})
            text = json.dumps({name: _DEFAULTS.get(spec.get("type"), None) for name, spec in properties.items()},
                              ensure_ascii=False)
        else:
            text = f"Resultado simulado {digest % 10_000:04d} para un prompt de {len(request.prompt)} caracteres."
        return Completion(text=text, model=request.model, input_tokens=len(request.prompt) // 4,
                          output_tokens=len(text) // 4)
