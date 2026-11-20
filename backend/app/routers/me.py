"""Personal home ("我的研究") and the advisor multi-project overview."""

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..labels import MEETING_CATEGORY_LABEL
from ..models import (
    ActionItem,
    Blocker,
    Goal,
    Meeting,
    MeetingOutcome,
    MeetingParticipant,
    ProgressUpdate,
    Project,
    ProjectMember,
    User,
    utcnow,
)
from ..security import current_user
from ..serialize import Ser
from .common import action_sort_key, is_overdue

router = APIRouter(prefix="/api/me", tags=["me"])

BLOCKER_ATTENTION_DAYS = 7


def _taipei_today():
    # Due dates are calendar dates; the team and pilot users are in Taiwan (UTC+8).
    return (utcnow() + timedelta(hours=8)).date()


def _my_projects(db: Session, user: User, role: str | None = None) -> list[tuple[Project, str]]:
    q = (
        db.query(Project, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .filter(ProjectMember.user_id == user.id)
    )
    if role:
        q = q.filter(ProjectMember.role == role)
    return [(p, r) for p, r in q.order_by(Project.created_at).all()]


@router.get("/home")
def home(db: Session = Depends(get_db), user: User = Depends(current_user)):
    ser = Ser(db)
    projects = _my_projects(db, user)
    project_ids = [p.id for p, _ in projects]
    advisor_project_ids = [p.id for p, r in projects if r == "advisor"]
    today = _taipei_today()

    goals = (
        db.query(Goal)
        .filter(
            Goal.project_id.in_(project_ids),
            Goal.research_state != "archived",
            or_(
                (Goal.visibility == "shared") & (Goal.assignee_id == user.id),
                (Goal.visibility == "private") & (Goal.created_by == user.id),
            ),
        )
        .order_by(Goal.updated_at.desc())
        .all()
    )
    my_goals = []
    for g in goals:
        last = (
            db.query(ProgressUpdate)
            .filter(ProgressUpdate.goal_id == g.id, ProgressUpdate.publication_state == "published")
            .order_by(ProgressUpdate.published_at.desc())
            .first()
        )
        my_goals.append(
            {
                **ser.goal(g),
                "project_title": next(p.title for p, _ in projects if p.id == g.project_id),
                "open_blocker_count": db.query(Blocker).filter(Blocker.goal_id == g.id, Blocker.state == "open").count(),
                "last_update_at": last.published_at if last else None,
            }
        )

    actions = sorted(
        db.query(ActionItem)
        .filter(
            ActionItem.project_id.in_(project_ids),
            ActionItem.assignee_id == user.id,
            ActionItem.state.in_(("open", "in_progress")),
        )
        .all(),
        key=action_sort_key,
    )

    my_goal_ids = [g.id for g in goals]
    blockers = (
        db.query(Blocker)
        .filter(
            Blocker.project_id.in_(project_ids),
            Blocker.state == "open",
            or_(Blocker.reported_by == user.id, Blocker.goal_id.in_(my_goal_ids)),
        )
        .order_by(Blocker.opened_at)
        .all()
    )

    # Feedback: outcomes on my goals or from meetings I took part in, newest first.
    my_meeting_ids = [mp.meeting_id for mp in db.query(MeetingParticipant).filter(MeetingParticipant.user_id == user.id)]
    feedback = (
        db.query(MeetingOutcome)
        .join(Meeting, Meeting.id == MeetingOutcome.meeting_id)
        .filter(
            Meeting.project_id.in_(project_ids),
            or_(MeetingOutcome.goal_id.in_(my_goal_ids), MeetingOutcome.meeting_id.in_(my_meeting_ids)),
        )
        .order_by(Meeting.occurred_at.desc(), MeetingOutcome.id.desc())
        .limit(8)
        .all()
    )

    pending_confirmation = (
        db.query(MeetingOutcome)
        .join(Meeting, Meeting.id == MeetingOutcome.meeting_id)
        .filter(Meeting.project_id.in_(advisor_project_ids), MeetingOutcome.confirmation_state == "pending")
        .order_by(MeetingOutcome.created_at)
        .all()
    )

    drafts = (
        db.query(ProgressUpdate)
        .filter(ProgressUpdate.author_id == user.id, ProgressUpdate.publication_state == "draft",
                ProgressUpdate.project_id.in_(project_ids))
        .order_by(ProgressUpdate.updated_at.desc())
        .all()
    )
    recent_updates = (
        db.query(ProgressUpdate)
        .filter(ProgressUpdate.author_id == user.id, ProgressUpdate.publication_state == "published",
                ProgressUpdate.project_id.in_(project_ids))
        .order_by(ProgressUpdate.published_at.desc())
        .limit(5)
        .all()
    )

    last_meetings = []
    for p, _ in projects:
        m = (
            db.query(Meeting)
            .filter(Meeting.project_id == p.id, Meeting.occurred_at <= utcnow())
            .order_by(Meeting.occurred_at.desc())
            .first()
        )
        if m:
            last_meetings.append({**ser.meeting(m), "project_title": p.title})

    return {
        "projects": [{"id": p.id, "title": p.title, "state": p.state, "my_role": r} for p, r in projects],
        "is_advisor": bool(advisor_project_ids),
        "my_goals": my_goals,
        "my_actions": [{**ser.action(a), "overdue": is_overdue(a, today)} for a in actions],
        "my_open_blockers": [ser.blocker(b) for b in blockers],
        "recent_feedback": [ser.outcome(o) for o in feedback],
        "pending_confirmation": [ser.outcome(o) for o in pending_confirmation],
        "drafts": [ser.update(u) for u in drafts],
        "recent_updates": [ser.update(u) for u in recent_updates],
        "last_meetings": last_meetings,
    }


@router.get("/overview")
def overview(
    stale_days: int = Query(default=14, ge=1, le=365),
    category: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Advisor overview across the projects where the caller is an advisor.

    Only data the advisor can already see; nothing here ranks students. "Stale" means the
    information may be out of date, not that no research happened.
    """
    ser = Ser(db)
    now = utcnow()
    today = _taipei_today()
    projects = [p for p, _ in _my_projects(db, user, role="advisor")]
    pids = [p.id for p in projects]

    members = (
        db.query(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .filter(ProjectMember.project_id.in_(pids))
        .all()
    )
    shared_goals = db.query(Goal).filter(Goal.project_id.in_(pids), Goal.visibility == "shared").all()
    goal_by_id = {g.id: g for g in shared_goals}
    updates = (
        db.query(ProgressUpdate)
        .filter(ProgressUpdate.project_id.in_(pids), ProgressUpdate.publication_state == "published")
        .order_by(ProgressUpdate.published_at.desc())
        .all()
    )
    open_blockers = (
        db.query(Blocker)
        .filter(Blocker.project_id.in_(pids), Blocker.state == "open")
        .order_by(Blocker.opened_at)
        .all()
    )
    open_actions = (
        db.query(ActionItem)
        .filter(ActionItem.project_id.in_(pids), ActionItem.state.in_(("open", "in_progress")))
        .all()
    )
    pending = (
        db.query(MeetingOutcome, Meeting)
        .join(Meeting, Meeting.id == MeetingOutcome.meeting_id)
        .filter(Meeting.project_id.in_(pids), MeetingOutcome.confirmation_state == "pending")
        .all()
    )
    mq = db.query(Meeting).filter(Meeting.project_id.in_(pids))
    if category:
        mq = mq.filter(Meeting.category == category)
    meetings = mq.order_by(Meeting.occurred_at.desc()).all()

    by_project = []
    for p in projects:
        p_updates = [u for u in updates if u.project_id == p.id]
        p_meetings = [m for m in meetings if m.project_id == p.id]
        latest_by_cat: dict[str, dict] = {}
        for m in p_meetings:
            latest_by_cat.setdefault(m.category, {"id": m.id, "title": m.title, "occurred_at": m.occurred_at,
                                                  "category_label": MEETING_CATEGORY_LABEL[m.category]})
        p_actions = [a for a in open_actions if a.project_id == p.id]
        by_project.append(
            {
                "id": p.id,
                "title": p.title,
                "state": p.state,
                "members": [
                    {"id": u.id, "name": u.name, "role": pm.role} for pm, u in members if pm.project_id == p.id
                ],
                "goal_count": sum(1 for g in shared_goals if g.project_id == p.id),
                "last_update_at": p_updates[0].published_at if p_updates else None,
                "recent_updates": [ser.update(u) for u in p_updates[:3]],
                "open_blockers": [ser.blocker(b) for b in open_blockers if b.project_id == p.id],
                "open_action_count": len(p_actions),
                "overdue_action_count": sum(is_overdue(a, today) for a in p_actions),
                "pending_outcome_count": sum(1 for _, m in pending if m.project_id == p.id),
                "latest_meetings": list(latest_by_cat.values()),
            }
        )

    # One row per student across the advisor's projects.
    students: dict[int, dict] = {}
    for pm, u in members:
        if pm.role != "student":
            continue
        row = students.setdefault(u.id, {"id": u.id, "name": u.name, "projects": []})
        row["projects"].append({"id": pm.project_id, "title": next(p.title for p in projects if p.id == pm.project_id)})

    by_member = []
    attention = []
    for sid, row in students.items():
        s_pids = {p["id"] for p in row["projects"]}
        s_updates = [u for u in updates if u.author_id == sid and u.project_id in s_pids]
        s_goal_ids = {g.id for g in shared_goals if g.assignee_id == sid}
        s_blockers = [
            b for b in open_blockers if b.project_id in s_pids and (b.reported_by == sid or b.goal_id in s_goal_ids)
        ]
        s_actions = [a for a in open_actions if a.assignee_id == sid and a.project_id in s_pids]
        overdue = [a for a in s_actions if is_overdue(a, today)]
        last_at = s_updates[0].published_at if s_updates else None
        if last_at is None:
            freshness = "no_record"
        elif now - last_at > timedelta(days=stale_days):
            freshness = "stale"
        else:
            freshness = "fresh"
        by_member.append(
            {
                **row,
                "goals": [{"id": g.id, "title": g.title, "research_state": g.research_state}
                          for g in shared_goals if g.assignee_id == sid],
                "last_update_at": last_at,
                "freshness": freshness,
                "latest_update": ser.update(s_updates[0]) if s_updates else None,
                "open_blockers": [ser.blocker(b) for b in s_blockers],
                "open_action_count": len(s_actions),
                "overdue_actions": [ser.action(a) for a in overdue],
            }
        )
        if freshness == "no_record":
            attention.append({"kind": "no_record", "member": {"id": sid, "name": row["name"]},
                              "text": f"{row['name']} 尚無進度紀錄"})
        elif freshness == "stale":
            days = (now - last_at).days
            attention.append({"kind": "stale", "member": {"id": sid, "name": row["name"]},
                              "text": f"{row['name']} 已 {days} 天沒有新進度，資訊可能過期（週期 {stale_days} 天）"})
        for b in s_blockers:
            days = (now - b.opened_at).days
            if days >= BLOCKER_ATTENTION_DAYS:
                goal = goal_by_id.get(b.goal_id)
                attention.append({"kind": "long_blocker", "member": {"id": sid, "name": row["name"]},
                                  "blocker_id": b.id, "goal_id": b.goal_id,
                                  "text": f"{row['name']} 的 blocker「{b.title}」已持續 {days} 天"
                                          + (f"（{goal.title}）" if goal else "")})
        for a in overdue:
            attention.append({"kind": "overdue", "member": {"id": sid, "name": row["name"]}, "action_id": a.id,
                              "text": f"{row['name']} 的待辦「{a.title}」已過期限 {a.due_date.isoformat()}"})

    for o, m in pending:
        attention.append({"kind": "pending_outcome", "meeting_id": m.id, "outcome_id": o.id,
                          "text": f"「{m.title}」有學生記錄的結論待確認：{o.decision[:40]}"})

    by_member.sort(key=lambda r: r["name"])
    return {
        "rules": {
            "stale_days": stale_days,
            "blocker_attention_days": BLOCKER_ATTENTION_DAYS,
            "description": f"超過 {stale_days} 天沒有新進度視為「資訊可能過期」；blocker 開啟超過 "
                           f"{BLOCKER_ATTENTION_DAYS} 天、待辦超過期限、學生記錄的結論待確認時列入需要關注。",
        },
        "attention": attention,
        "by_project": by_project,
        "by_member": by_member,
    }
