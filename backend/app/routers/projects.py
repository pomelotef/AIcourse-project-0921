from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import events
from ..db import get_db
from ..models import Project, ProjectMember, User
from ..perms import require_advisor, require_member
from ..schemas import MemberIn, MemberPatch, ProjectIn, ProjectPatch
from ..security import current_user

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _members(db: Session, project_id: int) -> list[dict]:
    rows = (
        db.query(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .filter(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.role, User.name)
        .all()
    )
    return [{"id": u.id, "name": u.name, "email": u.email, "role": m.role} for m, u in rows]


def _project(db: Session, p: Project, my_role: str) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "description": p.description,
        "state": p.state,
        "my_role": my_role,
        "created_at": p.created_at,
        "members": _members(db, p.id),
    }


@router.get("")
def list_projects(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = (
        db.query(Project, ProjectMember)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .filter(ProjectMember.user_id == user.id)
        .order_by(Project.state, Project.created_at.desc())
        .all()
    )
    return [_project(db, p, m.role) for p, m in rows]


@router.post("", status_code=201)
def create_project(body: ProjectIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = Project(title=body.title, description=body.description, created_by=user.id)
    db.add(p)
    db.flush()
    db.add(ProjectMember(project_id=p.id, user_id=user.id, role=body.creator_role))
    events.record(
        db, project_id=p.id, actor_id=user.id, event_type="project_created", entity_type="project",
        entity_id=p.id, summary=f"建立專案「{p.title}」",
    )
    db.commit()
    return _project(db, p, body.creator_role)


@router.get("/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = require_member(db, user, project_id)
    return _project(db, db.get(Project, project_id), m.role)


@router.patch("/{project_id}")
def patch_project(
    project_id: int, body: ProjectPatch, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    m = require_advisor(db, user, project_id)
    p = db.get(Project, project_id)
    for field in ("title", "description", "state"):
        value = getattr(body, field)
        if value is not None:
            setattr(p, field, value)
    db.commit()
    return _project(db, p, m.role)


@router.post("/{project_id}/members", status_code=201)
def add_member(project_id: int, body: MemberIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_advisor(db, user, project_id)
    target = db.query(User).filter(User.email == body.email.lower()).first()
    if target is None:
        raise HTTPException(404, "找不到此 email 的帳號，請對方先註冊")
    exists = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == target.id)
        .first()
    )
    if exists:
        raise HTTPException(409, "此成員已在專案中")
    db.add(ProjectMember(project_id=project_id, user_id=target.id, role=body.role))
    events.record(
        db, project_id=project_id, actor_id=user.id, event_type="member_added", entity_type="project",
        entity_id=project_id, summary=f"加入成員 {target.name}（{'指導者' if body.role == 'advisor' else '學生'}）",
    )
    db.commit()
    return _members(db, project_id)


def _advisor_count(db: Session, project_id: int) -> int:
    return (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.role == "advisor")
        .count()
    )


def _get_membership(db: Session, project_id: int, user_id: int) -> ProjectMember:
    m = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        .first()
    )
    if m is None:
        raise HTTPException(404, "找不到此成員")
    return m


@router.patch("/{project_id}/members/{user_id}")
def change_role(
    project_id: int, user_id: int, body: MemberPatch, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    require_advisor(db, user, project_id)
    m = _get_membership(db, project_id, user_id)
    if m.role == "advisor" and body.role != "advisor" and _advisor_count(db, project_id) <= 1:
        raise HTTPException(400, "專案至少需要一位指導者")
    m.role = body.role
    db.commit()
    return _members(db, project_id)


@router.delete("/{project_id}/members/{user_id}")
def remove_member(project_id: int, user_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_advisor(db, user, project_id)
    m = _get_membership(db, project_id, user_id)
    if m.role == "advisor" and _advisor_count(db, project_id) <= 1:
        raise HTTPException(400, "專案至少需要一位指導者")
    db.delete(m)
    db.commit()
    return _members(db, project_id)
