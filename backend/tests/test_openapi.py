"""Contrato OpenAPI: el documento describe todas las operaciones y las respuestas reales cumplen sus esquemas."""
import re
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, ValidationError

from app import auth
from app.main import app
from app.openapi import schemas as s
from app.openapi.spec import OPERATIONS, _as_tuple

EXPORTED = Path(__file__).resolve().parents[1] / "openapi.yaml"
ADMIN = "admin@bancohorizonte.demo"


def spec():
    return app.openapi()


def operations():
    for path, ops in spec()["paths"].items():
        for method, op in ops.items():
            yield method.upper(), path, op


def test_every_operation_is_documented_in_spanish_with_a_success_response():
    ids = [op["operationId"] for _, _, op in operations()]
    assert len(ids) == len(set(ids)) == len(OPERATIONS)
    summaries = [op["summary"] for _, _, op in operations()]
    assert len(summaries) == len(set(summaries)), "resúmenes repetidos"
    for method, path, op in operations():
        success = [code for code in op["responses"] if code.startswith("2")]
        assert len(success) == 1, (method, path)
        if success[0] != "204":
            assert "schema" in op["responses"][success[0]]["content"]["application/json"], (method, path)
            schema = op["responses"][success[0]]["content"]["application/json"]["schema"]
            assert schema != {"type": "object", "additionalProperties": True}, (method, path)


def test_security_matches_the_route_protection():
    public = {("GET", "/api/health"), ("POST", "/api/auth/login"), ("GET", "/api/config/public")}
    assert spec()["components"]["securitySchemes"]["bearerAuth"] == {
        "type": "http", "scheme": "bearer", "description": spec()["components"]["securitySchemes"]["bearerAuth"]["description"]}
    for method, path, op in operations():
        if (method, path) in public:
            assert op["security"] == [], (method, path)
            assert ("401" in op["responses"]) == (path == "/api/auth/login"), (method, path)
        else:
            assert "security" not in op, (method, path)  # hereda la global (bearerAuth)
            assert "401" in op["responses"], (method, path)
            assert ("403" in op["responses"]) == (path != "/api/auth/me"), (method, path)
            for response in op["responses"].values():
                assert "X-Auth-Version" in response["headers"], (method, path)


def test_untyped_request_bodies_are_documented():
    for method, path, op in operations():
        body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
        if body is not None:
            assert body != {"title": "Payload"} and body.get("title") != "Payload", (method, path)


def test_exported_document_is_up_to_date():
    """`backend/openapi.yaml` se regenera con `python scripts/export_openapi.py`."""
    assert EXPORTED.exists(), "falta backend/openapi.yaml: ejecuta python scripts/export_openapi.py"
    assert yaml.safe_load(EXPORTED.read_text(encoding="utf-8")) == spec(), \
        "backend/openapi.yaml está desactualizado: ejecuta python scripts/export_openapi.py"


# --- Contrato con respuestas reales --------------------------------------------------------------------------------

def _template(method: str, url: str) -> str:
    path = url.split("?")[0]
    for template in spec()["paths"]:
        pattern = "^" + re.sub(r"\{[^}]+\}", "[^/]+", template) + "$"
        if re.match(pattern, path) and method.lower() in spec()["paths"][template]:
            if template.endswith("/audit") or "{" not in template or path.count("/") == template.count("/"):
                exact = [t for t in spec()["paths"] if t == path]
                return exact[0] if exact else template
    raise AssertionError(f"Sin plantilla para {method} {url}")


class NativeIssue(BaseModel):
    """Error de validación nativo de FastAPI (`HTTPValidationError` del OpenAPI)."""
    model_config = ConfigDict(extra="forbid")
    type: str
    loc: list[str | int]
    msg: str
    input: object = None
    ctx: dict | None = None


