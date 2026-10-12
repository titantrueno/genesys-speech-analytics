"""Recontacto de 7 días (FCR) con clientes sin identificar (FE012, /test)."""
from datetime import datetime, timedelta, timezone

from app.data.repository import followup_map
from app.models import Analysis, Conversation

START = datetime(2026, 10, 12, 9, tzinfo=timezone.utc)


def conv(n: int, customer: str | None, hours: int) -> Conversation:
    analysis = Analysis(summary="", main_topic=None, secondary_topics=[], sentiment=None, sentiment_timeline=[],
                        resolution=None, csat=None, effort=None, churn_risk=None, compliance={}, entities=[],
                        keywords=[], pending=True)
    return Conversation(id=f"1CO-{n}", channel="chat", started_at=START + timedelta(hours=hours), duration_s=10,
                        queue_id=None, queue=None, agent_id=None, agent=None, customer_id=customer, turns=[],
                        analysis=analysis)


def test_conversations_without_a_customer_are_never_each_others_followups():
    found = followup_map([conv(1, None, 0), conv(2, None, 1), conv(3, None, 2)])
    assert found == {"1CO-1": False, "1CO-2": False, "1CO-3": False}


def test_the_same_customer_within_seven_days_is_a_followup_and_after_that_is_not():
    found = followup_map([conv(1, "1CU-A", 0), conv(2, "1CU-A", 24), conv(3, "1CU-B", 0), conv(4, "1CU-A", 24 * 9)])
    assert found == {"1CO-1": True, "1CO-2": False, "1CO-3": False, "1CO-4": False}
