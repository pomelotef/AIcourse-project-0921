from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import events
from ..db import get_db
from ..labels import GOAL_STATE_LABEL
from ..models import (
    ActionItem,
    ActivityEvent,
    Blocker,
    Goal,
    Meeting,
    MeetingOutcome,
    PrivateNote,
    ProgressUpdate,
    User,
    utcnow,
)
from ..perms import goal_visible, load_goal, require_member, require_project_member_user
from ..schemas import GoalIn, GoalPatch
from ..security import current_user
from ..serialize import Ser
from .common import action_sort_key

router = APIRouter(prefix="/api", tags=["goals"])


def _has_linked_records(db: Session, goal_id: int) -> bool:
    return any(
        db.query(model).filter(model.goal_id == goal_id).first() is not None
        for model in (ProgressUpdate, Blocker, ActionItem, MeetingOutcome)
    ) or db.query(Goal).filter(Goal.parent_id == goal_id).first() is not None


def _validate_parent(db: Session, user: User, goal: Goal | None, project_id: int, parent_id: int | None, visibility: str):
    if parent_id is None:
        return
    parent = db.get(Goal, parent_id)
    if parent is None or parent.project_id != project_id or not goal_visible(parent, user):
        raise HTTPException(400, "上層目標不存在或不屬於此專案")
    if visibility == "shared" and parent.visibility != "shared":
        raise HTTPException(400, "共享目標不能放在私人目標底下")
    # cycle check: walk up from the new parent; we must never reach the goal itself
    if goal is not None:
        seen = set()
        node = parent
        while node is not None:
            if node.id == goal.id:
                raise HTTPException(400, "上層目標設定會形成循環")
            if node.id in seen:  # pragma: no cover - defensive, data already cyclic
                break
            seen.add(node.id)
            node = db.get(Goal, node.parent_id) if node.parent_id else None


def _validate_assignee(db: Session, user: User, member_role: str, project_id: int, assignee_id: int | None, visibility: str):
    if assignee_id is None:
        return
    require_project_member_user(db, project_id, assignee_id)
    if visibility == "private" and assignee_id != user.id:
        raise HTTPException(400, "私人目標只能由自己負責；要指派給他人請先設為共享")
    if member_role != "advisor" and assignee_id != user.id:
        raise HTTPException(403, "學生只能將目標指派給自己")


def _goal_stats(db: Session, goal: Goal) -> dict:
    open_blockers = db.query(Blocker).filter(Blocker.goal_id == goal.id, Blocker.state == "open").count()
    last = (
        db.query(ProgressUpdate)
        .filter(ProgressUpdate.goal_id == goal.id, ProgressUpdate.publication_state == "published")
        .order_by(ProgressUpdate.published_at.desc())
        .first()
    )
    open_actions = (
        db.query(ActionItem)
        .filter(ActionItem.goal_id == goal.id, ActionItem.state.in_(("open", "in_progress")))
        .count()
    )
    return {
        "open_blocker_count": open_blockers,
        "open_action_count": open_actions,
        "last_update_at": last.published_at if last else None,
    }


