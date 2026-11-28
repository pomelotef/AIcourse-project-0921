"""The notification bell: list, unread count, mark as read."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ActionItem, ActivityEvent, MeetingOutcome, Notification, Project, ProjectMember, User, utcnow
from ..security import current_user
from ..serialize import Ser

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _visible(user: User):
    """Notifications the user may still see: still a member, and the event is not private to someone else
    (a goal made private after the notification was sent)."""
    return (
        select(Notification, ActivityEvent)
        .join(ActivityEvent, ActivityEvent.id == Notification.event_id)
        .join(ProjectMember, (ProjectMember.project_id == Notification.project_id)
              & (ProjectMember.user_id == user.id))
        .where(Notification.user_id == user.id)
        .where(or_(ActivityEvent.private_to.is_(None), ActivityEvent.private_to == user.id))
    )


def _link(db: Session, ev: ActivityEvent) -> str:
    """Page to open when the notification is clicked."""
    if ev.entity_type == "outcome":
        o = db.get(MeetingOutcome, ev.entity_id)
        if o:
            return f"/meetings/{o.meeting_id}"
    if ev.entity_type == "meeting":
        return f"/meetings/{ev.entity_id}"
    if ev.goal_id:
        return f"/goals/{ev.goal_id}"
    if ev.entity_type == "action":
        a = db.get(ActionItem, ev.entity_id)
        if a and a.source_meeting_id:
            return f"/meetings/{a.source_meeting_id}"
    return f"/projects/{ev.project_id}"


@router.get("")
def list_notifications(
    limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(current_user)
):
    rows = db.execute(_visible(user).order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit))
    unread = db.execute(_visible(user).where(Notification.read_at.is_(None))).all()
    ser = Ser(db)
    items = []
    for n, ev in rows:
        project = db.get(Project, n.project_id)
        items.append({
            "id": n.id,
            "event_type": ev.event_type,
            "summary": ev.summary,
            "actor": ser.user(ev.actor_id),
            "project": {"id": project.id, "title": project.title},
            "link": _link(db, ev),
            "read": n.read_at is not None,
            "created_at": n.created_at,
        })
    return {"items": items, "unread": len(unread)}


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:  # someone else's: same answer as missing
        raise HTTPException(404, "找不到此通知")
    if n.read_at is None:
        n.read_at = utcnow()
        db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(current_user)):
    now = utcnow()
    for n in db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))):
        n.read_at = now
    db.commit()
    return {"ok": True}
