"""Escritura de los campos del análisis completo en PostgreSQL (FE014, T1; criterios 9, 10 y 11).

Amplía la de FE013 (`test_flow_fields_pg.py`): escalares, listas, checks y entidades combinados clave a clave, y el
sentimiento, que solo se escribe si Genesys no lo da.
"""
import psycopg
import pytest

from ingestion.runs import RunExecutor, create_run
from tests.ingestion_helpers import DAY_END, DAY_START, client_factory, create_flow, make_fake
from tests.test_flow_fields_pg import RUN_ID, _ids, service  # noqa: F401  (fixture)

pytestmark = pytest.mark.pg

COLUMNS = "status, resolution, csat, effort, churn_risk, sentiment, secondary_topics, keywords, compliance, entities, llm_meta"


def _row(pg_url, cid) -> dict:
    with psycopg.connect(pg_url) as conn:
        row = conn.execute(f"SELECT {COLUMNS} FROM analysis WHERE conversation_id = %s", (cid,)).fetchone()
    return dict(zip([c.strip() for c in COLUMNS.split(",")], row))


def _sql(pg_url, statement, params=()):
    with psycopg.connect(pg_url) as conn:
        conn.execute(statement, params)


def _post(service, items, overwrite=False):
    return service.post("/analysis/fields", json={"run_id": RUN_ID, "provider": "gemini",
                                                  "model": "gemini-3.5-flash-lite", "overwrite": overwrite,
                                                  "items": items})


def _write(service, cid, values, overwrite=False) -> dict:
    response = _post(service, [{"conversation_id": cid, "values": values}], overwrite)
    assert response.status_code == 200, response.text
    [result] = response.json()["results"]
    return result


@pytest.fixture
def cid(service, pg_url):
    cid = _ids(pg_url, 1)[0]
    _sql(pg_url, "UPDATE conversation SET customer_sentiment = NULL WHERE id = %s", (cid,))
    return cid


# Un valor por familia de destino, el que hay después de escribir y el que lo sustituye con «Sobrescribir».
CASES = [
    ("resolution", "resuelta", "resolution", "resuelta", "escalada"),
    ("churn_risk", "alto", "churn_risk", "alto", "bajo"),
    ("csat", 4, "csat", 4.0, 2),
    ("effort", 2.5, "effort", 2.5, 5),
    ("sentiment", -0.4, "sentiment", pytest.approx(-0.4), 0.5),
    ("secondary_topics", ["fraude", "app"], "secondary_topics", ["fraude", "app"], ["cajeros"]),
    ("keywords", ["tarjeta", "cargo"], "keywords", ["tarjeta", "cargo"], ["cajero"]),
]


@pytest.mark.parametrize("target, value, column, stored, other", CASES, ids=[c[0] for c in CASES])
def test_each_field_is_written_kept_and_overwritten(service, pg_url, cid, target, value, column, stored, other):
    assert _write(service, cid, {target: value})["outcomes"] == {target: "escrito"}
    row = _row(pg_url, cid)
    assert row[column] == stored
    assert row["status"] == "pendiente"
    assert {k: v for k, v in row["llm_meta"][target].items() if k != "at"} == {
        "provider": "gemini", "model": "gemini-3.5-flash-lite", "run_id": RUN_ID}
    kept = _write(service, cid, {target: other})
    assert kept["outcomes"] == {target: "omitido"}
    assert kept["reasons"] == {target: "Ya tenía valor"}
    assert _row(pg_url, cid)[column] == stored
    assert _write(service, cid, {target: other}, overwrite=True)["outcomes"] == {target: "escrito"}
    assert _row(pg_url, cid)[column] == (pytest.approx(other) if isinstance(other, float) else other)


def test_an_empty_list_counts_as_empty(service, pg_url, cid):
    _sql(pg_url, "UPDATE analysis SET keywords = '[]' WHERE conversation_id = %s", (cid,))
    assert _write(service, cid, {"keywords": ["tarjeta"]})["outcomes"] == {"keywords": "escrito"}


