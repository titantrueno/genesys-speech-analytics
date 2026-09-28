import pytest
from fastapi.testclient import TestClient

from app import auth
from app.data.catalog import QUEUE_IDS
from app.data.store import conversation_index, get_dataset
from app.main import app
from app.routers import search as search_router
from app.services.listing import list_item


def similar(api, conversation_id):
    return api.get(f"/api/search/similar/{conversation_id}")


def test_returns_ten_sorted_neighbours_without_itself(api):
    origin = get_dataset()[100]
    response = similar(api, origin.id)
    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == origin.id
    results = body["results"]
    assert len(results) == 10
    ids = [r["conversation_id"] for r in results]
    assert origin.id not in ids and len(set(ids)) == 10
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert all(0 < s <= 1 and round(s, 4) == s for s in scores)
    for r in results:
        conv = conversation_index()[r["conversation_id"]]
        assert r["conversation"] == {**list_item(conv), "started_at": conv.started_at.isoformat()}


def test_neighbours_share_the_main_topic(api):
    by_id = conversation_index()
    for origin in get_dataset()[::50]:
        topics = [by_id[r["conversation_id"]].analysis.main_topic for r in similar(api, origin.id).json()["results"]]
        assert sum(t == origin.analysis.main_topic for t in topics) >= 8, (origin.id, origin.analysis.main_topic, topics)


def test_lowercase_identifier_is_accepted(api):
    origin = get_dataset()[5]
    assert similar(api, origin.id.lower()).json()["conversation_id"] == origin.id


@pytest.mark.parametrize("conversation_id", [
    "1CO-00000000-0000-4000-8000-000000000000",
    "no-es-un-id",
    QUEUE_IDS["Tarjetas"],
])
def test_unknown_malformed_or_other_type_returns_404(api, conversation_id):
    assert similar(api, conversation_id).status_code == 404


def test_uses_the_injected_engine(api):
    origin, neighbour = get_dataset()[0], get_dataset()[1]

    class Fake:
        fragments = []

        def search(self, text, candidates=None):
            return []

        def expansions(self, text):
            return []

        def similar(self, conversation_id, k=10):
            assert (conversation_id, k) == (origin.id, 10)
            return [(neighbour.id, 0.5)]

    app.dependency_overrides[search_router.get_search_engine] = lambda: Fake()
    try:
        body = similar(api, origin.id).json()
    finally:
        app.dependency_overrides.clear()
    assert [(r["conversation_id"], r["score"]) for r in body["results"]] == [(neighbour.id, 0.5)]


def test_viewer_gets_403():
    viewer = auth.get_store().find_by_email("viewer@bancohorizonte.demo")
    response = TestClient(app).get(f"/api/search/similar/{get_dataset()[0].id}",
                                   headers={"Authorization": f"Bearer {auth.create_token(viewer)}"})
    assert response.status_code == 403
