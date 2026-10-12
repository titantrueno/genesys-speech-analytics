"""Índice de búsqueda en caliente (FE012, criterio 11): se reconstruye con datos nuevos sin dejar de dar servicio."""
import threading

from app.data.repository import DataUnavailable
from app.search.index import SearchIndex


class FakeRepository:
    origin = "falso"

    def __init__(self):
        self.current = 1
        self.items = ["a"]

    def version(self):
        return self.current

    def conversations(self):
        return list(self.items)


class Gate:
    """Constructor de índices que se queda esperando hasta que el test lo libera."""

    def __init__(self):
        self.started, self.release, self.calls = threading.Event(), threading.Event(), []
        self.block = False

    def __call__(self, conversations):
        self.calls.append(list(conversations))
        if self.block:
            self.started.set()
            assert self.release.wait(5)
        return ("indice", tuple(conversations))


def make(block=False):
    repo, gate = FakeRepository(), Gate()
    gate.block = block
    return repo, gate, SearchIndex(gate, repository=lambda: repo)


def test_the_first_use_builds_inline_and_the_same_version_never_rebuilds():
    repo, gate, index = make()
    assert index.engine() == ("indice", ("a",))
    index.engine(), index.engine()
    index.wait()
    assert len(gate.calls) == 1


def test_new_data_triggers_a_rebuild_and_the_previous_index_serves_until_it_is_ready():
    repo, gate, index = make()
    index.engine()
    gate.block = True
    repo.current, repo.items = 2, ["a", "b"]
    assert index.engine() == ("indice", ("a",))  # sigue el anterior, sin esperar
    assert gate.started.wait(5)
    assert index.engine() == ("indice", ("a",))  # también mientras construye
    gate.release.set()
    index.wait()
    assert index.engine() == ("indice", ("a", "b"))


def test_rebuilds_are_grouped_while_one_is_running():
    repo, gate, index = make()
    index.engine()
    gate.block = True
    repo.current, repo.items = 2, ["a", "b"]
    for _ in range(5):
        index.engine()
    assert gate.started.wait(5)
    repo.current, repo.items = 3, ["a", "b", "c"]
    for _ in range(5):
        index.engine()
    assert len(gate.calls) == 2  # la inicial y una sola reconstrucción en curso
    gate.release.set()
    index.wait()
    gate.block = False
    assert index.engine() == ("indice", ("a", "b"))  # la versión 3 aún no está: sigue el anterior...
    index.wait()
    assert index.engine() == ("indice", ("a", "b", "c"))  # ...y una nueva reconstrucción la recoge
    assert len(gate.calls) == 3


def test_a_failed_rebuild_keeps_serving_the_previous_index_and_is_retried():
    repo, gate, index = make()
    index.engine()
    repo.current = 2
    original = repo.conversations
    repo.conversations = lambda: (_ for _ in ()).throw(DataUnavailable("caído"))
    assert index.engine() == ("indice", ("a",))
    index.wait()
    repo.conversations = original
    assert index.engine() == ("indice", ("a",))
    index.wait()
    assert index.engine() == ("indice", ("a",))
    assert len(gate.calls) == 2


def test_each_origin_has_its_own_index():
    repo, gate, index = make()
    other = FakeRepository()
    other.origin, other.items = "otro", ["z"]
    current = [repo]
    index = SearchIndex(gate, repository=lambda: current[0])
    assert index.engine() == ("indice", ("a",))
    current[0] = other
    assert index.engine() == ("indice", ("z",))  # primer uso del origen: se construye en línea
    current[0] = repo
    assert index.engine() == ("indice", ("a",))  # vuelve al suyo sin reconstruir
    index.wait()
    assert len(gate.calls) == 2
