"""Who gets a notification (the bell) for an activity event.

Every write that matters already goes through ``events.record``, so this module only decides
recipients; routes do not call it directly. The rules, in one place so the team can change them:

| event                         | notified                                             |
|-------------------------------|------------------------------------------------------|
| update_published              | the project's advisors                               |
| blocker_opened                | advisors + the goal's assignee                       |
| action_created/updated        | the action's assignee                                |
| outcome_recorded (unconfirmed)| advisors (they need to confirm it)                   |
| outcome_confirmed             | the outcome's author                                 |
| outcome_commented             | the outcome's author + everyone who commented before |
| member_added                  | the member who was added                             |

Always: never the person who did it, only current project members, and nothing for events
that are private to one user (private goals). Everything else (goal edits, meetings created,
blocker resolved ...) stays on the timeline only.

Merging: each user has at most one notification per thing (entity_type + entity_id). A later
event about the same thing replaces the old one, moves it to the top and marks it unread, so
editing a task three times rings the bell once. Acting on a thing yourself (replying,
confirming ...) marks your own notification about it as read, since you have clearly seen it.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    ActionItem,
    ActivityEvent,
    Blocker,
    Goal,
    MeetingOutcome,
    Notification,
    OutcomeComment,
    ProjectMember,
)


def _advisors(db: Session, project_id: int) -> set[int]:
    return set(db.scalars(
        select(ProjectMember.user_id).where(ProjectMember.project_id == project_id, ProjectMember.role == "advisor")
    ))


def _members(db: Session, project_id: int) -> set[int]:
    return set(db.scalars(select(ProjectMember.user_id).where(ProjectMember.project_id == project_id)))


def recipients(db: Session, ev: ActivityEvent, subject_user_id: int | None = None) -> set[int]:
    if ev.private_to is not None:
        return set()
    t, pid = ev.event_type, ev.project_id
    users: set[int] = set()
    if t == "update_published":
        users = _advisors(db, pid)
    elif t == "blocker_opened":
        users = _advisors(db, pid)
        b = db.get(Blocker, ev.entity_id)
        goal = db.get(Goal, b.goal_id) if b else None
        if goal and goal.assignee_id:
            users.add(goal.assignee_id)
    elif t in ("action_created", "action_updated"):
        a = db.get(ActionItem, ev.entity_id)
        if a:
            users = {a.assignee_id}
    elif t == "outcome_recorded":
        o = db.get(MeetingOutcome, ev.entity_id)
        if o and o.confirmation_state != "confirmed":
            users = _advisors(db, pid)
    elif t == "outcome_confirmed":
        o = db.get(MeetingOutcome, ev.entity_id)
        if o:
            users = {o.author_id}
    elif t == "outcome_commented":
        o = db.get(MeetingOutcome, ev.entity_id)
        if o:
            users = {o.author_id}
            users |= set(db.scalars(select(OutcomeComment.author_id).where(OutcomeComment.outcome_id == o.id)))
    elif t == "member_added" and subject_user_id is not None:
        users = {subject_user_id}
    users.discard(ev.actor_id)
    return users & _members(db, pid)


def fan_out(db: Session, ev: ActivityEvent, subject_user_id: int | None = None) -> None:
    """Create or refresh one Notification per recipient. Call after the event is added."""
    if ev.id is None:
        db.flush()
    mine = db.scalar(select(Notification).where(
        Notification.user_id == ev.actor_id,
        Notification.entity_type == ev.entity_type,
        Notification.entity_id == ev.entity_id,
        Notification.read_at.is_(None),
    ))
    if mine is not None:
        mine.read_at = ev.created_at
    users = recipients(db, ev, subject_user_id)
    if not users:
        return
    existing = {
        n.user_id: n
        for n in db.scalars(select(Notification).where(
            Notification.user_id.in_(users),
            Notification.entity_type == ev.entity_type,
            Notification.entity_id == ev.entity_id,
        ))
    }
    for uid in sorted(users):
        n = existing.get(uid)
        if n is None:
            db.add(Notification(user_id=uid, entity_type=ev.entity_type, entity_id=ev.entity_id,
                                event_id=ev.id, project_id=ev.project_id, created_at=ev.created_at))
        else:
            n.event_id, n.created_at, n.read_at = ev.id, ev.created_at, None
