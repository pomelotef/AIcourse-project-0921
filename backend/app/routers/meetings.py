from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import events
from ..db import get_db
from ..labels import MEETING_CATEGORY_LABEL
from ..models import (
    ActionItem,
    Blocker,
    Goal,
    Meeting,
    MeetingOutcome,
    MeetingParticipant,
    OutcomeComment,
    ProgressUpdate,
    User,
    utcnow,
)
from ..perms import (
    NOT_FOUND,
    load_in_project,
    load_shared_goal_in_project,
    require_member,
    require_project_member_user,
)
from ..schemas import CommentIn, MeetingIn, MeetingPatch, OutcomeIn, OutcomePatch
from ..security import current_user
from ..serialize import Ser
from .common import action_sort_key

router = APIRouter(prefix="/api", tags=["meetings"])


def _set_participants(db: Session, meeting: Meeting, user_ids: list[int]) -> None:
    db.query(MeetingParticipant).filter(MeetingParticipant.meeting_id == meeting.id).delete()
    for uid in dict.fromkeys(user_ids):
        require_project_member_user(db, meeting.project_id, uid)
        db.add(MeetingParticipant(meeting_id=meeting.id, user_id=uid))


def previous_meeting(db: Session, meeting: Meeting) -> Meeting | None:
    """Latest earlier meeting of the same project *and* category (lab / industry threads stay separate)."""
    return (
        db.query(Meeting)
        .filter(
            Meeting.project_id == meeting.project_id,
            Meeting.category == meeting.category,
            Meeting.id != meeting.id,
            or_(
                Meeting.occurred_at < meeting.occurred_at,
                (Meeting.occurred_at == meeting.occurred_at) & (Meeting.id < meeting.id),
            ),
        )
        .order_by(Meeting.occurred_at.desc(), Meeting.id.desc())
        .first()
    )


