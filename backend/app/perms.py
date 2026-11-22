"""Authorization helpers. Every router goes through these; the frontend only hides buttons.

Records the caller is not allowed to see are reported as 404 (not 403) so that IDs of
other projects or private records cannot be probed.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Goal, ProjectMember, User

NOT_FOUND = "找不到資料，或你沒有存取權限"


def membership(db: Session, user: User, project_id: int) -> ProjectMember | None:
    return (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
        .one_or_none()
    )


def require_member(db: Session, user: User, project_id: int) -> ProjectMember:
    m = membership(db, user, project_id)
    if m is None:
        raise HTTPException(404, NOT_FOUND)
    return m


def require_advisor(db: Session, user: User, project_id: int) -> ProjectMember:
    m = require_member(db, user, project_id)
    if m.role != "advisor":
        raise HTTPException(403, "只有指導者可以執行此操作")
    return m


def goal_visible(goal: Goal, user: User) -> bool:
    return goal.visibility == "shared" or goal.created_by == user.id


def load_goal(db: Session, user: User, goal_id: int) -> tuple[Goal, ProjectMember]:
    goal = db.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(404, NOT_FOUND)
    m = require_member(db, user, goal.project_id)
    if not goal_visible(goal, user):
        raise HTTPException(404, NOT_FOUND)
    return goal, m


def load_shared_goal_in_project(db: Session, user: User, goal_id: int, project_id: int) -> Goal:
    """For linking a record to a goal: must exist, be in the same project and be shared."""
    goal = db.get(Goal, goal_id)
    if goal is None or goal.project_id != project_id or not goal_visible(goal, user):
        raise HTTPException(400, "研究目標不存在或不屬於此專案")
    if goal.visibility != "shared":
        raise HTTPException(400, "私人目標不能關聯共享紀錄；請先將目標設為共享")
    return goal


def load_in_project(db: Session, user: User, model, obj_id: int):
    """Load any record that has a project_id, after checking project membership."""
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(404, NOT_FOUND)
    m = require_member(db, user, obj.project_id)
    return obj, m


def require_project_member_user(db: Session, project_id: int, user_id: int) -> ProjectMember:
    m = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        .one_or_none()
    )
    if m is None:
        raise HTTPException(400, "指定的使用者不是此專案成員")
    return m
