"""Motor de ejecución de flujos: sampling por método, prompt simulado y outputs (FE004, criterio 5)."""
import copy
import json
import random
from collections import Counter

import pytest

from app.data.catalog import MAIN_TOPICS
from app.data.store import get_dataset
from app.flows.model import OutputConfig, OutputFormat, PromptConfig, SamplingConfig, SchemaField
from app.flows.outputs import build_metric, build_report, build_table
from app.flows.prompting import MockPromptRunner, render_template, sentiment_class
from app.flows.sampling import candidates, draw_sample, proportional_quotas
from app.query.engine import run_query
from app.query.model import parse_query
from tests.flow_fixtures import days_ago

PERIOD = {"from": days_ago(57), "to": days_ago(1)}


def sampling(method: str, size: int, conditions: list | None = None, **extra) -> SamplingConfig:
    query = {**PERIOD, "root": {"op": "and", "conditions": conditions or []}}
    return SamplingConfig(query=query, method=method, size=size, **extra)


def prompt(output: dict, template: str = "Analiza {{summary}}", model: str = "mock-rapido", temperature: float = 0.2) -> PromptConfig:
    return PromptConfig(template=template, model=model, temperature=temperature, output=OutputFormat(**output))


def pool(config: SamplingConfig):
    return candidates(config)


# --- Sampling ---

def test_candidates_are_the_conversations_that_match_the_filters():
    config = sampling("aleatorio", 10, [{"field": "channel", "operator": "is", "value": "voz"}])
    expected = run_query(parse_query(copy.deepcopy(config.query)), get_dataset())
    assert [c.id for c in pool(config)] == [c.id for c in expected]
    assert all(c.channel == "voz" for c in pool(config))


@pytest.mark.parametrize("method, extra", [
    ("aleatorio", {}),
    ("estratificado", {"stratify_by": "cola"}),
    ("primeros_n", {"order_by": "fecha", "order": "desc"}),
])
def test_every_method_respects_the_filters_and_the_size(method, extra):
    config = sampling(method, 60, [{"field": "channel", "operator": "is", "value": "chat"}], **extra)
    available = pool(config)
    sample = draw_sample(available, config, seed=11)
    assert len(sample) == 60 < len(available)
    assert len({c.id for c in sample}) == 60
    assert {c.id for c in sample} <= {c.id for c in available}
    small = sampling(method, 1000, [{"field": "main_topic", "operator": "is", "value": "cajeros"}], **extra)
    assert len(draw_sample(pool(small), small, seed=11)) == len(pool(small)) < 1000


def test_random_sampling_is_reproducible_with_its_seed():
    config = sampling("aleatorio", 50)
    available = pool(config)
    first = [c.id for c in draw_sample(available, config, seed=1)]
    assert first == [c.id for c in draw_sample(available, config, seed=1)]
    assert first != [c.id for c in draw_sample(available, config, seed=2)]


def test_random_sampling_covers_the_whole_pool():
    config = sampling("aleatorio", 50)
    available = pool(config)
    picked = Counter(c.id for seed in range(200) for c in draw_sample(available, config, seed=seed))
    # Con 200 muestras de 50, cada conversación del intervalo debería salir alguna vez.
    assert len(picked) > 0.95 * len(available)


@pytest.mark.parametrize("stratum, key", [
    ("canal", lambda c: c.channel),
    ("cola", lambda c: c.queue_id),
    ("main_topic", lambda c: c.analysis.main_topic),
])
@pytest.mark.parametrize("size", [1, 37, 200])
def test_stratified_sampling_is_proportional_within_one(stratum, key, size):
    config = sampling("estratificado", size, stratify_by=stratum)
    available = pool(config)
    sample = draw_sample(available, config, seed=5)
    assert len(sample) == size
    totals, drawn = Counter(map(key, available)), Counter(map(key, sample))
    for group, total in totals.items():
        assert abs(drawn[group] - size * total / len(available)) < 1, (group, drawn[group], size * total / len(available))


def test_stratified_quotas_give_the_rest_to_the_largest_remainders():
    # Exactas: a = 0,3, b = 2,1 y c = 0,6. La unidad que falta va a c, no al primer estrato por orden.
    assert proportional_quotas({"a": 1, "b": 7, "c": 2}, 10, 3) == {"a": 0, "b": 2, "c": 1}
    assert proportional_quotas({"a": 5, "b": 5}, 10, 4) == {"a": 2, "b": 2}


