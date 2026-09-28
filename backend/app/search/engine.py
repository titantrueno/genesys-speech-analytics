"""Interfaz del motor de búsqueda semántica: la API solo depende de `SearchEngine` (ver ADR-005)."""
from collections.abc import Collection
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.models import Conversation


@dataclass(frozen=True)
class Fragment:
    conversation_id: str
    start_turn: int
    end_turn: int
    turns: tuple[int, ...]
    text: str


@dataclass(frozen=True)
class Hit:
    """`score` ordena y filtra; `focus` indica cuánto representa el fragmento a su conversación (criterio 18)."""
    fragment: Fragment
    score: float
    focus: float = 0.0


@runtime_checkable
class SearchEngine(Protocol):
    fragments: list[Fragment]

    def search(self, text: str, candidates: Collection[str] | None = None) -> list[Hit]: ...

    def expansions(self, text: str) -> list[str]:
        """Términos que el motor añade a la consulta (vacío en un motor sin expansión)."""
        ...

    def similar(self, conversation_id: str, k: int = 10) -> list[tuple[str, float]]: ...


FRAGMENT_TURNS = 3
FRAGMENT_STEP = 2


def build_fragments(conv: Conversation) -> list[Fragment]:
    """Ventanas de 3 turnos con paso 2; los turnos de `sistema` no se indexan."""
    indexed = [i for i, turn in enumerate(conv.turns) if turn.speaker != "sistema"]
    fragments = []
    for pos in range(0, len(indexed), FRAGMENT_STEP):
        window = tuple(indexed[pos:pos + FRAGMENT_TURNS])
        text = "\n".join(conv.turns[i].text for i in window)
        fragments.append(Fragment(conv.id, window[0], window[-1], window, text))
        if pos + FRAGMENT_TURNS >= len(indexed):
            break
    return fragments


def best_per_conversation(hits: list[Hit]) -> list[Hit]:
    """Una entrada por conversación, en el orden de su mejor `score`, con el fragmento de mayor `focus`.

    `hits` debe venir ordenado por `score` descendente; ante empate de `focus` gana el de mayor `score`.
    """
    groups: dict[str, list[Hit]] = {}
    for hit in hits:
        groups.setdefault(hit.fragment.conversation_id, []).append(hit)
    result = []
    for group in groups.values():
        representative = max(group, key=lambda h: h.focus)
        result.append(Hit(representative.fragment, group[0].score, representative.focus))
    return result
