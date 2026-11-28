from sqlalchemy.orm import Session

from . import notify
from .models import ActivityEvent, Goal, utcnow


def short(text: str, limit: int = 120) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def record(
    db: Session,
    *,
    project_id: int,
    actor_id: int,
    event_type: str,
    entity_type: str,
    entity_id: int,
    summary: str,
    goal: Goal | None = None,
    meeting_category: str | None = None,
    private_to: int | None = None,
    subject_user_id: int | None = None,
    at=None,
) -> ActivityEvent:
    """Add a timeline event and the notifications it causes (see notify.py).

    subject_user_id: the user the event is about when that is not the entity itself
    (e.g. the member who was added to a project).
    """
    if goal is not None and goal.visibility == "private":
        private_to = goal.created_by
    ev = ActivityEvent(
        project_id=project_id,
        goal_id=goal.id if goal is not None else None,
        actor_id=actor_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=short(summary, 500),
        meeting_category=meeting_category,
        private_to=private_to,
        created_at=at or utcnow(),
    )
    db.add(ev)
    db.flush()
    notify.fan_out(db, ev, subject_user_id)
    return ev
