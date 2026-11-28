# Prompt Engineering Log

每筆紀錄對應一個 PR。格式：

## PR #編號 — 標題
- 日期：
- 工具和模型：
- Prompt（重點即可）：
- 保留了什麼：
- 修改了什麼、為什麼：

---

## PR #27 — 通知鈴鐺（feat/notifications）
- 日期：2026-11-26
- 工具和模型：Claude Code（Claude Opus 5.5）
- Prompt（重點即可）：
  1. 「開始做通知功能」：沿用時間軸事件（`events.record`）決定誰收到通知，透過既有的 SSE 即時更新鈴鐺；規則照先前討論的表（發布進度 → 老師、待辦 → 負責人、留言 → 結論作者與留言者等），不通知自己、不通知私人目標、只通知目前成員。
  2. 「用 B 合併通知」：同一個人、同一件事只保留一則通知，有新動作就移到最上面並重新標為未讀（參考 GitHub）。
- 保留了什麼：`notify.py` 的規則表與合併邏輯、通知 API、鈴鐺元件、後端測試（初版 15 個，依 review 補到 16 個）。
- 修改了什麼、為什麼：
  - 依 pomelotef 的 review（2026-11-27）修正測試：`test_added_member_is_told` 原本只檢查 fixture 裡的 alice，沒驗證新加入的 dan；改成驗證 dan 收到 `member_added`，且 alice、bob、老師都不會因此收到通知。
  - 補上 `test_blocker_reaches_advisors_and_goal_assignee`：`blocker_opened` 原本沒有測試；確認老師和目標負責人收到、提出的人和非成員不會收到，且連結指向 `/goals/{goal_id}`（不是 blocker 的 id）。
  - 初版紀錄寫「16 個測試」，實際是 15 個，已更正。
  - 第二輪測試修正同樣用 Claude Code（Claude Opus 5.5），prompt：「review 有 suggestion，照 review 修」。
