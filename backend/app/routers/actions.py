from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import events
from ..db import get_db
from ..labels import ACTION_STATE_LABEL, PRIORITY_LABEL
from ..models import ActionItem, Goal, Meeting, ProgressUpdate, User, utcnow
from ..perms import load_in_project, load_shared_goal_in_project, require_member, require_project_member_user
from ..schemas import ActionIn, ActionPatch
from ..security import current_user
from ..serialize import Ser
from .common import action_sort_key

router = APIRouter(prefix="/api", tags=["actions"])


def _meeting_category(db: Session, meeting_id: int | None) -> str | None:
    m = db.get(Meeting, meeting_id) if meeting_id else None
    return m.category if m else None


@router.get("/projects/{project_id}/actions")
def list_actions(
    project_id: int,
    assignee_id: int | None = None,
    goal_id: int | None = None,
    state: str | None = Query(default=None, description="open = 未結束（open+in_progress）"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    require_member(db, user, project_id)
    q = db.query(ActionItem).filter(ActionItem.project_id == project_id)
    if assignee_id is not None:
        q = q.filter(ActionItem.assignee_id == assignee_id)
    if goal_id is not None:
        q = q.filter(ActionItem.goal_id == goal_id)
    if state == "open":
        q = q.filter(ActionItem.state.in_(("open", "in_progress")))
    elif state:
        q = q.filter(ActionItem.state == state)
    ser = Ser(db)
    return [ser.action(a) for a in sorted(q.all(), key=action_sort_key)]


@router.post("/projects/{project_id}/actions", status_code=201)
def create_action(project_id: int, body: ActionIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = require_member(db, user, project_id)
    require_project_member_user(db, project_id, body.assignee_id)
    if m.role != "advisor" and body.assignee_id != user.id:
        raise HTTPException(403, "學生只能建立自己負責的待辦")
    goal = load_shared_goal_in_project(db, user, body.goal_id, project_id) if body.goal_id else None
    if body.source_meeting_id is not None:
        mt = db.get(Meeting, body.source_meeting_id)
        if mt is None or mt.project_id != project_id:
            raise HTTPException(400, "來源 meeting 不存在或不屬於此專案")
    if body.source_update_id is not None:
        up = db.get(ProgressUpdate, body.source_update_id)
        if up is None or up.project_id != project_id or up.publication_state != "published":
            raise HTTPException(400, "來源進度更新不存在或不屬於此專案")
    a = ActionItem(
        project_id=project_id, goal_id=goal.id if goal else None, source_meeting_id=body.source_meeting_id,
        source_update_id=body.source_update_id, title=body.title, assignee_id=body.assignee_id,
        priority=body.priority, due_date=body.due_date, created_by=user.id,
    )
    db.add(a)
    db.flush()
    assignee = db.get(User, body.assignee_id)
    due = f"，期限 {body.due_date.isoformat()}" if body.due_date else ""
    events.record(
        db, project_id=project_id, actor_id=user.id, event_type="action_created", entity_type="action",
        entity_id=a.id, goal=goal, meeting_category=_meeting_category(db, body.source_meeting_id),
        summary=f"新增待辦「{a.title}」→ {assignee.name}（優先度{PRIORITY_LABEL[a.priority]}{due}）",
    )
    db.commit()
    return Ser(db).action(a)


@router.patch("/actions/{action_id}")
def patch_action(action_id: int, body: ActionPatch, db: Session = Depends(get_db), user: User = Depends(current_user)):
    a, m = load_in_project(db, user, ActionItem, action_id)
    if not (m.role == "advisor" or a.assignee_id == user.id or a.created_by == user.id):
        raise HTTPException(403, "只有指導者、負責人或建立者可以修改此待辦")
    goal = db.get(Goal, a.goal_id) if a.goal_id else None
    changes: list[str] = []

    if body.title is not None and body.title != a.title:
        changes.append(f"名稱改為「{body.title}」")
        a.title = body.title
    if body.priority is not None and body.priority != a.priority:
        changes.append(f"優先度：{PRIORITY_LABEL[a.priority]} → {PRIORITY_LABEL[body.priority]}")
        a.priority = body.priority
    if body.assignee_id is not None and body.assignee_id != a.assignee_id:
        if m.role != "advisor" and body.assignee_id != user.id:
            raise HTTPException(403, "學生只能將待辦指派給自己")
        require_project_member_user(db, a.project_id, body.assignee_id)
        changes.append(f"負責人改為 {db.get(User, body.assignee_id).name}")
        a.assignee_id = body.assignee_id

    new_due = None if body.clear_due_date else (body.due_date if body.due_date is not None else a.due_date)
    if new_due != a.due_date:
        if a.due_date is not None and not body.reason:
            raise HTTPException(400, "改期或移除期限時請填寫原因")
        old = a.due_date.isoformat() if a.due_date else "無"
        new = new_due.isoformat() if new_due else "無"
        changes.append(f"期限：{old} → {new}" + (f"（原因：{body.reason}）" if body.reason else ""))
        a.due_date = new_due

    if body.state is not None and body.state != a.state:
        if body.state == "canceled" and not (body.reason or body.note):
            raise HTTPException(400, "取消待辦時請填寫原因")
        changes.append(f"狀態：{ACTION_STATE_LABEL[a.state]} → {ACTION_STATE_LABEL[body.state]}")
        if body.state == "canceled" and body.reason:
            changes[-1] += f"（原因：{body.reason}）"
        a.state = body.state
        a.closed_at = utcnow() if body.state in ("done", "canceled") else None
    if body.note is not None and body.note != a.note:
        a.note = body.note
        changes.append(f"備註：{events.short(body.note, 80)}")

    if changes:
        a.updated_at = utcnow()
        events.record(
            db, project_id=a.project_id, actor_id=user.id, event_type="action_updated", entity_type="action",
            entity_id=a.id, goal=goal, meeting_category=_meeting_category(db, a.source_meeting_id),
            summary=f"待辦「{a.title}」" + "；".join(changes),
        )
    db.commit()
    return Ser(db).action(a)
