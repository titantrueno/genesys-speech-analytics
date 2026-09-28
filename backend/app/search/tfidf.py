"""Motor TF-IDF en Python puro: palabras y n-gramas de caracteres, similitud coseno e índice invertido."""
import math
import re
from array import array
from collections import Counter, defaultdict
from collections.abc import Collection, Iterable

from app.models import Conversation
from app.query.fields import normalize_text
from app.search.engine import Fragment, Hit, build_fragments

# «no» y «sin» cambian el sentido («no reconozco»), así que no son palabras vacías.
STOPWORDS = {
    "a", "al", "algo", "con", "de", "del", "el", "en", "es", "esa", "ese", "eso", "esta", "este", "esto", "ha",
    "han", "he", "la", "las", "le", "les", "lo", "los", "me", "mi", "mis", "o", "para", "pero", "por", "que",
    "se", "su", "sus", "te", "tu", "un", "una", "unos", "unas", "y", "ya", "yo",
}
NGRAM_SIZES = (3, 4, 5)
WORD_WEIGHT = 0.5
_WORD_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return [w for w in _WORD_RE.findall(normalize_text(text)) if w not in STOPWORDS]


def char_ngrams(words: Iterable[str]) -> Iterable[str]:
    for word in words:
        if word.isdigit():
            continue
        padded = f" {word} "
        for size in NGRAM_SIZES:
            for start in range(len(padded) - size + 1):
                yield padded[start:start + size]


class _SparseIndex:
    """Vectores TF-IDF (TF sublineal, norma L2) con índice invertido para el coseno.

    El IDF se calcula por conversación y sin sumar 1: el texto presente en casi todas las conversaciones
    (saludo, verificación, despedida) pesa casi cero aunque aparezca en pocos fragmentos de cada una.
    """

    def __init__(self, documents: list[Counter], groups: list[str]):
        total = len(set(groups))
        seen = {(term, group) for counts, group in zip(documents, groups) for term in counts}
        df = Counter(term for term, _ in seen)
        self.idf = {term: math.log((1 + total) / (1 + count)) for term, count in df.items()}
        # Postings como pares de arrays compactos (documento, peso): una lista de tuplas ocupaba unos 300 MB.
        self.postings: dict[str, tuple[array, array]] = {}
        for doc, counts in enumerate(documents):
            for term, weight in self.vector(counts).items():
                docs, weights = self.postings.setdefault(term, (array("I"), array("f")))
                docs.append(doc)
                weights.append(weight)

    def vector(self, counts: Counter) -> dict[str, float]:
        raw = {t: (1 + math.log(c)) * self.idf[t] for t, c in counts.items() if self.idf.get(t)}
        norm = math.sqrt(sum(w * w for w in raw.values()))
        return {t: w / norm for t, w in raw.items()} if norm else {}

    def scores(self, vector: dict[str, float]) -> dict[int, float]:
        acc: dict[int, float] = defaultdict(float)
        for term, weight in vector.items():
            docs, weights = self.postings.get(term, ((), ()))
            for doc, doc_weight in zip(docs, weights):
                acc[doc] += weight * doc_weight
        return acc

    def size(self) -> tuple[int, int]:
        return len(self.postings), sum(len(docs) for docs, _ in self.postings.values())


class _Blocks:
    """Coseno combinado de palabras y n-gramas: `WORD_WEIGHT·cos_palabras + (1 − WORD_WEIGHT)·cos_ngramas`."""

    def __init__(self, texts: list[str], groups: list[str]):
        words = [tokenize(t) for t in texts]
        self.words = _SparseIndex([Counter(w) for w in words], groups)
        self.chars = _SparseIndex([Counter(char_ngrams(w)) for w in words], groups)

    def scores(self, text: str) -> dict[int, float]:
        words = tokenize(text)
        combined: dict[int, float] = defaultdict(float)
        for index, counts, weight in ((self.words, Counter(words), WORD_WEIGHT),
                                      (self.chars, Counter(char_ngrams(words)), 1 - WORD_WEIGHT)):
            for doc, score in index.scores(index.vector(counts)).items():
                combined[doc] += weight * score
        return combined


def _ranked(scores: dict[int, float]) -> list[tuple[int, float]]:
    return sorted(((doc, min(score, 1.0)) for doc, score in scores.items() if score > 0), key=lambda d: (-d[1], d[0]))


class TfidfEngine:
    def __init__(self, conversations: list[Conversation]):
        self.fragments: list[Fragment] = [f for conv in conversations for f in build_fragments(conv)]
        self._fragments = _Blocks([f.text for f in self.fragments], [f.conversation_id for f in self.fragments])
        self._conversation_ids = [conv.id for conv in conversations]
        self._conversation_texts = {
            conv.id: "\n".join(t.text for t in conv.turns if t.speaker != "sistema") for conv in conversations
        }
        self._conversations = _Blocks(list(self._conversation_texts.values()), self._conversation_ids)

    def search(self, text: str, candidates: Collection[str] | None = None) -> list[Hit]:
        ranked = _ranked(self._fragments.scores(text))
        hits = (Hit(self.fragments[doc], score) for doc, score in ranked)
        return [h for h in hits if candidates is None or h.fragment.conversation_id in candidates]

    def similar(self, conversation_id: str, k: int = 10) -> list[tuple[str, float]]:
        text = self._conversation_texts[conversation_id]
        ranked = _ranked(self._conversations.scores(text))
        return [(self._conversation_ids[doc], score) for doc, score in ranked
                if self._conversation_ids[doc] != conversation_id][:k]

    def stats(self) -> dict:
        word_terms, word_postings = self._fragments.words.size()
        char_terms, char_postings = self._fragments.chars.size()
        return {
            "conversations": len(self._conversation_ids), "fragments": len(self.fragments),
            "word_terms": word_terms, "char_terms": char_terms, "postings": word_postings + char_postings,
        }