ORDERINGS = {
    "fecha": lambda c: c.started_at,
    "duracion": lambda c: c.duration_s,
    "sentimiento": lambda c: c.analysis.sentiment,
    "csat": lambda c: c.analysis.csat,
}


@pytest.mark.parametrize("order_by", list(ORDERINGS))
@pytest.mark.parametrize("order", ["asc", "desc"])
def test_first_n_matches_an_independent_ordering(order_by, order):
    config = sampling("primeros_n", 25, order_by=order_by, order=order)
    available = pool(config)
    key = ORDERINGS[order_by]
    values = sorted((key(c) for c in available), reverse=order == "desc")[:25]
    sample = draw_sample(available, config, seed=0)
    assert [key(c) for c in sample] == values
    assert draw_sample(available, config, seed=99) == sample


# --- Prompt simulado ---

CONVERSATIONS = get_dataset()[:120]


def test_render_template_substitutes_every_variable():
    conv = CONVERSATIONS[0]
    text = render_template("{{transcripcion}}|{{ summary }}|{{main_topic}}|{{metadatos}}|{{resultado_anterior}}|{{otra}}",
                           conv, previous="Negativo")
    transcript, summary, topic, metadata, previous, unknown = text.split("|")
    assert conv.turns[0].text in transcript and conv.turns[-1].text in transcript
    assert summary == conv.analysis.summary
    assert topic == MAIN_TOPICS[conv.analysis.main_topic].name
    assert conv.queue in metadata and conv.channel in metadata.lower()
    assert previous == "Negativo"
    assert unknown == "{{otra}}"


@pytest.mark.parametrize("output", [
    {"type": "texto"},
    {"type": "etiqueta", "labels": ["Uno", "Dos", "Tres"]},
    {"type": "json", "fields": [{"name": "motivo", "type": "texto"}, {"name": "gravedad", "type": "numero"}]},
])
def test_mock_results_are_deterministic(output):
    config = prompt(output)
    first = [MockPromptRunner().run(config, conv, None) for conv in CONVERSATIONS]
    assert first == [MockPromptRunner().run(config, conv, None) for conv in CONVERSATIONS]
    assert len({json.dumps(r, sort_keys=True) for r in first}) > 1


def test_text_results_describe_the_conversation():
    for conv in CONVERSATIONS[:30]:
        result = MockPromptRunner().run(prompt({"type": "texto"}), conv, None)
        assert isinstance(result, str) and MAIN_TOPICS[conv.analysis.main_topic].name in result


def test_the_precise_model_gives_longer_answers():
    fast = [MockPromptRunner().run(prompt({"type": "texto"}), c, None) for c in CONVERSATIONS[:30]]
    precise = [MockPromptRunner().run(prompt({"type": "texto"}, model="mock-preciso"), c, None) for c in CONVERSATIONS[:30]]
    assert all(len(p) > len(f) for f, p in zip(fast, precise))


def test_chained_prompts_receive_the_previous_result():
    conv = CONVERSATIONS[0]
    config = prompt({"type": "texto"}, template="Explica {{resultado_anterior}}")
    assert "«Negativo»" in MockPromptRunner().run(config, conv, "Negativo")
    assert "«Negativo»" not in MockPromptRunner().run(config, conv, None)


def test_labels_are_always_from_the_list():
    rng = random.Random(3)
    words = ["Fraude", "Otro", "Positivo", "Negativo", "Resuelta", "ñandú", "Cargo no reconocido", "123", "Riesgo alto"]
    for conv in CONVERSATIONS:
        labels = rng.sample(words, rng.randint(2, 6))
        assert MockPromptRunner().run(prompt({"type": "etiqueta", "labels": labels}), conv, None) in labels


def test_a_label_that_names_the_main_topic_is_chosen():
    labels = [topic.name for topic in MAIN_TOPICS.values()]
    config = prompt({"type": "etiqueta", "labels": labels})
    for conv in CONVERSATIONS:
        assert MockPromptRunner().run(config, conv, None) == MAIN_TOPICS[conv.analysis.main_topic].name


@pytest.mark.parametrize("labels", [["Positivo", "Neutro", "Negativo"], ["negativo", "NEUTRO", "Positivo"]])
def test_a_label_that_names_the_sentiment_is_chosen(labels):
    config = prompt({"type": "etiqueta", "labels": labels})
    for conv in CONVERSATIONS:
        chosen = MockPromptRunner().run(config, conv, None)
        assert chosen.casefold() == sentiment_class(conv.analysis.sentiment)


