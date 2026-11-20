"""Progress updates, blockers and external links."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import events
from ..db import get_db
from ..models import Blocker, ExternalLink, Goal, ProgressUpdate, UpdateBlocker, User, utcnow
from ..perms import NOT_FOUND, load_goal, load_in_project
from ..schemas import BlockerIn, BlockerPatch, LinkCreate, LinkIn, UpdateIn
from ..security import current_user
from ..serialize import Ser

router = APIRouter(prefix="/api", tags=["updates"])


def _require_shared(goal: Goal) -> None:
    if goal.visibility != "shared":
        raise HTTPException(400, "私人目標不能新增共享紀錄；請先將目標設為共享")


def _add_links(db: Session, user: User, project_id: int, target_type: str, target_id: int, links: list[LinkIn]):
    for l in links:
        db.add(
            ExternalLink(
                project_id=project_id, target_type=target_type, target_id=target_id,
                url=l.url, label=l.label, link_type=l.link_type, created_by=user.id,
            )
        )


def _set_referenced_blockers(db: Session, update: ProgressUpdate, blocker_ids: list[int]) -> None:
    db.query(UpdateBlocker).filter(UpdateBlocker.update_id == update.id).delete()
    for bid in dict.fromkeys(blocker_ids):
        b = db.get(Blocker, bid)
        if b is None or b.project_id != update.project_id:
            raise HTTPException(400, "引用的 blocker 不存在或不屬於此專案")
        db.add(UpdateBlocker(update_id=update.id, blocker_id=b.id))


def _publish(db: Session, user: User, goal: Goal, u: ProgressUpdate) -> None:
    if not (u.completed or u.findings or u.next_steps or u.draft_blockers):
        raise HTTPException(400, "發布前請至少填寫一個欄位")
    now = utcnow()
    for nb in u.draft_blockers or []:
        b = Blocker(
            project_id=u.project_id, goal_id=goal.id, reported_by=user.id,
            title=nb["title"], description=nb.get("description", ""), opened_at=now,
        )
        db.add(b)
        db.flush()
        db.add(UpdateBlocker(update_id=u.id, blocker_id=b.id))
        events.record(
            db, project_id=u.project_id, actor_id=user.id, event_type="blocker_opened", entity_type="blocker",
            entity_id=b.id, goal=goal, summary=f"提出 blocker：{b.title}", at=now,
        )
    u.draft_blockers = []
    u.publication_state = "published"
    u.published_at = now
    u.updated_at = now
    parts = [p for p in (u.completed, u.findings) if p]
    events.record(
        db, project_id=u.project_id, actor_id=user.id, event_type="update_published", entity_type="update",
        entity_id=u.id, goal=goal, summary="進度更新：" + (events.short(parts[0], 100) if parts else "（下一步）"),
        at=now,
    )


def _load_update(db: Session, user: User, update_id: int) -> ProgressUpdate:
    u, _ = load_in_project(db, user, ProgressUpdate, update_id)
    if u.publication_state == "draft" and u.author_id != user.id:
        raise HTTPException(404, NOT_FOUND)
    return u


# ---------------- progress updates ----------------
@router.get("/goals/{goal_id}/updates")
def list_updates(goal_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    goal, _ = load_goal(db, user, goal_id)
    rows = (
        db.query(ProgressUpdate)
        .filter(ProgressUpdate.goal_id == goal.id)
        .order_by(ProgressUpdate.created_at.desc())
        .all()
    )
    ser = Ser(db)
    return [ser.update(u) for u in rows if u.publication_state == "published" or u.author_id == user.id]


@router.post("/goals/{goal_id}/updates", status_code=201)
def create_update(goal_id: int, body: UpdateIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    goal, _ = load_goal(db, user, goal_id)
    _require_shared(goal)
    u = ProgressUpdate(
        project_id=goal.project_id, goal_id=goal.id, author_id=user.id,
        completed=body.completed, findings=body.findings, next_steps=body.next_steps,
        no_blocker=body.no_blocker, draft_blockers=[b.model_dump() for b in body.new_blockers],
    )
    db.add(u)
    db.flush()
    _set_referenced_blockers(db, u, body.referenced_blocker_ids)
    _add_links(db, user, goal.project_id, "update", u.id, body.links)
    if body.publish:
        _publish(db, user, goal, u)
    db.commit()
    return Ser(db).update(u)


@router.patch("/updates/{update_id}")
def edit_draft(update_id: int, body: UpdateIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    u = _load_update(db, user, update_id)
    if u.author_id != user.id or u.publication_state != "draft":
        raise HTTPException(400, "只能編輯自己的草稿；已發布的更新會保留原樣")
    goal = db.get(Goal, u.goal_id)
    u.completed, u.findings, u.next_steps = body.completed, body.findings, body.next_steps
    u.no_blocker = body.no_blocker
    u.draft_blockers = [b.model_dump() for b in body.new_blockers]
    u.updated_at = utcnow()
    _set_referenced_blockers(db, u, body.referenced_blocker_ids)
    db.query(ExternalLink).filter(ExternalLink.target_type == "update", ExternalLink.target_id == u.id).delete()
    _add_links(db, user, u.project_id, "update", u.id, body.links)
    if body.publish:
        _publish(db, user, goal, u)
    db.commit()
    return Ser(db).update(u)


@router.delete("/updates/{update_id}")
def delete_draft(update_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    u = _load_update(db, user, update_id)
    if u.author_id != user.id or u.publication_state != "draft":
        raise HTTPException(400, "只能刪除自己的草稿")
    db.query(ExternalLink).filter(ExternalLink.target_type == "update", ExternalLink.target_id == u.id).delete()
    db.delete(u)
    db.commit()
    return {"ok": True}


# ---------------- blockers ----------------
@router.get("/goals/{goal_id}/blockers")
def list_blockers(goal_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    goal, _ = load_goal(db, user, goal_id)
    ser = Ser(db)
    rows = db.query(Blocker).filter(Blocker.goal_id == goal.id).order_by(Blocker.opened_at.desc()).all()
    return [ser.blocker(b) for b in rows]


@router.post("/goals/{goal_id}/blockers", status_code=201)
def create_blocker(goal_id: int, body: BlockerIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    goal, _ = load_goal(db, user, goal_id)
    _require_shared(goal)
    b = Blocker(project_id=goal.project_id, goal_id=goal.id, reported_by=user.id, title=body.title,
                description=body.description)
    db.add(b)
    db.flush()
    events.record(
        db, project_id=goal.project_id, actor_id=user.id, event_type="blocker_opened", entity_type="blocker",
        entity_id=b.id, goal=goal, summary=f"提出 blocker：{b.title}",
    )
    db.commit()
    return Ser(db).blocker(b)


@router.patch("/blockers/{blocker_id}")
def patch_blocker(blocker_id: int, body: BlockerPatch, db: Session = Depends(get_db), user: User = Depends(current_user)):
    b, m = load_in_project(db, user, Blocker, blocker_id)
    goal = db.get(Goal, b.goal_id)
    if not (m.role == "advisor" or b.reported_by == user.id or goal.assignee_id == user.id):
        raise HTTPException(403, "只有指導者、提出者或目標負責人可以修改此 blocker")
    if body.title is not None:
        b.title = body.title
    if body.description is not None:
        b.description = body.description
    if body.state is not None and body.state != b.state:
        if body.state == "resolved":
            b.state, b.resolved_at, b.resolved_by = "resolved", utcnow(), user.id
            b.resolution = body.resolution or ""
            summary = f"解決 blocker：{b.title}" + (f"（{events.short(b.resolution, 80)}）" if b.resolution else "")
            etype = "blocker_resolved"
        else:
            b.state, b.resolved_at, b.resolved_by = "open", None, None
            summary, etype = f"重新開啟 blocker：{b.title}", "blocker_reopened"
        events.record(
            db, project_id=b.project_id, actor_id=user.id, event_type=etype, entity_type="blocker",
            entity_id=b.id, goal=goal, summary=summary,
        )
    elif body.resolution is not None:
        b.resolution = body.resolution
    db.commit()
    return Ser(db).blocker(b)


# ---------------- external links ----------------
def _link_target(db: Session, user: User, target_type: str, target_id: int):
    """Return (project_id, can_edit) after checking the caller may see the target."""
    if target_type == "goal":
        goal, m = load_goal(db, user, target_id)
        return goal.project_id, True
    if target_type == "update":
        u = _load_update(db, user, target_id)
        return u.project_id, u.author_id == user.id
    b, _ = load_in_project(db, user, Blocker, target_id)
    return b.project_id, True


@router.post("/links", status_code=201)
def add_link(body: LinkCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_id, can_edit = _link_target(db, user, body.target_type, body.target_id)
    if not can_edit:
        raise HTTPException(403, "只有作者可以替這筆更新加連結")
    link = ExternalLink(
        project_id=project_id, target_type=body.target_type, target_id=body.target_id,
        url=body.url, label=body.label, link_type=body.link_type, created_by=user.id,
    )
    db.add(link)
    db.commit()
    return Ser(db).links(body.target_type, body.target_id)


@router.delete("/links/{link_id}")
def delete_link(link_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    link, m = load_in_project(db, user, ExternalLink, link_id)
    _link_target(db, user, link.target_type, link.target_id)
    if link.created_by != user.id and m.role != "advisor":
        raise HTTPException(403, "只有新增者或指導者可以刪除連結")
    db.delete(link)
    db.commit()
    return {"ok": True}
