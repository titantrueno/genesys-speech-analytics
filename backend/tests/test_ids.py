import random
import re
import uuid
from pathlib import Path

import pytest

from app import ids

ID_RE = re.compile(r"^1[A-Z]{2}-[0-9A-F]{8}-[0-9A-F]{4}-[45][0-9A-F]{3}-[89AB][0-9A-F]{3}-[0-9A-F]{12}$")
REGISTRY = Path(__file__).resolve().parents[2] / "vault" / "ingenieria" / "registro-de-identificadores.md"


def uuid_part(value: str) -> uuid.UUID:
    return uuid.UUID(value.split("-", 1)[1])


def test_new_id_is_prefixed_uppercase_uuid4():
    value = ids.new_id(ids.CONVERSATION, random.Random(1))
    assert ID_RE.match(value)
    assert value.startswith("1CO-")
    assert value == value.upper()
    parsed = uuid_part(value)
    assert parsed.version == 4
    assert parsed.variant == uuid.RFC_4122


def test_new_id_is_deterministic_per_seed():
    a = [ids.new_id(ids.CUSTOMER, random.Random(7)) for _ in range(2)]
    assert a[0] == a[1]
    assert ids.new_id(ids.CUSTOMER, random.Random(8)) != a[0]
    rng = random.Random(7)
    assert ids.new_id(ids.CUSTOMER, rng) != ids.new_id(ids.CUSTOMER, rng)


def test_stable_id_is_uuid5_and_stable_by_name():
    first = ids.stable_id(ids.AGENT, "Sergio Molina")
    assert ID_RE.match(first) and first.startswith("1AG-")
    assert uuid_part(first).version == 5
    assert ids.stable_id(ids.AGENT, "Sergio Molina") == first
    assert ids.stable_id(ids.AGENT, "Irene Vidal") != first


@pytest.mark.parametrize("prefix", ["1ZZ", "CNV", "1co", ""])
def test_unknown_prefix_is_rejected(prefix):
    with pytest.raises(ValueError):
        ids.new_id(prefix, random.Random(1))
    with pytest.raises(ValueError):
        ids.stable_id(prefix, "x")


def test_is_valid_and_normalize():
    value = ids.new_id(ids.CONVERSATION, random.Random(3))
    assert ids.is_valid(value)
    assert ids.is_valid(value, ids.CONVERSATION)
    assert not ids.is_valid(value, ids.CUSTOMER)
    assert not ids.is_valid(value.lower())
    assert ids.normalize(value.lower()) == value
    for bad in ["", "CNV-000001", "1CO-123", "1ZZ-" + value[4:], value[:-1], value + "0", value.replace("-", "", 1)]:
        assert not ids.is_valid(bad), bad


def test_prefixes_match_vault_registry():
    rows = re.findall(r"^\|\s*`(1[A-Z]{2})`\s*\|\s*([^|]+?)\s*\|", REGISTRY.read_text(encoding="utf-8"), re.M)
    assert rows, "el registro del vault no contiene la tabla de prefijos"
    assert dict(rows) == ids.PREFIXES
