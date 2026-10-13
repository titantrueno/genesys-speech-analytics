"""FE016 (T8): todos los mensajes de la API están en inglés y no dependen del idioma de la plataforma ni del cliente.

Tres comprobaciones: el código no contiene mensajes de error o de estado en español (análisis estático), el contrato
OpenAPI exportado tampoco, y la misma petición da el mismo mensaje con la plataforma en `es-ES`, en `en-US` y con
`Accept-Language: es`.
"""
import ast
import re
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from app import auth
from app.main import app

BACKEND = Path(__file__).resolve().parents[1]
SOURCES = ("app", "ingestion", "llm")
SPANISH = re.compile(
    r"[áéíóúñ¿¡]|\b(de|el|la|los|las|para|con|sin|una|por|del|al|se|que|su|ha|han|ya|solo|debe|puede|hay)\b", re.I)

# Dónde aparece el texto de un mensaje: argumentos de excepciones y de incidencias, claves `detail`, `message`…, el log
# de una descarga y las listas de avisos. Los datos (etiquetas de catálogo, prompts para el LLM, patrones del
# intérprete, plantillas de flujo) no son mensajes y quedan fuera.
MESSAGE_KEYS = {"detail", "message", "reason", "msg", "error", "warning"}  # y `summary=` como argumento (rutas)
MESSAGE_CALLS = {"HTTPException", "Issue", "Rejection", "FieldIssue", "NodeFailure", "PromptRejected", "ValueRejected"}
LIST_RECEIVERS = {"warnings", "errors", "issues"}
ALLOWED = ("Copia de", "`índice`")  # un nombre de flujo duplicado y un código de unidad de la API: datos, no mensajes


def _call_name(node: ast.Call) -> str:
    func = node.func
    return func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")


def _receiver(node: ast.Call) -> str:
    func = node.func
    return func.value.id if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) else ""


def message_strings(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text())
    found: dict[tuple[int, str], None] = {}
    for node in ast.walk(tree):
        parts: list[ast.AST] = []
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name.endswith(("Error", "Exception")) or name in MESSAGE_CALLS:
                parts += list(node.args) + [k.value for k in node.keywords]
            if name == "log" and path.parts[-2] == "ingestion" or name == "log" and "ingestion" in path.parts:
                parts += list(node.args)
            if name == "append" and _receiver(node) in LIST_RECEIVERS:
                parts += list(node.args)
            parts += [k.value for k in node.keywords if k.arg in MESSAGE_KEYS | {"summary"}]
        if isinstance(node, ast.Dict):
            parts += [v for k, v in zip(node.keys, node.values) if isinstance(k, ast.Constant) and k.value in MESSAGE_KEYS]
        for part in parts:
            for const in ast.walk(part):
                if isinstance(const, ast.Constant) and isinstance(const.value, str):
                    found[(const.lineno, const.value)] = None
    return sorted(found)


def test_no_error_or_status_message_in_the_code_is_in_spanish():
    offenders = []
    for folder in SOURCES:
        for path in sorted((BACKEND / folder).rglob("*.py")):
            for line, text in message_strings(path):
                if SPANISH.search(text) and not any(allowed in text for allowed in ALLOWED):
                    offenders.append(f"{path.relative_to(BACKEND)}:{line}: {text[:90]!r}")
    assert offenders == []


def test_the_exported_openapi_document_has_no_spanish_descriptions():
    document = yaml.safe_load((BACKEND / "openapi.yaml").read_text(encoding="utf-8"))
    offenders: list[str] = []

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("description", "summary", "title") and isinstance(value, str):
                    if SPANISH.search(value) and not any(allowed in value for allowed in ALLOWED):
                        offenders.append(f"{path}/{key}: {value[:90]!r}")
                walk(value, f"{path}/{key}")
        elif isinstance(node, list):
            for i, item in enumerate(node):
                walk(item, f"{path}[{i}]")

    walk(document, "")
    assert offenders == []


def test_the_api_does_not_document_or_read_accept_language():
    assert "Accept-Language" not in (BACKEND / "openapi.yaml").read_text(encoding="utf-8")
    for path in (BACKEND / "app").rglob("*.py"):
        assert "accept-language" not in path.read_text().lower(), path


def _set_language(api, language):
    response = api.put("/api/config/general", json={
        "platform_name": "Speech & Text Analytics", "timezone": "Europe/Madrid", "language": language})
    assert response.status_code == 200, response.text


def _errors(api):
    """Un error por cada forma de respuesta de error: texto, 404, permisos y validación por campo."""
    anonymous = TestClient(app)
    admin = auth.get_store().find_by_email("admin@bancohorizonte.demo")
    viewer = auth.get_store().find_by_email("viewer@bancohorizonte.demo")
    as_viewer = TestClient(app, headers={"Authorization": f"Bearer {auth.create_token(viewer)}"})
    results = {
        "login": anonymous.post("/api/auth/login", json={"email": admin.email, "password": "wrong"}),
        "no_token": anonymous.get("/api/auth/me"),
        "forbidden": as_viewer.get("/api/config"),
        "not_found": api.get("/api/conversations/1CO-00000000-0000-4000-8000-000000000000"),
        "unknown_flow": api.get("/api/flows/1FL-00000000-0000-4000-8000-000000000000"),
        "field_errors": api.put("/api/config/general", json={"platform_name": "", "timezone": "Marte", "language": "xx"}),
        "empty_search": api.get("/api/search/semantic", params={"q": " "}),
    }
    return {name: (r.status_code, r.json()) for name, r in results.items()}


def test_every_error_is_the_same_whatever_the_configured_language_or_the_request_header(api):
    _set_language(api, "es-ES")
    spanish = _errors(api)
    _set_language(api, "en-US")
    english = _errors(api)
    api.headers["Accept-Language"] = "es-ES,es;q=0.9"
    with_header = _errors(api)
    assert spanish == english == with_header
    assert english["login"] == (401, {"detail": "Wrong credentials"})
    assert english["no_token"] == (401, {"detail": "Missing token"})
    assert english["forbidden"][1] == {"detail": "Missing permission config:view"}
    assert english["not_found"][1] == {"detail": "Conversation not found"}
    assert english["unknown_flow"][1] == {"detail": "Flow not found"}
    assert {item["msg"] for item in english["field_errors"][1]["detail"]} == {
        "Cannot be empty", "Unknown time zone", "Language not available; options: es-ES, en-US"}
    assert english["empty_search"][1] == {"detail": "The query cannot be empty"}
