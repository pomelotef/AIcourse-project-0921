from datetime import date, timedelta

from ..models import ActionItem, utcnow

_STATE_ORDER = {"in_progress": 0, "open": 1, "done": 2, "canceled": 3}
_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def action_sort_key(a: ActionItem):
    """Unfinished first, then by priority, then earliest due date (no due date last)."""
    return (
        _STATE_ORDER.get(a.state, 9),
        _PRIORITY_ORDER.get(a.priority, 9),
        a.due_date or date.max,
        a.id,
    )


def is_overdue(a: ActionItem, today: date) -> bool:
    return a.state in ("open", "in_progress") and a.due_date is not None and a.due_date < today


def taipei_today() -> date:
    """Due dates are calendar dates; the team and pilot users are in Taiwan (UTC+8)."""
    return (utcnow() + timedelta(hours=8)).date()
