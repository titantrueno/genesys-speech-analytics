import random
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app import ids

_rng = random.SystemRandom()


@dataclass
class SavedQuery:
    id: str
    owner_id: str
    name: str
    query: dict
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "query": self.query,
                "created_at": self.created_at.isoformat(), "updated_at": self.updated_at.isoformat()}


class SavedQueryStore:
    def __init__(self):
        self._items: dict[str, SavedQuery] = {}

    def list_for(self, owner_id: str) -> list[SavedQuery]:
        items = [q for q in self._items.values() if q.owner_id == owner_id]
        return sorted(items, key=lambda q: q.updated_at, reverse=True)

    def get(self, owner_id: str, query_id: str) -> SavedQuery | None:
        item = self._items.get(ids.normalize(query_id))
        return item if item and item.owner_id == owner_id else None

    def create(self, owner_id: str, name: str, query: dict) -> SavedQuery:
        item = SavedQuery(ids.new_id(ids.SAVED_QUERY, _rng), owner_id, name, query)
        self._items[item.id] = item
        return item

    def update(self, item: SavedQuery, name: str | None, query: dict | None) -> SavedQuery:
        if name is not None:
            item.name = name
        if query is not None:
            item.query = query
        item.updated_at = datetime.now(timezone.utc)
        return item

    def delete(self, item: SavedQuery) -> None:
        del self._items[item.id]


_store = SavedQueryStore()


def get_saved_store() -> SavedQueryStore:
    return _store


def reset_saved_store() -> None:
    global _store
    _store = SavedQueryStore()