@router.get("/projects/{project_id}/meetings")
def list_meetings(
    project_id: int, category: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    require_member(db, user, project_id)
    q = db.query(Meeting).filter(Meeting.project_id == project_id)
    if category:
        q = q.filter(Meeting.category == category)
    ser = Ser(db)
    out = []
    for m in q.order_by(Meeting.occurred_at.desc(), Meeting.id.desc()).all():
        outcomes = db.query(MeetingOutcome).filter(MeetingOutcome.meeting_id == m.id).all()
        out.append(
            {
                **ser.meeting(m),
                "outcome_count": len(outcomes),
                "pending_outcome_count": sum(o.confirmation_state == "pending" for o in outcomes),
            }
        )
    return out


@router.post("/projects/{project_id}/meetings", status_code=201)
def create_meeting(project_id: int, body: MeetingIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_member(db, user, project_id)
    m = Meeting(
        project_id=project_id, title=body.title, category=body.category, occurred_at=body.occurred_at,
        agenda=body.agenda, created_by=user.id,
    )
    db.add(m)
    db.flush()
    _set_participants(db, m, body.participant_ids or [user.id])
    events.record(
        db, project_id=project_id, actor_id=user.id, event_type="meeting_created", entity_type="meeting",
        entity_id=m.id, meeting_category=m.category,
        summary=f"建立 {MEETING_CATEGORY_LABEL[m.category]}「{m.title}」",
    )
    db.commit()
    return Ser(db).meeting(m)


@router.get("/meetings/{meeting_id}")
def meeting_detail(meeting_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m, mem = load_in_project(db, user, Meeting, meeting_id)
    ser = Ser(db)
    outcomes = (
        db.query(MeetingOutcome)
        .filter(MeetingOutcome.meeting_id == m.id)
        .order_by(MeetingOutcome.created_at, MeetingOutcome.id)
        .all()
    )
    actions = db.query(ActionItem).filter(ActionItem.source_meeting_id == m.id).all()
    return {
        "meeting": ser.meeting(m),
        "my_role": mem.role,
        "outcomes": [ser.outcome(o) for o in outcomes],
        "actions": [ser.action(a) for a in sorted(actions, key=action_sort_key)],
    }


@router.patch("/meetings/{meeting_id}")
def patch_meeting(meeting_id: int, body: MeetingPatch, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m, mem = load_in_project(db, user, Meeting, meeting_id)
    if not (mem.role == "advisor" or m.created_by == user.id):
        raise HTTPException(403, "只有指導者或建立者可以修改此 meeting")
    for field in ("title", "category", "occurred_at", "agenda"):
        value = getattr(body, field)
        if value is not None:
            setattr(m, field, value)
    if body.participant_ids is not None:
        _set_participants(db, m, body.participant_ids)
    db.commit()
    return Ser(db).meeting(m)


@router.get("/meetings/{meeting_id}/brief")
def meeting_brief(
    meeting_id: int, member_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    """What to look at before/in this meeting.

    Window = (previous meeting of the same category, this meeting]. Commitments are the
    actions created at the previous meeting (all states, so finished work stays visible),
    plus older actions that are still unfinished. Optional member_id narrows to one person.
    """
    m, _ = load_in_project(db, user, Meeting, meeting_id)
    if member_id is not None:
        require_project_member_user(db, m.project_id, member_id)
    prev = previous_meeting(db, m)
    ser = Ser(db)

    shared_goal_ids = {
        g.id for g in db.query(Goal).filter(Goal.project_id == m.project_id, Goal.visibility == "shared")
    }
    member_goal_ids = (
        {g.id for g in db.query(Goal).filter(Goal.project_id == m.project_id, Goal.assignee_id == member_id)}
        if member_id is not None
        else None
    )

    uq = db.query(ProgressUpdate).filter(
        ProgressUpdate.project_id == m.project_id,
        ProgressUpdate.publication_state == "published",
        ProgressUpdate.published_at <= m.occurred_at,
    )
    if prev is not None:
        uq = uq.filter(ProgressUpdate.published_at > prev.occurred_at)
    if member_id is not None:
        uq = uq.filter(ProgressUpdate.author_id == member_id)
    updates = uq.order_by(ProgressUpdate.published_at.desc()).all()

    def action_in_scope(a: ActionItem) -> bool:
        return member_id is None or a.assignee_id == member_id

    previous_commitments = []
    if prev is not None:
        previous_commitments = sorted(
            [a for a in db.query(ActionItem).filter(ActionItem.source_meeting_id == prev.id) if action_in_scope(a)],
            key=action_sort_key,
        )
    excluded_sources = {m.id} | ({prev.id} if prev else set())
    carried_over = sorted(
        [
            a
            for a in db.query(ActionItem).filter(
                ActionItem.project_id == m.project_id,
                ActionItem.state.in_(("open", "in_progress")),
                ActionItem.created_at <= max(m.occurred_at, utcnow()),
            )
            if a.source_meeting_id not in excluded_sources and action_in_scope(a)
        ],
        key=action_sort_key,
    )

    def blocker_in_scope(b: Blocker) -> bool:
        if b.goal_id not in shared_goal_ids:
            return False
        return member_id is None or b.reported_by == member_id or b.goal_id in (member_goal_ids or set())

    open_blockers = [
        b for b in db.query(Blocker).filter(Blocker.project_id == m.project_id, Blocker.state == "open")
        .order_by(Blocker.opened_at) if blocker_in_scope(b)
    ]
    rq = db.query(Blocker).filter(
        Blocker.project_id == m.project_id, Blocker.state == "resolved", Blocker.resolved_at <= m.occurred_at
    )
    if prev is not None:
        rq = rq.filter(Blocker.resolved_at > prev.occurred_at)
    resolved_in_window = [b for b in rq.order_by(Blocker.resolved_at.desc()) if blocker_in_scope(b)]

    prev_outcomes = []
    if prev is not None:
        prev_outcomes = (
            db.query(MeetingOutcome)
            .filter(MeetingOutcome.meeting_id == prev.id)
            .order_by(MeetingOutcome.created_at, MeetingOutcome.id)
            .all()
        )
        if member_id is not None:
            prev_outcomes = [
                o for o in prev_outcomes if o.goal_id is None or o.goal_id in (member_goal_ids or set())
            ]

    return {
        "meeting": ser.meeting(m),
        "member": ser.user(member_id),
        "is_first_meeting": prev is None,
        "previous_meeting": ser.meeting(prev) if prev else None,
        "window": {"start": prev.occurred_at if prev else None, "end": m.occurred_at},
        "previous_outcomes": [ser.outcome(o) for o in prev_outcomes],
        "previous_commitments": [ser.action(a) for a in previous_commitments],
        "carried_over_actions": [ser.action(a) for a in carried_over],
        "updates": [ser.update(u) for u in updates],
        "open_blockers": [ser.blocker(b) for b in open_blockers],
        "resolved_blockers": [ser.blocker(b) for b in resolved_in_window],
        "agenda": m.agenda,
    }


# ---------------- outcomes ----------------
@router.post("/meetings/{meeting_id}/outcomes", status_code=201)
def create_outcome(meeting_id: int, body: OutcomeIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m, mem = load_in_project(db, user, Meeting, meeting_id)
    goal = load_shared_goal_in_project(db, user, body.goal_id, m.project_id) if body.goal_id else None
    now = utcnow()
    is_advisor = mem.role == "advisor"
    o = MeetingOutcome(
        meeting_id=m.id, goal_id=goal.id if goal else None, decision=body.decision, rationale=body.rationale,
        feedback=body.feedback, author_id=user.id,
        confirmation_state="confirmed" if is_advisor else "pending",
        confirmed_by=user.id if is_advisor else None, confirmed_at=now if is_advisor else None,
    )
    db.add(o)
    db.flush()
    events.record(
        db, project_id=m.project_id, actor_id=user.id, event_type="outcome_recorded", entity_type="outcome",
        entity_id=o.id, goal=goal, meeting_category=m.category,
        summary=f"【{m.title}】決策：{events.short(o.decision, 100)}" + ("" if is_advisor else "（待指導者確認）"),
    )
    db.commit()
    return Ser(db).outcome(o)


def _load_outcome(db: Session, user: User, outcome_id: int):
    o = db.get(MeetingOutcome, outcome_id)
    if o is None:
        raise HTTPException(404, NOT_FOUND)
    m, mem = load_in_project(db, user, Meeting, o.meeting_id)
    return o, m, mem


@router.patch("/outcomes/{outcome_id}")
def edit_outcome(outcome_id: int, body: OutcomePatch, db: Session = Depends(get_db), user: User = Depends(current_user)):
    o, m, _ = _load_outcome(db, user, outcome_id)
    if o.author_id != user.id or o.confirmation_state != "pending":
        raise HTTPException(400, "只有作者能修改尚未確認的紀錄；已確認的決策請以留言補充")
    for field in ("decision", "rationale", "feedback"):
        value = getattr(body, field)
        if value is not None:
            setattr(o, field, value)
    o.updated_at = utcnow()
    goal = db.get(Goal, o.goal_id) if o.goal_id else None
    events.record(
        db, project_id=m.project_id, actor_id=user.id, event_type="outcome_revised", entity_type="outcome",
        entity_id=o.id, goal=goal, meeting_category=m.category,
        summary=f"【{m.title}】修改決策草稿：{events.short(o.decision, 100)}",
    )
    db.commit()
    return Ser(db).outcome(o)


@router.post("/outcomes/{outcome_id}/confirm")
def confirm_outcome(outcome_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    o, m, mem = _load_outcome(db, user, outcome_id)
    if mem.role != "advisor":
        raise HTTPException(403, "只有指導者可以確認 meeting 結論")
    if o.confirmation_state == "confirmed":
        raise HTTPException(400, "此紀錄已確認")
    o.confirmation_state, o.confirmed_by, o.confirmed_at = "confirmed", user.id, utcnow()
    goal = db.get(Goal, o.goal_id) if o.goal_id else None
    events.record(
        db, project_id=m.project_id, actor_id=user.id, event_type="outcome_confirmed", entity_type="outcome",
        entity_id=o.id, goal=goal, meeting_category=m.category,
        summary=f"【{m.title}】確認決策：{events.short(o.decision, 100)}",
    )
    db.commit()
    return Ser(db).outcome(o)


@router.post("/outcomes/{outcome_id}/comments", status_code=201)
def comment_outcome(outcome_id: int, body: CommentIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    o, m, _ = _load_outcome(db, user, outcome_id)
    db.add(OutcomeComment(outcome_id=o.id, author_id=user.id, body=body.body))
    goal = db.get(Goal, o.goal_id) if o.goal_id else None
    events.record(
        db, project_id=m.project_id, actor_id=user.id, event_type="outcome_commented", entity_type="outcome",
        entity_id=o.id, goal=goal, meeting_category=m.category,
        summary=f"【{m.title}】回饋：{events.short(body.body, 100)}",
    )
    db.commit()
    return Ser(db).outcome(o)
