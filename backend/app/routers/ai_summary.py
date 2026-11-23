"""AI summary of a Meeting Brief.

The records come from meeting_brief() itself, so the model sees exactly what the Brief shows
every member and nothing more: published updates only, blockers on shared goals only, and no
drafts, private notes or private goals. Member names are not sent, only each author's role.
The prompt, template and validator live in app/ai/brief_summary.py.
"""

import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..ai import brief_summary, llm
from ..db import get_db
from ..models import ProjectMember, User
from ..security import current_user
from .meetings import meeting_brief

router = APIRouter(prefix="/api", tags=["ai"])
log = logging.getLogger(__name__)

ACTION_STATE = {"open": "未開始", "in_progress": "進行中", "done": "已完成", "canceled": "已取消"}
PRIORITY = {"high": "高", "medium": "中", "low": "低"}


def get_summary_client():
    """The model client, or None when no API key is set. Tests replace it with a fake."""
    return llm.get_client()


def _day(value) -> str:
    """A calendar date in Taiwan time (UTC+8), like the rest of the app."""
    if isinstance(value, datetime):
        return (value.astimezone(timezone.utc) + timedelta(hours=8)).date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return ""


def _goal(item: dict) -> str:
    return item["goal"]["title"] if item.get("goal") else "整個專案"


def _join(*parts: str) -> str:
    return "；".join(p for p in parts if p)


def brief_records(brief: dict, roles: dict[int, str]) -> list[dict]:
    """Turn the serialized Brief into the records the summary module expects.

    IDs: P = progress update, B = blocker, A = action item, D = decision of the previous meeting.
    Each record also gets a short Chinese label so the page can show what a cited ID refers to.
    """
    def role(user: dict | None) -> str:
        return roles.get(user["id"], "member") if user else "member"

    records = []
    for u in brief["updates"]:
        text = _join(
            f"完成：{u['completed']}" if u["completed"] else "",
            f"發現：{u['findings']}" if u["findings"] else "",
            f"下一步：{u['next_steps']}" if u["next_steps"] else "",
            "回報沒有阻礙" if u["no_blocker"] else "",
        ) or "（沒有內容）"
        records.append({"id": f"P{u['id']}", "type": "progress", "date": _day(u["published_at"]),
                        "author_role": role(u["author"]), "goal": _goal(u), "text": text,
                        "label": f"進度更新 · {_goal(u)}"})
    for b in brief["open_blockers"]:
        records.append({"id": f"B{b['id']}", "type": "blocker", "date": _day(b["opened_at"]),
                        "author_role": role(b["reported_by"]), "goal": _goal(b),
                        "text": _join(b["title"], b["description"]), "label": f"Blocker：{b['title']}"})
    for b in brief["resolved_blockers"]:
        records.append({"id": f"B{b['id']}", "type": "progress", "date": _day(b["resolved_at"]),
                        "author_role": role(b["resolved_by"]), "goal": _goal(b),
                        "text": _join(f"已解決的阻礙：{b['title']}", f"解法：{b['resolution']}" if b["resolution"] else ""),
                        "label": f"已解決的 Blocker：{b['title']}"})
    for a in brief["previous_commitments"] + brief["carried_over_actions"]:
        status = f"狀態：{ACTION_STATE.get(a['state'], a['state'])}，優先度：{PRIORITY.get(a['priority'], a['priority'])}，" \
                 f"期限：{_day(a['due_date']) or '未設定'}" + ("，已逾期" if a.get("overdue") else "")
        records.append({"id": f"A{a['id']}", "type": "action", "date": _day(a["created_at"]),
                        "author_role": role(a["assignee"]), "goal": _goal(a),
                        "text": _join(a["title"], status, f"備註：{a['note']}" if a["note"] else ""),
                        "label": f"待辦：{a['title']}"})
    for o in brief["previous_outcomes"]:
        pending = "（待指導者確認）" if o["confirmation_state"] == "pending" else ""
        records.append({"id": f"D{o['id']}", "type": "decision", "date": _day(o["created_at"]),
                        "author_role": role(o["author"]), "goal": _goal(o),
                        "text": _join(o["decision"] + pending, f"理由：{o['rationale']}" if o["rationale"] else "",
                                      f"回饋：{o['feedback']}" if o["feedback"] else ""),
                        "label": f"上次決策：{o['decision'][:30]}"})
    return records


@router.post("/meetings/{meeting_id}/brief/ai-summary")
def brief_ai_summary(
    meeting_id: int,
    member_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    client=Depends(get_summary_client),
):
    # Same permission checks and filters as GET /brief: outsiders get 404 before anything else.
    brief = meeting_brief(meeting_id, member_id, db, user)
    if client is None:
        return {"status": "disabled", "summary": "", "points": [], "records": {}}
    roles = {
        pm.user_id: pm.role
        for pm in db.query(ProjectMember).filter(ProjectMember.project_id == brief["meeting"]["project_id"])
    }
    records = brief_records(brief, roles)
    result = brief_summary.summarize(client, records)
    if result["status"] == "unavailable":
        log.warning("AI summary unavailable for meeting %s: %s", meeting_id,
                    [a["problems"] for a in result["attempts"]])
    labels = {r["id"]: r["label"] for r in records}
    cited = {rid for p in result["points"] for rid in p["record_ids"]}
    return {
        "status": result["status"],
        "summary": result["summary"],
        "points": result["points"],
        "records": {rid: labels[rid] for rid in sorted(cited)},
    }
