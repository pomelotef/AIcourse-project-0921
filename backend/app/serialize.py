"""Turn ORM rows into JSON-ready dicts. Callers are responsible for visibility filtering."""

from sqlalchemy.orm import Session

from .routers.common import is_overdue, taipei_today
from .models import (
    ActionItem,
    ActivityEvent,
    Blocker,
    ExternalLink,
    Goal,
    Meeting,
    MeetingOutcome,
    MeetingParticipant,
    OutcomeComment,
    ProgressUpdate,
    UpdateBlocker,
    User,
)


class Ser:
    def __init__(self, db: Session):
        self.db = db
        self._users: dict[int, dict] = {}
        self._goals: dict[int, Goal | None] = {}
        self._meetings: dict[int, Meeting | None] = {}
        self.today = taipei_today()

    # ---- references ----
    def user(self, uid: int | None) -> dict | None:
        if uid is None:
            return None
        if uid not in self._users:
            u = self.db.get(User, uid)
            self._users[uid] = {"id": u.id, "name": u.name} if u else {"id": uid, "name": "(已刪除)"}
        return self._users[uid]

    def _goal(self, gid: int | None) -> Goal | None:
        if gid is None:
            return None
        if gid not in self._goals:
            self._goals[gid] = self.db.get(Goal, gid)
        return self._goals[gid]

    def goal_ref(self, gid: int | None) -> dict | None:
        g = self._goal(gid)
        return {"id": g.id, "title": g.title} if g else None

    def meeting_ref(self, mid: int | None) -> dict | None:
        if mid is None:
            return None
        if mid not in self._meetings:
            self._meetings[mid] = self.db.get(Meeting, mid)
        m = self._meetings[mid]
        if m is None:
            return None
        return {"id": m.id, "title": m.title, "category": m.category, "occurred_at": m.occurred_at}

    def links(self, target_type: str, target_id: int) -> list[dict]:
        rows = (
            self.db.query(ExternalLink)
            .filter(ExternalLink.target_type == target_type, ExternalLink.target_id == target_id)
            .order_by(ExternalLink.id)
            .all()
        )
        return [
            {"id": l.id, "url": l.url, "label": l.label, "link_type": l.link_type, "created_by": l.created_by}
            for l in rows
        ]

    # ---- records ----
    def goal(self, g: Goal) -> dict:
        return {
            "id": g.id,
            "project_id": g.project_id,
            "parent_id": g.parent_id,
            "title": g.title,
            "research_question": g.research_question,
            "assignee": self.user(g.assignee_id),
            "research_state": g.research_state,
            "visibility": g.visibility,
            "created_by": self.user(g.created_by),
            "created_at": g.created_at,
            "updated_at": g.updated_at,
        }

    def blocker(self, b: Blocker) -> dict:
        ref_count = self.db.query(UpdateBlocker).filter(UpdateBlocker.blocker_id == b.id).count()
        return {
            "id": b.id,
            "project_id": b.project_id,
            "goal": self.goal_ref(b.goal_id),
            "reported_by": self.user(b.reported_by),
            "title": b.title,
            "description": b.description,
            "state": b.state,
            "opened_at": b.opened_at,
            "resolved_at": b.resolved_at,
            "resolved_by": self.user(b.resolved_by),
            "resolution": b.resolution,
            "reference_count": ref_count,
            "links": self.links("blocker", b.id),
        }

    def update(self, u: ProgressUpdate) -> dict:
        blocker_ids = [r.blocker_id for r in self.db.query(UpdateBlocker).filter(UpdateBlocker.update_id == u.id)]
        blockers = [self.db.get(Blocker, bid) for bid in blocker_ids]
        return {
            "id": u.id,
            "project_id": u.project_id,
            "goal": self.goal_ref(u.goal_id),
            "author": self.user(u.author_id),
            "completed": u.completed,
            "findings": u.findings,
            "next_steps": u.next_steps,
            "no_blocker": u.no_blocker,
            "draft_blockers": u.draft_blockers or [],
            "blockers": [{"id": b.id, "title": b.title, "state": b.state} for b in blockers if b],
            "publication_state": u.publication_state,
            "created_at": u.created_at,
            "updated_at": u.updated_at,
            "published_at": u.published_at,
            "links": self.links("update", u.id),
        }

    def action(self, a: ActionItem) -> dict:
        return {
            "id": a.id,
            "project_id": a.project_id,
            "goal": self.goal_ref(a.goal_id),
            "source_meeting": self.meeting_ref(a.source_meeting_id),
            "source_update_id": a.source_update_id,
            "title": a.title,
            "assignee": self.user(a.assignee_id),
            "priority": a.priority,
            "state": a.state,
            "due_date": a.due_date,
            "note": a.note,
            "created_by": self.user(a.created_by),
            "created_at": a.created_at,
            "updated_at": a.updated_at,
            "closed_at": a.closed_at,
            "overdue": is_overdue(a, self.today),
        }

    def meeting(self, m: Meeting) -> dict:
        pids = [
            p.user_id for p in self.db.query(MeetingParticipant).filter(MeetingParticipant.meeting_id == m.id)
        ]
        return {
            "id": m.id,
            "project_id": m.project_id,
            "title": m.title,
            "category": m.category,
            "occurred_at": m.occurred_at,
            "agenda": m.agenda,
            "participants": [self.user(pid) for pid in pids],
            "created_by": self.user(m.created_by),
            "created_at": m.created_at,
        }

    def outcome(self, o: MeetingOutcome) -> dict:
        comments = (
            self.db.query(OutcomeComment)
            .filter(OutcomeComment.outcome_id == o.id)
            .order_by(OutcomeComment.created_at, OutcomeComment.id)
            .all()
        )
        return {
            "id": o.id,
            "meeting": self.meeting_ref(o.meeting_id),
            "goal": self.goal_ref(o.goal_id),
            "decision": o.decision,
            "rationale": o.rationale,
            "feedback": o.feedback,
            "author": self.user(o.author_id),
            "confirmation_state": o.confirmation_state,
            "confirmed_by": self.user(o.confirmed_by),
            "confirmed_at": o.confirmed_at,
            "created_at": o.created_at,
            "updated_at": o.updated_at,
            "comments": [
                {"id": c.id, "author": self.user(c.author_id), "body": c.body, "created_at": c.created_at}
                for c in comments
            ],
        }

    def event(self, e: ActivityEvent) -> dict:
        return {
            "id": e.id,
            "project_id": e.project_id,
            "goal": self.goal_ref(e.goal_id),
            "actor": self.user(e.actor_id),
            "event_type": e.event_type,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "summary": e.summary,
            "meeting_category": e.meeting_category,
            "private": e.private_to is not None,
            "created_at": e.created_at,
        }
