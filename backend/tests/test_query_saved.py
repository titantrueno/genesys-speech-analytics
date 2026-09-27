import pytest

from app import auth, ids
from app.data.catalog import QUEUE_IDS

QUERY = {"root": {"op": "and", "conditions": [
    {"field": "channel", "operator": "is", "value": "chat"},
    {"field": "queue", "operator": "is", "value": QUEUE_IDS["Tarjetas"].lower()},
]}}


def headers_for(email):
    user = auth.get_store().find_by_email(email)
    return {"Authorization": f"Bearer {auth.create_token(user)}"}


def create(api, name="Chats de tarjetas", query=QUERY, **kwargs):
    return api.post("/api/query/saved", json={"name": name, "query": query}, **kwargs)


def test_create_returns_prefixed_id_and_canonical_query(api):
    response = create(api)
    assert response.status_code == 201
    body = response.json()
    assert ids.is_valid(body["id"], ids.SAVED_QUERY)
    assert body["name"] == "Chats de tarjetas"
    assert body["query"]["root"]["conditions"][1]["value"] == QUEUE_IDS["Tarjetas"]
    assert "from" not in body["query"] and "to" not in body["query"]
    assert body["created_at"] and body["updated_at"]


def test_explicit_dates_are_kept(api):
    body = create(api, query={"from": "2026-07-01", "to": "2026-07-31", **QUERY}).json()
    assert (body["query"]["from"], body["query"]["to"]) == ("2026-07-01", "2026-07-31")


def test_list_get_rename_update_and_delete(api):
    first = create(api, "Primera").json()
    second = create(api, "Segunda").json()
    listed = api.get("/api/query/saved").json()["items"]
    assert [q["name"] for q in listed] == ["Segunda", "Primera"]

    assert api.get(f"/api/query/saved/{first['id'].lower()}").json()["name"] == "Primera"
    renamed = api.patch(f"/api/query/saved/{first['id']}", json={"name": "Renombrada"}).json()
    assert renamed["name"] == "Renombrada" and renamed["query"] == first["query"]
    new_query = {"root": {"op": "or", "conditions": [{"field": "sentiment", "operator": "lt", "value": -0.3}]}}
    updated = api.patch(f"/api/query/saved/{first['id']}", json={"query": new_query}).json()
    assert updated["query"]["root"]["op"] == "or" and updated["name"] == "Renombrada"
    assert api.get("/api/query/saved").json()["items"][0]["id"] == first["id"]

    assert api.delete(f"/api/query/saved/{second['id']}").status_code == 204
    assert api.get(f"/api/query/saved/{second['id']}").status_code == 404
    assert [q["id"] for q in api.get("/api/query/saved").json()["items"]] == [first["id"]]


def test_saved_queries_are_private_to_their_owner(api):
    mine = create(api).json()
    other = headers_for("analista@bancohorizonte.demo")
    assert api.get("/api/query/saved", headers=other).json()["items"] == []
    for method in ("get", "delete"):
        assert getattr(api, method)(f"/api/query/saved/{mine['id']}", headers=other).status_code == 404
    assert api.patch(f"/api/query/saved/{mine['id']}", json={"name": "x"}, headers=other).status_code == 404
    assert api.get(f"/api/query/saved/{mine['id']}").status_code == 200


@pytest.mark.parametrize("name", ["", "   ", "x" * 81])
def test_invalid_name_returns_422(api, name):
    assert create(api, name=name).status_code == 422


def test_invalid_query_returns_422_with_paths(api):
    response = create(api, query={"root": {"op": "and", "conditions": [{"field": "color", "operator": "is", "value": 1}]}})
    assert response.status_code == 422
    assert response.json()["detail"][0]["path"] == "root.conditions[0]"
    saved = create(api).json()
    bad = api.patch(f"/api/query/saved/{saved['id']}", json={"query": {"root": {"op": "nand"}}})
    assert bad.status_code == 422


@pytest.mark.parametrize("value", ["no-es-un-id", ids.stable_id(ids.CONVERSATION, "x")])
def test_malformed_or_foreign_ids_return_404(api, value):
    assert api.get(f"/api/query/saved/{value}").status_code == 404


def test_viewer_cannot_use_saved_queries(api):
    response = api.get("/api/query/saved", headers=headers_for("viewer@bancohorizonte.demo"))
    assert response.status_code == 403
