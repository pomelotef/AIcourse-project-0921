"""Live refresh: tell open browser tabs that a project changed, over Server-Sent Events.

How it works:

1. A SQLAlchemy ``after_flush`` hook looks at every row a request inserts, updates or deletes and
   notes which project it belongs to (and, for private rows, which single user may see it).
2. Only after the transaction commits, ``after_commit`` turns those notes into recipient user ids
   (current project members) and pushes a tiny message to each of their open streams.
3. The browser never receives data here, only "project N changed". It then re-fetches through the
   normal API, so every permission check in ``perms.py`` still applies.

Hooking the ORM (instead of calling a notify function in every route) means a new write endpoint
gets live refresh for free. The hub keeps subscribers in memory, so it only works with a single
server process; several workers would need Redis pub/sub or PostgreSQL LISTEN/NOTIFY instead.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections.abc import AsyncIterator

from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from .models import (
    ActivityEvent,
    Blocker,
    ExternalLink,
    Goal,
    Meeting,
    MeetingOutcome,
    MeetingParticipant,
    OutcomeComment,
    PrivateNote,
    ProgressUpdate,
    Project,
    ProjectMember,
    UpdateBlocker,
)

log = logging.getLogger(__name__)

PING_SECONDS = 15.0
QUEUE_SIZE = 64
_PENDING = "live_pending"

# A "touch" is (kind, id, only_user). kind is "project" or a parent row we resolve to a project
# after commit; only_user=None means every project member, otherwise just that user.
Touch = tuple[str, int, int | None]


# ---------------------------------------------------------------- hub
class Hub:
    """In-memory fan-out from any thread to asyncio queues owned by open SSE responses."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: dict[int, set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = {}

    def subscribe(self, user_id: int, loop: asyncio.AbstractEventLoop | None = None) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        entry = (loop or asyncio.get_running_loop(), q)
        with self._lock:
            self._subs.setdefault(user_id, set()).add(entry)
        return q

    def unsubscribe(self, user_id: int, q: asyncio.Queue) -> None:
        with self._lock:
            subs = self._subs.get(user_id, set())
            for entry in [e for e in subs if e[1] is q]:
                subs.discard(entry)
            if not subs:
                self._subs.pop(user_id, None)

    def has_subscribers(self) -> bool:
        with self._lock:
            return bool(self._subs)

    def publish(self, messages: dict[int, dict]) -> None:
        """messages: user_id -> payload. Safe to call from worker threads."""
        with self._lock:
            targets = [(e, messages[uid]) for uid, subs in self._subs.items() if uid in messages for e in subs]
        for (loop, q), payload in targets:
            try:
                loop.call_soon_threadsafe(_offer, q, payload)
            except RuntimeError:  # loop already closed: the stream is going away anyway
                pass


def _offer(q: asyncio.Queue, payload: dict) -> None:
    # A full queue means the tab is not reading; it refreshes on the next message anyway.
    try:
        q.put_nowait(payload)
    except asyncio.QueueFull:
        pass


hub = Hub()


# ---------------------------------------------------------------- what changed
def _goal_is_private(obj: Goal) -> bool:
    """Private now and not just switched from shared (others must refresh to see it disappear)."""
    if obj.visibility != "private":
        return False
    hist = inspect(obj).attrs.visibility.history
    return "shared" not in (hist.deleted or ())


def _touches_for(obj, deleted: bool) -> list[Touch]:
    if isinstance(obj, PrivateNote):
        return [("project", obj.project_id, obj.author_id)]
    if isinstance(obj, ProgressUpdate):
        only = obj.author_id if obj.publication_state == "draft" else None
        return [("project", obj.project_id, only)]
    if isinstance(obj, Goal):
        return [("project", obj.project_id, obj.created_by if _goal_is_private(obj) else None)]
    if isinstance(obj, ActivityEvent):
        return [("project", obj.project_id, obj.private_to)]
    if isinstance(obj, ProjectMember):
        touches: list[Touch] = [("project", obj.project_id, None)]
        if deleted:  # no longer a member, but their open page should still update
            touches.append(("project", obj.project_id, obj.user_id))
        return touches
    if isinstance(obj, Project):
        return [] if obj.id is None else [("project", obj.id, None)]
    if isinstance(obj, (MeetingParticipant, MeetingOutcome)):
        return [("meeting", obj.meeting_id, None)]
    if isinstance(obj, OutcomeComment):
        return [("outcome", obj.outcome_id, None)]
    if isinstance(obj, UpdateBlocker):
        return [("update", obj.update_id, None)]
    if isinstance(obj, ExternalLink):
        # A link is as private as what it hangs on (a private goal, a draft update).
        return [(f"link-{obj.target_type}", obj.target_id, None)]
    project_id = getattr(obj, "project_id", None)
    return [("project", project_id, None)] if project_id is not None else []


