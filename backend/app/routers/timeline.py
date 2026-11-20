"""Research timeline and private notes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ActivityEvent, Goal, PrivateNote, User, utcnow
from ..perms import NOT_FOUND, load_goal, require_member
from ..schemas import NoteIn, NotePatch
from ..security import current_user
from ..serialize import Ser

router = APIRouter(prefix="/api", tags=["timeline"])

EVENT_GROUPS = {
    "update": ("update_published",),
    "blocker": ("blocker_opened", "blocker_resolved", "blocker_reopened"),
    "decision": ("outcome_recorded", "outcome_confirmed", "outcome_commented", "outcome_revised", "meeting_created"),
    "action": ("action_created", "action_updated"),
    "goal": ("goal_created", "goal_updated"),
}


def _descendants(db: Session, root: Goal) -> set[int]:
    ids, frontier = {root.id}, [root.id]
    while frontier:
        children = [g.id for g in db.query(Goal).filter(Goal.parent_id.in_(frontier))]
        frontier = [c for c in children if c not in ids]
        ids.update(frontier)
    return ids


@router.get("/projects/{project_id}/timeline")
def timeline(
    project_id: int,
    goal_id: int | None = None,
    category: str | None = Query(default=None, description="meeting category"),
    kind: str | None = Query(default=None, description="update / blocker / decision / action / goal"),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    require_member(db, user, project_id)
    q = db.query(ActivityEvent).filter(
        ActivityEvent.project_id == project_id,
        or_(ActivityEvent.private_to.is_(None), ActivityEvent.private_to == user.id),
    )
    if goal_id is not None:
        goal, _ = load_goal(db, user, goal_id)
        if goal.project_id != project_id:
            raise HTTPException(404, NOT_FOUND)
        q = q.filter(ActivityEvent.goal_id.in_(_descendants(db, goal)))
    if category:
        q = q.filter(ActivityEvent.meeting_category == category)
    if kind:
        if kind not in EVENT_GROUPS:
            raise HTTPException(400, "未知的事件類型")
        q = q.filter(ActivityEvent.event_type.in_(EVENT_GROUPS[kind]))
    ser = Ser(db)
    rows = q.order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc()).limit(limit).all()
    return [ser.event(e) for e in rows]


# ---------------- private notes (author only) ----------------
def _note(n: PrivateNote) -> dict:
    return {
        "id": n.id, "project_id": n.project_id, "goal_id": n.goal_id, "body": n.body,
        "created_at": n.created_at, "updated_at": n.updated_at,
    }


@router.get("/projects/{project_id}/notes")
def list_notes(project_id: int, goal_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_member(db, user, project_id)
    q = db.query(PrivateNote).filter(PrivateNote.project_id == project_id, PrivateNote.author_id == user.id)
    if goal_id is not None:
        q = q.filter(PrivateNote.goal_id == goal_id)
    return [_note(n) for n in q.order_by(PrivateNote.updated_at.desc())]


@router.post("/projects/{project_id}/notes", status_code=201)
def create_note(project_id: int, body: NoteIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_member(db, user, project_id)
    if body.goal_id is not None:
        goal, _ = load_goal(db, user, body.goal_id)
        if goal.project_id != project_id:
            raise HTTPException(400, "研究目標不屬於此專案")
    n = PrivateNote(project_id=project_id, goal_id=body.goal_id, author_id=user.id, body=body.body)
    db.add(n)
    db.commit()
    return _note(n)


def _own_note(db: Session, user: User, note_id: int) -> PrivateNote:
    n = db.get(PrivateNote, note_id)
    if n is None or n.author_id != user.id:
        raise HTTPException(404, NOT_FOUND)
    require_member(db, user, n.project_id)
    return n


@router.patch("/notes/{note_id}")
def edit_note(note_id: int, body: NotePatch, db: Session = Depends(get_db), user: User = Depends(current_user)):
    n = _own_note(db, user, note_id)
    n.body, n.updated_at = body.body, utcnow()
    db.commit()
    return _note(n)


@router.delete("/notes/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    n = _own_note(db, user, note_id)
    db.delete(n)
    db.commit()
    return {"ok": True}
