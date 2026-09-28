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
    fragment: Fragment
    score: float


@runtime_checkable
class SearchEngine(Protocol):
    fragments: list[Fragment]

    def search(self, text: str, candidates: Collection[str] | None = None) -> list[Hit]: ...

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
