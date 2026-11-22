"""Demo data. EVERYTHING HERE IS FICTIONAL - it is not interview evidence or real research.

Accounts (local demo only; password for all: demo1234):
  advisor@demo.labpulse   王老師（示範）  advisor of both projects
  alice@demo.labpulse     Alice（示範）   student
  bob@demo.labpulse       Bob（示範）     student
  carol@demo.labpulse     Carol（示範）   student, RAG project only

Dates are relative to "now" so that the meeting brief always shows a meaningful window.
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from . import events
from .db import Base, SessionLocal, engine
from .models import (
    ActionItem,
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
    User,
    utcnow,
)
from .security import hash_password

DEMO_PASSWORD = "demo1234"
DEMO_TAG = "【示範資料】"


def _ago(days: float, hours: float = 0):
    return utcnow() - timedelta(days=days, hours=hours)


def seed(db: Session) -> None:
    if db.query(User).filter(User.email == "advisor@demo.labpulse").first():
        print("Demo data already present; use --reset to rebuild.")
        return

    pw = hash_password(DEMO_PASSWORD)
    prof = User(email="advisor@demo.labpulse", name="王老師（示範）", password_hash=pw)
    alice = User(email="alice@demo.labpulse", name="Alice（示範）", password_hash=pw)
    bob = User(email="bob@demo.labpulse", name="Bob（示範）", password_hash=pw)
    carol = User(email="carol@demo.labpulse", name="Carol（示範）", password_hash=pw)
    db.add_all([prof, alice, bob, carol])
    db.flush()

    # ---------------- Project 1 ----------------
    p1 = Project(title="On-device LLM Memory", created_by=prof.id, created_at=_ago(30),
                 description=f"{DEMO_TAG}研究地端 LLM 推論時的記憶體行為與加速器影響。")
    db.add(p1)
    db.flush()
    for u, role in ((prof, "advisor"), (alice, "student"), (bob, "student")):
        db.add(ProjectMember(project_id=p1.id, user_id=u.id, role=role, created_at=_ago(30)))
    events.record(db, project_id=p1.id, actor_id=prof.id, event_type="project_created", entity_type="project",
                  entity_id=p1.id, summary=f"建立專案「{p1.title}」", at=_ago(30))

    def goal(title, question, assignee, state, parent=None, by=prof, visibility="shared", days=28):
        g = Goal(project_id=p1.id, parent_id=parent.id if parent else None,
                 title=title, research_question=question, assignee_id=assignee.id if assignee else None,
                 research_state=state, visibility=visibility, created_by=by.id,
                 created_at=_ago(days), updated_at=_ago(days))
        db.add(g)
        db.flush()
        events.record(db, project_id=g.project_id, actor_id=by.id, event_type="goal_created", entity_type="goal",
                      entity_id=g.id, goal=g, at=_ago(days),
                      summary=f"新增研究目標「{g.title}」" + (f"，負責人：{assignee.name}" if assignee else ""))
        return g

    g_mem = goal("Memory Characterization", "不同模型在地端推論時的記憶體使用特徵為何？", None, "investigating")
    g_gemma = goal("Gemma / Llama 記憶體比較", "Gemma 與 Llama 在相同量化設定下的峰值記憶體差異？", alice,
                   "partially_answered", parent=g_mem)
    g_acc = goal("Accelerator Analysis", "加速器如何影響地端 LLM 推論的記憶體行為？", None, "investigating")
    g_vulkan = goal("Vulkan backend profiling", "使用 Vulkan backend 時記憶體配置與 CPU backend 有何不同？", alice,
                    "investigating", parent=g_acc)
    g_llama = goal("Llama KV cache 行為", "KV cache 大小隨 context length 的成長是否線性？", bob, "investigating",
                   parent=g_mem)
    goal("Memory Optimization", "有哪些可行的記憶體最佳化策略？", None, "planned", days=20)
    g_private = goal("下學期計畫申請方向（私人）", "只有老師自己看得到的長期規劃。", prof, "planned",
                     visibility="private", days=10)
    db.add(PrivateNote(project_id=p1.id, goal_id=g_private.id, author_id=prof.id,
                       body=f"{DEMO_TAG}考慮把 Vulkan 結果整理成計畫書的初步成果。（私人筆記）"))

    # Meeting 1 (lab) - 14 days ago
    m1 = Meeting(project_id=p1.id, title="Lab Meeting #1", category="lab", occurred_at=_ago(14),
                 agenda="確認研究問題與分工", created_by=prof.id, created_at=_ago(14))
    db.add(m1)
    db.flush()
    for u in (prof, alice, bob):
        db.add(MeetingParticipant(meeting_id=m1.id, user_id=u.id))
    events.record(db, project_id=p1.id, actor_id=prof.id, event_type="meeting_created", entity_type="meeting",
                  entity_id=m1.id, meeting_category="lab", summary=f"建立 Lab Meeting「{m1.title}」", at=_ago(14))
    o1 = MeetingOutcome(meeting_id=m1.id, goal_id=g_acc.id, decision="先比較 Gemma / Llama，再做 Vulkan profiling",
                        rationale="需要先有 CPU baseline 才能解讀加速器結果", feedback="記得固定量化設定",
                        author_id=prof.id, confirmation_state="confirmed", confirmed_by=prof.id,
                        confirmed_at=_ago(14), created_at=_ago(14))
    db.add(o1)
    db.flush()
    events.record(db, project_id=p1.id, actor_id=prof.id, event_type="outcome_recorded", entity_type="outcome",
                  entity_id=o1.id, goal=g_acc, meeting_category="lab", at=_ago(14),
                  summary=f"【{m1.title}】決策：{o1.decision}")

    def action(title, assignee, g, meeting, priority, due, state="open", days=14, note=""):
        a = ActionItem(project_id=p1.id, goal_id=g.id if g else None, source_meeting_id=meeting.id if meeting else None,
                       title=title, assignee_id=assignee.id, priority=priority, due_date=due, state=state, note=note,
                       created_by=prof.id, created_at=_ago(days), updated_at=_ago(days),
                       closed_at=_ago(3) if state in ("done", "canceled") else None)
        db.add(a)
        db.flush()
        events.record(db, project_id=p1.id, actor_id=prof.id, event_type="action_created", entity_type="action",
                      entity_id=a.id, goal=g, meeting_category=meeting.category if meeting else None, at=_ago(days),
                      summary=f"新增待辦「{a.title}」→ {assignee.name}")
        return a

    today = date.today()
    a1 = action("比較 Gemma / Llama 峰值記憶體", alice, g_gemma, m1, "high", today - timedelta(days=5), state="done",
                note="結果已整理在實驗紀錄")
    events.record(db, project_id=p1.id, actor_id=alice.id, event_type="action_updated", entity_type="action",
                  entity_id=a1.id, goal=g_gemma, meeting_category="lab", at=_ago(3),
                  summary=f"待辦「{a1.title}」狀態：待處理 → 已完成")
    action("執行 Vulkan profiling", alice, g_vulkan, m1, "high", today + timedelta(days=2))
    action("量測 KV cache 隨 context 成長", bob, g_llama, m1, "medium", today - timedelta(days=1))
    action("整理相關論文列表", bob, None, None, "low", None, days=20)

    # Updates between meeting 1 and now
    u1 = ProgressUpdate(project_id=p1.id, goal_id=g_gemma.id, author_id=alice.id,
                        completed="完成 Gemma 2B 與 Llama 3 8B 在 4-bit 量化下的峰值記憶體量測",
                        findings="Gemma 峰值記憶體約低 18%，但 context 拉長後差距縮小（示範數據）",
                        next_steps="把量測腳本參數化，準備 Vulkan 比較", no_blocker=True,
                        publication_state="published", created_at=_ago(6), updated_at=_ago(6), published_at=_ago(6))
    db.add(u1)
    db.flush()
    db.add(ExternalLink(project_id=p1.id, target_type="update", target_id=u1.id, url="https://example.com/demo-experiment-log",
                        label="實驗紀錄（示範連結）", link_type="experiment", created_by=alice.id))
    events.record(db, project_id=p1.id, actor_id=alice.id, event_type="update_published", entity_type="update",
                  entity_id=u1.id, goal=g_gemma, at=_ago(6), summary="進度更新：" + u1.completed)

    u2 = ProgressUpdate(project_id=p1.id, goal_id=g_vulkan.id, author_id=alice.id,
                        completed="嘗試建置 llama.cpp Vulkan backend",
                        findings="CPU backend 正常，Vulkan backend 在目前驅動版本下編譯失敗",
                        next_steps="修正 Vulkan build；必要時換驅動版本後重新 profiling",
                        publication_state="published", created_at=_ago(4), updated_at=_ago(4), published_at=_ago(4))
    db.add(u2)
    db.flush()
    b1 = Blocker(project_id=p1.id, goal_id=g_vulkan.id, reported_by=alice.id, title="Vulkan backend 編譯失敗",
                 description="shader 編譯階段出錯，疑似驅動版本不相容（示範）", opened_at=_ago(9))
    db.add(b1)
    db.flush()
    db.add(UpdateBlocker(update_id=u2.id, blocker_id=b1.id))
    events.record(db, project_id=p1.id, actor_id=alice.id, event_type="blocker_opened", entity_type="blocker",
                  entity_id=b1.id, goal=g_vulkan, at=_ago(9), summary=f"提出 blocker：{b1.title}")
    events.record(db, project_id=p1.id, actor_id=alice.id, event_type="update_published", entity_type="update",
                  entity_id=u2.id, goal=g_vulkan, at=_ago(4), summary="進度更新：" + u2.completed)

    # Upcoming meeting 2 (lab) - in 1 day, so the brief covers everything since meeting 1
    m2 = Meeting(project_id=p1.id, title="Lab Meeting #2", category="lab", occurred_at=utcnow() + timedelta(days=1),
                 agenda="是否延續 Vulkan 路線？", created_by=prof.id, created_at=_ago(1))
    db.add(m2)
    db.flush()
    for u in (prof, alice, bob):
        db.add(MeetingParticipant(meeting_id=m2.id, user_id=u.id))
    events.record(db, project_id=p1.id, actor_id=prof.id, event_type="meeting_created", entity_type="meeting",
                  entity_id=m2.id, meeting_category="lab", summary=f"建立 Lab Meeting「{m2.title}」", at=_ago(1))

    # Industry meeting kept on its own thread
    m3 = Meeting(project_id=p1.id, title="產學 Meeting：合作廠商進度同步", category="industry", occurred_at=_ago(7),
                 agenda="廠商希望看到記憶體比較初步結果", created_by=alice.id, created_at=_ago(7))
    db.add(m3)
    db.flush()
    for u in (prof, alice):
        db.add(MeetingParticipant(meeting_id=m3.id, user_id=u.id))
    events.record(db, project_id=p1.id, actor_id=alice.id, event_type="meeting_created", entity_type="meeting",
                  entity_id=m3.id, meeting_category="industry", summary=f"建立 產學 Meeting「{m3.title}」", at=_ago(7))
    o3 = MeetingOutcome(meeting_id=m3.id, goal_id=g_gemma.id, decision="下次產學會議提供 Gemma / Llama 比較表",
                        rationale="廠商只需要量化後的數據", feedback="", author_id=alice.id,
                        confirmation_state="pending", created_at=_ago(7))
    db.add(o3)
    db.flush()
    db.add(OutcomeComment(outcome_id=o3.id, author_id=alice.id, body="比較表草稿已放在實驗紀錄（示範）", created_at=_ago(5)))
    events.record(db, project_id=p1.id, actor_id=alice.id, event_type="outcome_recorded", entity_type="outcome",
                  entity_id=o3.id, goal=g_gemma, meeting_category="industry", at=_ago(7),
                  summary=f"【{m3.title}】決策：{o3.decision}（待指導者確認）")

    # ---------------- Project 2 ----------------
    p2 = Project(title="RAG Optimization", created_by=prof.id, created_at=_ago(25),
                 description=f"{DEMO_TAG}檢索增強生成的檢索品質與延遲取捨。")
    db.add(p2)
    db.flush()
    for u, role in ((prof, "advisor"), (carol, "student")):
        db.add(ProjectMember(project_id=p2.id, user_id=u.id, role=role, created_at=_ago(25)))
    events.record(db, project_id=p2.id, actor_id=prof.id, event_type="project_created", entity_type="project",
                  entity_id=p2.id, summary=f"建立專案「{p2.title}」", at=_ago(25))
    g_rag = Goal(project_id=p2.id, title="Reranker 對延遲的影響", research_question="加入 reranker 後延遲增加多少？",
                 assignee_id=carol.id, research_state="investigating", created_by=prof.id,
                 created_at=_ago(25), updated_at=_ago(25))
    db.add(g_rag)
    db.flush()
    events.record(db, project_id=p2.id, actor_id=prof.id, event_type="goal_created", entity_type="goal",
                  entity_id=g_rag.id, goal=g_rag, at=_ago(25), summary=f"新增研究目標「{g_rag.title}」，負責人：{carol.name}")
    u3 = ProgressUpdate(project_id=p2.id, goal_id=g_rag.id, author_id=carol.id, completed="建立 baseline 檢索流程",
                        findings="baseline recall@10 = 0.62（示範數據）", next_steps="加入 reranker 比較",
                        no_blocker=True, publication_state="published", created_at=_ago(20), updated_at=_ago(20),
                        published_at=_ago(20))
    db.add(u3)
    db.flush()
    events.record(db, project_id=p2.id, actor_id=carol.id, event_type="update_published", entity_type="update",
                  entity_id=u3.id, goal=g_rag, at=_ago(20), summary="進度更新：" + u3.completed)

    db.commit()
    print("Demo data loaded. Accounts: advisor/alice/bob/carol@demo.labpulse, password: demo1234")


def run(reset: bool = False) -> None:
    if reset:
        from sqlalchemy import text

        Base.metadata.drop_all(engine)
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    _migrate()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


def _migrate() -> None:
    import os

    from alembic import command
    from alembic.config import Config

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(root, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(root, "migrations"))
    command.upgrade(cfg, "head")