def test_the_main_topic_wins_over_the_sentiment():
    for conv in CONVERSATIONS[:30]:
        labels = ["Negativo", "Positivo", "Neutro", MAIN_TOPICS[conv.analysis.main_topic].name]
        assert MockPromptRunner().run(prompt({"type": "etiqueta", "labels": labels}), conv, None) == labels[-1]


def test_exact_resolution_labels_are_not_confused():
    config = prompt({"type": "etiqueta", "labels": ["No resuelta", "Resuelta", "Escalada"]})
    expected = {"resuelta": "Resuelta", "no_resuelta": "No resuelta", "escalada": "Escalada"}
    for conv in CONVERSATIONS:
        assert MockPromptRunner().run(config, conv, None) == expected[conv.analysis.resolution]


def test_json_results_follow_the_schema():
    rng = random.Random(8)
    names = ["motivo", "gravedad", "urgente", "detalle", "puntuacion", "x1", "_raro"]
    for conv in CONVERSATIONS:
        fields = [{"name": n, "type": rng.choice(["texto", "numero", "booleano"])} for n in rng.sample(names, rng.randint(1, 5))]
        result = MockPromptRunner().run(prompt({"type": "json", "fields": fields}), conv, None)
        assert list(result) == [f["name"] for f in fields]
        for f in fields:
            expected = {"texto": str, "numero": (int, float), "booleano": bool}[f["type"]]
            assert isinstance(result[f["name"]], expected) and not (f["type"] == "numero" and isinstance(result[f["name"]], bool))


def test_known_json_fields_take_the_analysis_values():
    fields = [{"name": n, "type": t} for n, t in [
        ("main_topic", "texto"), ("sentimiento", "numero"), ("resolucion", "texto"), ("csat", "numero"),
        ("riesgo_abandono", "texto"), ("canal", "texto"), ("cola", "texto"), ("resumen", "texto")]]
    config = prompt({"type": "json", "fields": fields})
    for conv in CONVERSATIONS[:40]:
        result = MockPromptRunner().run(config, conv, None)
        assert result == {
            "main_topic": MAIN_TOPICS[conv.analysis.main_topic].name,
            "sentimiento": conv.analysis.sentiment,
            "resolucion": conv.analysis.resolution,
            "csat": conv.analysis.csat,
            "riesgo_abandono": conv.analysis.churn_risk,
            "canal": conv.channel,
            "cola": conv.queue,
            "resumen": conv.analysis.summary,
        }


# --- Outputs ---

def test_table_has_one_row_per_conversation_with_its_result():
    results = {c.id: f"r-{i}" for i, c in enumerate(CONVERSATIONS[:5])}
    table = build_table(CONVERSATIONS[:5], results)
    assert [row["conversation"]["id"] for row in table["rows"]] == [c.id for c in CONVERSATIONS[:5]]
    assert [row["result"] for row in table["rows"]] == ["r-0", "r-1", "r-2", "r-3", "r-4"]
    assert table["rows"][0]["conversation"]["main_topic_label"]


@pytest.mark.parametrize("aggregation", ["recuento", "porcentaje"])
def test_metric_counts_every_label_and_sums_to_the_sample(aggregation):
    labels = ["A", "B", "C", "Nunca"]
    convs = CONVERSATIONS[:7]
    results = {c.id: ["A", "B", "C"][i % 3] for i, c in enumerate(convs)}
    metric = build_metric(labels, convs, results, OutputConfig(kind="metrica", aggregation=aggregation, destination="x"))
    assert metric["aggregation"] == aggregation
    assert [i["label"] for i in metric["items"]] == labels
    assert [i["count"] for i in metric["items"]] == [3, 2, 2, 0]
    assert sum(i["count"] for i in metric["items"]) == metric["total"] == 7
    assert round(sum(i["percent"] for i in metric["items"]), 6) == 100.0
    assert [i["percent"] for i in metric["items"]] == [42.8, 28.6, 28.6, 0.0]


def test_report_summarizes_size_topics_sentiment_and_frequent_results():
    convs = CONVERSATIONS[:20]
    results = {c.id: "Negativo" if i % 4 else "Neutro" for i, c in enumerate(convs)}
    report = build_report(convs, results, OutputConfig(kind="informe", destination="Informe de fraude"))
    text = report["text"]
    top_topic = Counter(MAIN_TOPICS[c.analysis.main_topic].name for c in convs).most_common(1)[0][0]
    average = sum(c.analysis.sentiment for c in convs) / len(convs)
    assert "20 conversaciones" in text
    assert top_topic in text
    assert f"{average:.2f}".replace(".", ",") in text
    assert "«Negativo» (15)" in text