def test_checks_are_merged_key_by_key(service, pg_url, cid):
    outcome = _write(service, cid, {"compliance:saludo": True, "compliance:despedida": None})
    assert outcome["outcomes"] == {"compliance:saludo": "escrito", "compliance:despedida": "escrito"}
    # `null` (no aplica) es un valor: la clave existe y ya no está vacía.
    kept = _write(service, cid, {"compliance:despedida": False, "compliance:identificacion": False})
    assert kept["outcomes"] == {"compliance:despedida": "omitido", "compliance:identificacion": "escrito"}
    row = _row(pg_url, cid)
    assert row["compliance"] == {"saludo": True, "despedida": None, "identificacion": False}
    assert set(row["llm_meta"]) == {"compliance:saludo", "compliance:despedida", "compliance:identificacion"}
    _write(service, cid, {"compliance:saludo": False}, overwrite=True)
    assert _row(pg_url, cid)["compliance"] == {"saludo": False, "despedida": None, "identificacion": False}


def test_entities_are_merged_key_by_key(service, pg_url, cid):
    _write(service, cid, {"entity:importe": "120 €"})
    kept = _write(service, cid, {"entity:importe": "99 €", "entity:producto": "Tarjeta oro"})
    assert kept["outcomes"] == {"entity:importe": "omitido", "entity:producto": "escrito"}
    assert _row(pg_url, cid)["entities"] == {"importe": "120 €", "producto": "Tarjeta oro"}
    _write(service, cid, {"entity:importe": "99 €"}, overwrite=True)
    assert _row(pg_url, cid)["entities"] == {"importe": "99 €", "producto": "Tarjeta oro"}


def test_sentiment_is_not_written_when_genesys_gives_it(service, pg_url, cid):
    _sql(pg_url, "UPDATE conversation SET customer_sentiment = 0.3 WHERE id = %s", (cid,))
    for overwrite in (False, True):
        result = _write(service, cid, {"sentiment": -0.8, "resolution": "resuelta"}, overwrite)
        assert result["outcomes"]["sentiment"] == "omitido"
        assert result["reasons"] == {"sentiment": "Genesys ya da el sentimiento"}
    row = _row(pg_url, cid)
    assert row["sentiment"] is None and "sentiment" not in row["llm_meta"]
    assert row["resolution"] == "resuelta"


def test_a_whole_answer_is_written_in_one_go(service, pg_url, cid):
    values = {"summary": "Resumen.", "main_topic": "cajeros", "resolution": "escalada", "csat": 3, "effort": 4,
              "churn_risk": "medio", "sentiment": 0.1, "secondary_topics": ["fraude"], "keywords": ["cajero"],
              "compliance:saludo": True, "entity:importe": "50 €"}
    result = _write(service, cid, values)
    assert set(result["outcomes"].values()) == {"escrito"}
    assert result["reasons"] == {}
    row = _row(pg_url, cid)
    assert (row["resolution"], row["csat"], row["compliance"], row["entities"]) == (
        "escalada", 3.0, {"saludo": True}, {"importe": "50 €"})
    assert len(row["llm_meta"]) == len(values)


@pytest.mark.parametrize("values", [
    {"status": "completo"},
    {"compliance:": True},
    {"compliance:Saludo; DROP": True},
    {"entity:color": "rojo"},
    {"csat": "cuatro"},
    {"keywords": "tarjeta"},
    {"keywords": ["tarjeta", 3]},
    {"compliance:saludo": "cumple"},
    {"resolution": ""},
    {"entity:importe": "  "},
    {"sentiment": None},
], ids=str)
def test_unknown_targets_and_wrong_types_are_refused(service, pg_url, cid, values):
    response = _post(service, [{"conversation_id": cid, "values": values}])
    assert response.status_code == 422, response.text
    row = _row(pg_url, cid)
    assert row["llm_meta"] == {} and row["compliance"] is None


def test_redownloading_with_overwrite_erases_the_new_fields(service, pg_url, cid):
    _write(service, cid, {"resolution": "resuelta", "sentiment": 0.2, "keywords": ["x"], "compliance:saludo": True,
                          "entity:importe": "1 €"})
    flow_id = create_flow(pg_url, overwrite=True)
    run_id = create_run(pg_url, flow_id, "manual", DAY_START, DAY_END, ["voz", "chat"])
    RunExecutor(pg_url, client_factory(make_fake())).execute(run_id)
    row = _row(pg_url, cid)
    assert row == {**row, "resolution": None, "sentiment": None, "keywords": None, "compliance": None,
                   "entities": None, "llm_meta": {}}
