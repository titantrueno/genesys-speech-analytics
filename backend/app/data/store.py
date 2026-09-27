import os
from bisect import bisect_right
from collections import defaultdict
from datetime import date, timedelta
from functools import cache

from app.data.generator import generate_dataset
from app.models import Conversation

FCR_WINDOW = timedelta(days=7)


def reference_date() -> date:
    configured = os.environ.get("DATA_REFERENCE_DATE")
    return date.fromisoformat(configured) if configured else date.today()


@cache
def get_dataset() -> list[Conversation]:
    return generate_dataset(seed=int(os.environ.get("DATA_SEED", "42")), reference_date=reference_date())


@cache
def followup_index() -> dict[str, bool]:
    """Indica si el cliente volvió a contactar en los 7 días siguientes a cada conversación."""
    by_customer = defaultdict(list)
    for conv in get_dataset():
        by_customer[conv.customer_id].append(conv.started_at)
    for starts in by_customer.values():
        starts.sort()
    index = {}
    for conv in get_dataset():
        starts = by_customer[conv.customer_id]
        nxt = bisect_right(starts, conv.started_at)
        index[conv.id] = nxt < len(starts) and starts[nxt] <= conv.started_at + FCR_WINDOW
    return index