class NativeErrors(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detail: list[NativeIssue]


def _declares_native_422(method: str, template: str) -> bool:
    schema = spec()["paths"][template][method.lower()]["responses"].get("422", {})
    refs = schema.get("content", {}).get("application/json", {}).get("schema", {})
    return "HTTPValidationError" in str(refs)


def _models_for(method: str, template: str, status: int) -> tuple[type[BaseModel], ...] | None:
    op = OPERATIONS[(method, template)]
    native = (NativeErrors,) if status == 422 and _declares_native_422(method, template) else ()
    if status == op.status:
        return (op.ok,) if op.ok is not None else None
    if status in op.errors:
        return _as_tuple(op.errors[status][1]) + native
    if native:
        return native
    if status in (401, 403):
        return (s.ErrorText,)
    raise AssertionError(f"{method} {template}: código {status} no documentado")


def _matches(models: tuple[type[BaseModel], ...], raw: str) -> bool:
    """Valida el JSON en modo estricto: un `1` no pasa por `true` ni un texto por un número."""
    for model in models:
        try:
            model.model_validate_json(raw, strict=True)
            return True
        except ValidationError:
            continue
    return False


class Recorder:
    def __init__(self, client: TestClient):
        self.client = client
        self.seen: list[tuple[str, str, int]] = []

    def __call__(self, method: str, url: str, expected: int, **kwargs):
        response = self.client.request(method, url, **kwargs)
        assert response.status_code == expected, (method, url, response.status_code, response.text[:300])
        template = _template(method, url)
        self.seen.append((method, template, expected))
        assert ("x-auth-version" in response.headers) == ("authorization" in {k.lower() for k in self.client.headers}
                                                          | {k.lower() for k in kwargs.get("headers", {})})
        if expected == 204:
            assert response.content == b""
            return None
        body = response.json()
        models = _models_for(method, template, expected)
        if models is not None:
            assert _matches(models, response.text), (method, template, expected, [m.__name__ for m in models], str(body)[:300])
        elif expected == 422:
            assert isinstance(body["detail"], list)
        return body


@pytest.fixture
def call(api):
    return Recorder(api)


def test_real_responses_match_the_documented_schemas(call, api):
    anonymous = Recorder(TestClient(app))
    anonymous("GET", "/api/health", 200)
    anonymous("GET", "/api/config/public", 200)
    anonymous("POST", "/api/auth/login", 200, json={"email": ADMIN, "password": auth.DEMO_PASSWORD})
    anonymous("POST", "/api/auth/login", 401, json={"email": ADMIN, "password": "mala"})
    anonymous("GET", "/api/auth/me", 401)

    call("GET", "/api/auth/me", 200)
    catalog = call("GET", "/api/catalog", 200)
    call("GET", "/api/metrics/summary?dashboard=vision-general", 200)
    call("GET", "/api/metrics/summary?channel=voz", 200)
    call("GET", "/api/metrics/timeseries?kpi=first_response_s&granularity=week", 200)
    call("GET", "/api/metrics/breakdown?dimension=queue", 200)
    call("GET", "/api/metrics/breakdown?dimension=agent&queue=basura", 422)
    page = call("GET", "/api/conversations?page_size=3&sort=sentiment&order=asc", 200)
    call("GET", "/api/conversations?from=2026-09-30&to=2026-09-01", 422)
    call("GET", "/api/conversations?page_size=500", 422)
    conversation_id = page["items"][0]["id"]
    call("GET", f"/api/conversations/{conversation_id.lower()}", 200)
    call("GET", "/api/conversations/1CO-00000000-0000-4000-8000-000000000000", 404)

    query = {"root": {"op": "and", "conditions": [
        {"field": "channel", "operator": "is", "value": "chat"},
        {"field": "sentiment", "operator": "between", "value": [-1, 0]},
        {"op": "or", "conditions": [{"field": "check:saludo", "operator": "fails"},
                                    {"field": "transcript", "operator": "contains", "value": "tarjeta",
                                     "speaker": "cliente"}]}]}}
    call("GET", "/api/query/schema", 200)
    call("POST", "/api/query/run?page_size=2", 200, json=query)
    call("POST", "/api/query/run", 422, json={"root": {"op": "and", "conditions": [{"field": "x", "operator": "is"}]}})
    call("GET", "/api/query/suggest?field=main_topic", 200)
    call("GET", "/api/query/suggest?field=sentiment", 422)
    call("POST", "/api/query/interpret", 200, json={"text": "chats negativos sin resolver"})
    call("POST", "/api/query/interpret", 422, json={"text": " "})
    saved = call("POST", "/api/query/saved", 201, json={"name": "Chats", "query": query})
    call("POST", "/api/query/saved", 422, json={"name": "  ", "query": query})
    call("GET", "/api/query/saved", 200)
    call("GET", f"/api/query/saved/{saved['id']}", 200)
    call("PATCH", f"/api/query/saved/{saved['id']}", 200, json={"name": "Chats negativos"})
    call("DELETE", f"/api/query/saved/{saved['id']}", 204)
    call("GET", f"/api/query/saved/{saved['id']}", 404)

    call("GET", "/api/search/semantic?q=bloquear%20tarjeta&group=fragment&limit=3", 200)
    call("GET", "/api/search/semantic?q=zzzzqqq", 200)
    call("GET", "/api/search/semantic?q=%20", 422)
    call("GET", f"/api/search/similar/{conversation_id}", 200)

    call("GET", "/api/flows/catalog", 200)
    flow = call("POST", "/api/flows", 201, json={"name": "Motivos"})
    call("POST", "/api/flows", 422, json={"name": "   "})
    graph = {"version": 1, "nodes": [
        {"id": "tmp-s", "type": "sampling", "position": {"x": 0, "y": 0},
         "config": {"query": query, "method": "aleatorio", "size": 4}},
        {"id": "tmp-p", "type": "prompt", "position": {"x": 1, "y": 0},
         "config": {"template": "{{transcripcion}}", "model": "mock-rapido", "temperature": 0,
                    "output": {"type": "json", "fields": [{"name": "motivo", "type": "texto"}]}}},
        {"id": "tmp-e", "type": "prompt", "position": {"x": 2, "y": 0},
         "config": {"template": "{{summary}}", "model": "mock-preciso", "temperature": 0.5,
                    "output": {"type": "etiqueta", "labels": ["sí", "no"]}}},
        {"id": "tmp-t", "type": "output", "position": {"x": 3, "y": 0}, "config": {"kind": "tabla", "destination": "T"}},
        {"id": "tmp-m", "type": "output", "position": {"x": 3, "y": 1},
         "config": {"kind": "metrica", "aggregation": "recuento", "destination": "M"}},
        {"id": "tmp-i", "type": "output", "position": {"x": 3, "y": 2}, "config": {"kind": "informe", "destination": "I"}}],
        "edges": [{"source": "tmp-s", "target": "tmp-p"}, {"source": "tmp-s", "target": "tmp-e"},
                  {"source": "tmp-p", "target": "tmp-t"}, {"source": "tmp-e", "target": "tmp-m"},
                  {"source": "tmp-e", "target": "tmp-i"}]}
    call("POST", "/api/flows/validate", 200, json={"nodes": [graph["nodes"][1]]})
    call("POST", "/api/flows/validate", 422, json={"nodes": [{"id": "malo", "type": "output"}]})
    call("POST", "/api/flows/sampling/estimate", 200, json={"query": query, "size": 10})
    call("POST", "/api/flows/sampling/estimate", 422, json={"query": {"root": {"op": "xor"}}})
    call("POST", f"/api/flows/{flow['id']}/runs", 422)
    call("PUT", f"/api/flows/{flow['id']}/graph", 200, json=graph)
    call("PUT", f"/api/flows/{flow['id']}/graph", 422, json={"nodes": [], "edges": [{"source": "a", "target": "b"}]})
    call("PATCH", f"/api/flows/{flow['id']}", 200, json={"name": "Motivos de queja"})
    call("GET", f"/api/flows/{flow['id']}", 200)
    run = call("POST", f"/api/flows/{flow['id']}/runs", 202)
    finished = call("GET", f"/api/flows/{flow['id']}/runs/{run['id']}", 200)
    assert finished["status"] == "ok" and {o["kind"] for o in finished["outputs"].values()} == {"tabla", "metrica", "informe"}
    call("GET", f"/api/flows/{flow['id']}/runs", 200)
    call("GET", f"/api/flows/{flow['id']}/runs/1RN-00000000-0000-4000-8000-000000000000", 404)
    call("GET", "/api/flows", 200)
    copy = call("POST", f"/api/flows/{flow['id']}/duplicate", 201)
    call("DELETE", f"/api/flows/{copy['id']}", 204)
    call("GET", f"/api/flows/{copy['id']}", 404)

    config = call("GET", "/api/config", 200)
    call("PUT", "/api/config/general", 200, json={**config["general"], "timezone": "UTC"})
    call("PUT", "/api/config/general", 422, json={"platform_name": "", "timezone": "Marte", "language": "xx"})
    call("PUT", "/api/config/privacy", 200, json={"pii_masking": False})
    call("PUT", "/api/config/ai", 200, json={"provider": "simulado", "model": "mock-preciso"})
    call("PUT", "/api/config/kpis/csat_avg", 200, json={"target": 4, "green": 4, "amber": 3.5, "dashboards": []})
    call("PUT", "/api/config/kpis/csat_avg", 422, json={"target": 4, "green": 3, "amber": 4, "dashboards": []})
    call("PUT", "/api/config/kpis/inventado", 404, json={})
    connectors = call("GET", "/api/config/connectors", 200)
    call("POST", f"/api/config/connectors/{connectors['items'][0]['id']}/sync", 200)
    taxonomy = call("GET", "/api/config/taxonomy", 200)
    topic = call("POST", "/api/config/taxonomy/main-topics", 201,
                 json={"code": "hipotecas_verdes", "name": "Hipotecas verdes", "keywords": ["verde"]})
    call("POST", "/api/config/taxonomy/secondary-topics", 201, json={"code": "hipoteca verde", "name": "hipoteca verde"})
    call("PUT", f"/api/config/taxonomy/main-topics/{topic['id']}", 200,
         json={"code": "hipotecas_verdes", "name": "Hipotecas sostenibles", "active": False})
    call("DELETE", f"/api/config/taxonomy/main-topics/{taxonomy['main_topics'][0]['id']}", 409)
    call("DELETE", f"/api/config/taxonomy/main-topics/{topic['id']}", 204)
    call("PUT", f"/api/config/taxonomy/main-topics/{topic['id']}", 404, json={"code": "hipotecas_verdes", "name": "X"})
    checks = call("GET", "/api/config/compliance-checks", 200)
    check = call("POST", "/api/config/compliance-checks", 201,
                 json={"code": "oferta_seguro", "name": "Oferta de seguro", "phrases": ["seguro de protección"]})
    call("POST", "/api/config/compliance-checks", 422, json={"code": "oferta_seguro", "name": "Otro", "phrases": ["a"]})
    call("PUT", f"/api/config/compliance-checks/{check['id']}", 200,
         json={"code": "oferta_seguro", "name": "Oferta de seguro", "phrases": ["seguro"], "channel": "voz"})
    call("DELETE", f"/api/config/compliance-checks/{checks['items'][0]['id']}", 409)
    call("DELETE", f"/api/config/compliance-checks/{check['id']}", 204)
    call("GET", "/api/config/audit?section=cumplimiento", 200)
    call("GET", "/api/config/audit", 200)

    users = call("GET", "/api/users?q=demo&active=true", 200)
    created = call("POST", "/api/users", 201, json={"name": "Lucía", "email": "lucia@bancohorizonte.demo", "role": "viewer"})
    call("POST", "/api/users", 409, json={"name": "Otra", "email": ADMIN, "role": "viewer"})
    call("POST", "/api/users", 422, json={"name": "", "email": "x", "role": "viewer"})
    call("PUT", f"/api/users/{created['id']}", 200, json={**{k: created[k] for k in ("name", "email", "role")},
                                                          "active": False})
    admin = next(u for u in users["items"] if u["email"] == ADMIN)
    call("PUT", f"/api/users/{admin['id']}", 409, json={"name": "A", "email": ADMIN, "role": "viewer", "active": True})
    call("PUT", "/api/users/1US-00000000-0000-4000-8000-000000000000", 404,
         json={"name": "A", "email": "a@b.co", "role": "viewer", "active": True})
    call("GET", "/api/users/audit", 200)
    roles = call("GET", "/api/roles", 200)
    role = call("POST", "/api/roles", 201, json={"code": "auditor", "name": "Auditor", "permissions": ["config:view"]})
    call("POST", "/api/roles", 409, json={"code": "auditor", "name": "Otro", "permissions": []})
    call("POST", "/api/roles", 422, json={"code": "Mal Código", "name": "X", "permissions": []})
    admin_role = next(r for r in roles["items"] if r["code"] == "admin")
    call("PUT", f"/api/roles/{admin_role['id']}", 409, json={"name": "Administrador", "permissions": []})
    call("PUT", f"/api/roles/{role['id']}", 200, json={"name": "Auditoría", "permissions": []})
    call("DELETE", f"/api/roles/{admin_role['id']}", 409)
    call("DELETE", f"/api/roles/{role['id']}", 204)
    call("DELETE", f"/api/roles/{role['id']}", 404)

    viewer = Recorder(TestClient(app))
    token = auth.create_token(auth.get_store().find_by_email("viewer@bancohorizonte.demo"))
    viewer.client.headers["Authorization"] = f"Bearer {token}"
    viewer("GET", "/api/flows", 403)

    seen = {(method, template) for method, template, _ in call.seen + anonymous.seen + viewer.seen}
    successes = {(method, template) for method, template, status in call.seen + anonymous.seen
                 if status == OPERATIONS[(method, template)].status}
    assert set(OPERATIONS) - successes == set(), "operaciones sin respuesta correcta en el contrato"
    assert seen <= set(OPERATIONS)
    assert catalog["reference_date"]
