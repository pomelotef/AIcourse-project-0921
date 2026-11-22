"""Request bodies. Responses are plain dicts built in app/serialize.py."""

from datetime import date
from typing import Literal
from urllib.parse import urlparse

from typing import Annotated

from pydantic import AwareDatetime, BaseModel, Field, field_validator

Role = Literal["advisor", "student"]
GoalState = Literal["planned", "investigating", "partially_answered", "answered", "needs_revisit", "archived"]
Visibility = Literal["shared", "private"]
BlockerState = Literal["open", "resolved"]
ActionState = Literal["open", "in_progress", "done", "canceled"]
Priority = Literal["high", "medium", "low"]
MeetingCategory = Literal["lab", "industry", "one_on_one", "other"]
LinkType = Literal["general", "experiment", "code", "document", "data"]
LinkTarget = Literal["goal", "update", "blocker"]

# Syntax-only email check: lab/school/internal domains must not be rejected.
EmailStr = Annotated[str, Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+$")]

Title = Field(min_length=1, max_length=200)
LongText = Field(default="", max_length=10000)


class _Strip(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


# ---- auth ----
class RegisterIn(_Strip):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=200)


class LoginIn(_Strip):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


# ---- projects ----
class ProjectIn(_Strip):
    title: str = Title
    description: str = LongText
    creator_role: Role = "advisor"


class ProjectPatch(_Strip):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    state: Literal["active", "archived"] | None = None


class MemberIn(_Strip):
    email: EmailStr
    role: Role = "student"


class MemberPatch(BaseModel):
    role: Role


# ---- goals ----
class GoalIn(_Strip):
    title: str = Title
    research_question: str = LongText
    parent_id: int | None = None
    assignee_id: int | None = None
    research_state: GoalState = "planned"
    visibility: Visibility = "shared"


class GoalPatch(_Strip):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    research_question: str | None = Field(default=None, max_length=10000)
    parent_id: int | None = None
    assignee_id: int | None = None
    research_state: GoalState | None = None
    visibility: Visibility | None = None


# ---- links ----
def _check_url(v: str) -> str:
    parsed = urlparse(v)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("連結必須是 http:// 或 https:// 開頭的網址")
    return v


class LinkIn(_Strip):
    url: str = Field(min_length=1, max_length=2000)
    label: str = Field(default="", max_length=200)
    link_type: LinkType = "general"

    @field_validator("url")
    @classmethod
    def _valid_url(cls, v: str) -> str:
        return _check_url(v)


class LinkCreate(LinkIn):
    target_type: LinkTarget
    target_id: int


# ---- progress updates ----
class NewBlockerIn(_Strip):
    title: str = Title
    description: str = LongText


class UpdateIn(_Strip):
    completed: str = LongText
    findings: str = LongText
    next_steps: str = LongText
    no_blocker: bool = False
    referenced_blocker_ids: list[int] = Field(default_factory=list, max_length=50)
    new_blockers: list[NewBlockerIn] = Field(default_factory=list, max_length=20)
    links: list[LinkIn] = Field(default_factory=list, max_length=20)
    publish: bool = False


# ---- blockers ----
class BlockerIn(_Strip):
    title: str = Title
    description: str = LongText


class BlockerPatch(_Strip):
    state: BlockerState | None = None
    resolution: str | None = Field(default=None, max_length=10000)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)


# ---- actions ----
class ActionIn(_Strip):
    title: str = Field(min_length=1, max_length=300)
    goal_id: int | None = None
    source_meeting_id: int | None = None
    source_update_id: int | None = None
    assignee_id: int
    priority: Priority = "medium"
    due_date: date | None = None


class ActionPatch(_Strip):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    assignee_id: int | None = None
    priority: Priority | None = None
    state: ActionState | None = None
    due_date: date | None = None
    clear_due_date: bool = False
    note: str | None = Field(default=None, max_length=10000)
    # Required when canceling or when moving an existing due date.
    reason: str = Field(default="", max_length=2000)


# ---- meetings ----
class MeetingIn(_Strip):
    title: str = Title
    category: MeetingCategory = "lab"
    occurred_at: AwareDatetime
    agenda: str = LongText
    participant_ids: list[int] = Field(default_factory=list, max_length=100)


class MeetingPatch(_Strip):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    category: MeetingCategory | None = None
    occurred_at: AwareDatetime | None = None
    agenda: str | None = Field(default=None, max_length=10000)
    participant_ids: list[int] | None = Field(default=None, max_length=100)


class OutcomeIn(_Strip):
    goal_id: int | None = None
    decision: str = Field(min_length=1, max_length=10000)
    rationale: str = LongText
    feedback: str = LongText


class OutcomePatch(_Strip):
    decision: str | None = Field(default=None, min_length=1, max_length=10000)
    rationale: str | None = Field(default=None, max_length=10000)
    feedback: str | None = Field(default=None, max_length=10000)


class CommentIn(_Strip):
    body: str = Field(min_length=1, max_length=5000)


# ---- private notes ----
class NoteIn(_Strip):
    body: str = Field(min_length=1, max_length=10000)
    goal_id: int | None = None


class NotePatch(_Strip):
    body: str = Field(min_length=1, max_length=10000)
