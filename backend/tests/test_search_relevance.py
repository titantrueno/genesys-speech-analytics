import re

import pytest

from app.data.store import get_dataset
from app.text import normalize_text
from app.search.engine import best_per_conversation
from app.search.synonyms import SYNONYMS, expand
from app.search.text import tokenize
from app.search.tfidf import TfidfEngine
from tests.search_relevance import LABELLED_QUERIES, PARAPHRASE_PAIRS

TOP = 5
# «no» y «sin» aparecen en los guiones de todos los main topics: no cuentan como palabras con contenido.
NON_CONTENT = {"no", "sin"}


@pytest.fixture(scope="module")
def topics():
    return {c.id: c.analysis.main_topic for c in get_dataset()}


@pytest.fixture(scope="module")
def engine():
    return TfidfEngine(get_dataset())


@pytest.fixture(scope="module")
def plain_engine():
    return TfidfEngine(get_dataset(), synonyms=())


def top_hits(engine, text):
    """Fragmento representativo de las 5 mejores conversaciones, como `group=conversation`."""
    return best_per_conversation(engine.search(text))[:TOP]


def top_topics(engine, topics, text) -> list[str]:
    return [topics[hit.fragment.conversation_id] for hit in top_hits(engine, text)]


def topic_words(topic: str) -> set[str]:
    """Palabras de los turnos reales del main topic: incluye los valores con que se rellenan los guiones."""
    return {w for c in get_dataset() if c.analysis.main_topic == topic for t in c.turns for w in tokenize(t.text)}


def test_there_are_enough_pairs_and_labelled_queries():
    assert len(PARAPHRASE_PAIRS) >= 8
    assert len(LABELLED_QUERIES) >= 20


@pytest.mark.parametrize("phrase,topic", PARAPHRASE_PAIRS)
def test_pair_shares_no_content_word_with_its_topic(phrase, topic):
    assert set(tokenize(phrase)) - NON_CONTENT
    assert (set(tokenize(phrase)) - NON_CONTENT) & topic_words(topic) == set()


@pytest.mark.parametrize("phrase,topic", PARAPHRASE_PAIRS)
def test_pair_is_found_only_thanks_to_the_dictionary(engine, plain_engine, topics, phrase, topic):
    assert topic in top_topics(engine, topics, phrase)
    assert topic not in top_topics(plain_engine, topics, phrase)


def test_labelled_queries_reach_eighty_percent_in_top_five(engine, topics):
    found = [topic in top_topics(engine, topics, query) for query, topic in LABELLED_QUERIES]
    rate = sum(found) / len(found)
    missed = [q for (q, _), ok in zip(LABELLED_QUERIES, found) if not ok]
    print(f"\n[relevancia] {sum(found)}/{len(found)} = {rate:.0%} en el top {TOP}; fallan: {missed}")
    assert rate >= 0.8


def test_expansion_reports_added_terms_and_ignores_unrelated_text():
    assert expand("zzqx wwvk") == []
    added = expand("me han cobrado algo que no he comprado")
    assert added and all(isinstance(term, str) for term in added)
    assert "cobrado" not in [normalize_text(t) for t in added]


def test_expansion_is_exposed_by_the_engine(engine, plain_engine):
    assert engine.expansions("la máquina no soltó los billetes") == expand("la máquina no soltó los billetes")
    assert plain_engine.expansions("la máquina no soltó los billetes") == []


def test_every_dictionary_group_reaches_the_corpus():
    corpus = normalize_text(" ".join(t.text for c in get_dataset() for t in c.turns))
    for group in SYNONYMS:
        assert len(group) >= 2, group
        patterns = [re.compile(r"\b" + normalize_text(e).replace("*", r"\w*") + r"\b") for e in group]
        assert any(p.search(corpus) for p in patterns), f"grupo sin términos en el corpus: {group}"


CLOSING = "Resumiendo, hemos revisado su consulta sobre"


def test_closing_template_is_rarely_the_best_fragment(engine):
    """Criterio 18: el fragmento representativo prioriza lo que dice el cliente sobre la despedida plantillada."""
    hits = [hit for query, _ in LABELLED_QUERIES + PARAPHRASE_PAIRS for hit in top_hits(engine, query)]
    share = sum(CLOSING in hit.fragment.text for hit in hits) / len(hits)
    print(f"\n[despedidas] {share:.0%} de los mejores fragmentos del top {TOP}")
    assert share < 0.10