@event.listens_for(Session, "after_flush")
def _collect(session: Session, _ctx) -> None:
    pending: set[Touch] = session.info.setdefault(_PENDING, set())
    for objs, deleted in ((session.new, False), (session.dirty, False), (session.deleted, True)):
        for obj in objs:
            if objs is session.dirty and not session.is_modified(obj, include_collections=False):
                continue
            for t in _touches_for(obj, deleted):
                if t[1] is not None:
                    pending.add(t)


@event.listens_for(Session, "after_rollback")
def _discard(session: Session) -> None:
    session.info.pop(_PENDING, None)


@event.listens_for(Session, "after_commit")
def _dispatch(session: Session) -> None:
    pending: set[Touch] | None = session.info.pop(_PENDING, None)
    if not pending or not hub.has_subscribers():
        return
    try:
        # The committed session is mid-teardown; read membership with a short-lived one.
        with Session(bind=session.get_bind()) as db:
            hub.publish(_recipients(db, pending))
    except Exception:  # never turn a successful write into an error response
        log.exception("live refresh dispatch failed")


def _recipients(db: Session, pending: set[Touch]) -> dict[int, dict]:
    # Each resolver returns (project_id, only_user): the parent row decides who may see the change.
    def update_scope(i: int) -> tuple[int | None, int | None]:
        u = db.get(ProgressUpdate, i)  # a draft (and whatever hangs off it) is still the author's alone
        if u is None:
            return None, None
        return u.project_id, (u.author_id if u.publication_state == "draft" else None)

    def goal_scope(i: int) -> tuple[int | None, int | None]:
        g = db.get(Goal, i)
        if g is None:
            return None, None
        return g.project_id, (g.created_by if g.visibility == "private" else None)

    parents = {
        "meeting": lambda i: (db.scalar(select(Meeting.project_id).where(Meeting.id == i)), None),
        "outcome": lambda i: (
            db.scalar(
                select(Meeting.project_id)
                .join(MeetingOutcome, MeetingOutcome.meeting_id == Meeting.id)
                .where(MeetingOutcome.id == i)
            ),
            None,
        ),
        "update": update_scope,
        "link-update": update_scope,
        "link-goal": goal_scope,
        "link-blocker": lambda i: (db.scalar(select(Blocker.project_id).where(Blocker.id == i)), None),
    }
    per_user: dict[int, set[int]] = {}
    members_cache: dict[int, list[int]] = {}
    for kind, ident, only_user in pending:
        if kind == "project":
            pid = ident
        else:
            pid, scoped = parents[kind](ident)
            only_user = only_user if only_user is not None else scoped
        if pid is None:
            continue
        if only_user is not None:
            users = [only_user]
        else:
            if pid not in members_cache:
                members_cache[pid] = list(
                    db.scalars(select(ProjectMember.user_id).where(ProjectMember.project_id == pid))
                )
            users = members_cache[pid]
        for uid in users:
            per_user.setdefault(uid, set()).add(pid)
    return {uid: {"projects": sorted(pids)} for uid, pids in per_user.items()}


# ---------------------------------------------------------------- SSE stream
def _sse(event_name: str, data: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data)}\n\n"


async def stream(user_id: int) -> AsyncIterator[str]:
    q = hub.subscribe(user_id)
    try:
        # "ready" on every (re)connect lets the page catch up on anything missed while offline.
        yield "retry: 3000\n\n" + _sse("ready", {})
        while True:
            try:
                payload = await asyncio.wait_for(q.get(), PING_SECONDS)
            except TimeoutError:
                yield ": ping\n\n"  # keeps proxies from closing an idle connection
                continue
            yield _sse("changed", payload)
    finally:
        hub.unsubscribe(user_id, q)