@router.get("/projects/{project_id}/goals")
def list_goals(project_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_member(db, user, project_id)
    goals = db.query(Goal).filter(Goal.project_id == project_id).order_by(Goal.created_at, Goal.id).all()
    ser = Ser(db)
    return [{**ser.goal(g), **_goal_stats(db, g)} for g in goals if goal_visible(g, user)]


@router.post("/projects/{project_id}/goals", status_code=201)
def create_goal(project_id: int, body: GoalIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = require_member(db, user, project_id)
    _validate_parent(db, user, None, project_id, body.parent_id, body.visibility)
    _validate_assignee(db, user, m.role, project_id, body.assignee_id, body.visibility)
    g = Goal(
        project_id=project_id,
        parent_id=body.parent_id,
        title=body.title,
        research_question=body.research_question,
        assignee_id=body.assignee_id,
        research_state=body.research_state,
        visibility=body.visibility,
        created_by=user.id,
    )
    db.add(g)
    db.flush()
    assignee = db.get(User, body.assignee_id) if body.assignee_id else None
    events.record(
        db, project_id=project_id, actor_id=user.id, event_type="goal_created", entity_type="goal",
        entity_id=g.id, goal=g,
        summary=f"新增研究目標「{g.title}」" + (f"，負責人：{assignee.name}" if assignee else ""),
    )
    db.commit()
    return Ser(db).goal(g)


@router.get("/goals/{goal_id}")
def goal_detail(goal_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    goal, m = load_goal(db, user, goal_id)
    ser = Ser(db)

    published = (
        db.query(ProgressUpdate)
        .filter(ProgressUpdate.goal_id == goal.id, ProgressUpdate.publication_state == "published")
        .order_by(ProgressUpdate.published_at.desc())
        .all()
    )
    my_drafts = (
        db.query(ProgressUpdate)
        .filter(
            ProgressUpdate.goal_id == goal.id,
            ProgressUpdate.publication_state == "draft",
            ProgressUpdate.author_id == user.id,
        )
        .order_by(ProgressUpdate.updated_at.desc())
        .all()
    )
    blockers = db.query(Blocker).filter(Blocker.goal_id == goal.id).order_by(Blocker.opened_at.desc()).all()
    actions = sorted(db.query(ActionItem).filter(ActionItem.goal_id == goal.id).all(), key=action_sort_key)
    outcomes = (
        db.query(MeetingOutcome)
        .join(Meeting, Meeting.id == MeetingOutcome.meeting_id)
        .filter(MeetingOutcome.goal_id == goal.id)
        .order_by(Meeting.occurred_at.desc(), MeetingOutcome.id.desc())
        .all()
    )
    children = [
        {**ser.goal(c), **_goal_stats(db, c)}
        for c in db.query(Goal).filter(Goal.parent_id == goal.id).order_by(Goal.created_at).all()
        if goal_visible(c, user)
    ]
    notes = (
        db.query(PrivateNote)
        .filter(PrivateNote.goal_id == goal.id, PrivateNote.author_id == user.id)
        .order_by(PrivateNote.updated_at.desc())
        .all()
    )
    open_blockers = [b for b in blockers if b.state == "open"]
    open_actions = [a for a in actions if a.state in ("open", "in_progress")]
    latest = published[0] if published else None

    return {
        "goal": {**ser.goal(goal), **_goal_stats(db, goal)},
        "my_role": m.role,
        "parent": ser.goal_ref(goal.parent_id),
        "summary": {
            "latest_update": ser.update(latest) if latest else None,
            "open_blockers": [ser.blocker(b) for b in open_blockers],
            "next_steps_text": latest.next_steps if latest else "",
            "open_actions": [ser.action(a) for a in open_actions],
            "latest_decision": ser.outcome(outcomes[0]) if outcomes else None,
        },
        "children": children,
        "updates": [ser.update(u) for u in published],
        "my_drafts": [ser.update(u) for u in my_drafts],
        "blockers": [ser.blocker(b) for b in blockers],
        "actions": [ser.action(a) for a in actions],
        "outcomes": [ser.outcome(o) for o in outcomes],
        "links": ser.links("goal", goal.id),
        "private_notes": [
            {"id": n.id, "body": n.body, "created_at": n.created_at, "updated_at": n.updated_at} for n in notes
        ],
    }


@router.patch("/goals/{goal_id}")
def patch_goal(goal_id: int, body: GoalPatch, db: Session = Depends(get_db), user: User = Depends(current_user)):
    goal, m = load_goal(db, user, goal_id)
    if not (m.role == "advisor" or goal.created_by == user.id or goal.assignee_id == user.id):
        raise HTTPException(403, "只有指導者、建立者或負責人可以修改此目標")
    fields = body.model_fields_set
    new_visibility = body.visibility if "visibility" in fields and body.visibility else goal.visibility
    new_parent = body.parent_id if "parent_id" in fields else goal.parent_id
    new_assignee = body.assignee_id if "assignee_id" in fields else goal.assignee_id

    if new_visibility != goal.visibility:
        if goal.created_by != user.id:
            raise HTTPException(403, "只有建立者可以變更目標的可見範圍")
        if new_visibility == "private" and _has_linked_records(db, goal.id):
            raise HTTPException(400, "此目標已有共享紀錄或子目標，不能改為私人")
    if "parent_id" in fields or new_visibility != goal.visibility:
        _validate_parent(db, user, goal, goal.project_id, new_parent, new_visibility)
    if "assignee_id" in fields or new_visibility != goal.visibility:
        if "assignee_id" in fields and new_assignee != goal.assignee_id and m.role != "advisor" and new_assignee not in (None, user.id):
            raise HTTPException(403, "學生只能將目標指派給自己")
        if new_assignee is not None:
            require_project_member_user(db, goal.project_id, new_assignee)
            if new_visibility == "private" and new_assignee != goal.created_by:
                raise HTTPException(400, "私人目標只能由自己負責；要指派給他人請先設為共享")

    changes: list[str] = []
    if body.title is not None and body.title != goal.title:
        changes.append(f"標題改為「{body.title}」")
        goal.title = body.title
    if body.research_question is not None and body.research_question != goal.research_question:
        changes.append("更新研究問題")
        goal.research_question = body.research_question
    if body.research_state is not None and body.research_state != goal.research_state:
        changes.append(
            f"研究狀態：{GOAL_STATE_LABEL[goal.research_state]} → {GOAL_STATE_LABEL[body.research_state]}"
        )
        goal.research_state = body.research_state
    if "parent_id" in fields and new_parent != goal.parent_id:
        changes.append("調整上層目標")
        goal.parent_id = new_parent
    if "assignee_id" in fields and new_assignee != goal.assignee_id:
        who = db.get(User, new_assignee).name if new_assignee else "未指派"
        changes.append(f"負責人改為 {who}")
        goal.assignee_id = new_assignee
    if new_visibility != goal.visibility:
        changes.append("設為共享" if new_visibility == "shared" else "設為私人")
        goal.visibility = new_visibility
        if new_visibility == "private":
            # Hide the goal's earlier (shared) history from other members too.
            db.query(ActivityEvent).filter(ActivityEvent.goal_id == goal.id).update(
                {ActivityEvent.private_to: goal.created_by}
            )

    if changes:
        goal.updated_at = utcnow()
        events.record(
            db, project_id=goal.project_id, actor_id=user.id, event_type="goal_updated", entity_type="goal",
            entity_id=goal.id, goal=goal, summary=f"「{goal.title}」" + "；".join(changes),
        )
    db.commit()
    return {**Ser(db).goal(goal), **_goal_stats(db, goal)}
