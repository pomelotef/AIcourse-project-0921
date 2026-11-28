# Prompt Engineering Log

每筆紀錄對應一個 PR。格式：

## PR #編號 — 標題
- 日期：
- 工具和模型：
- Prompt（重點即可）：
- 保留了什麼：
- 修改了什麼、為什麼：

---

## PR #26 — AI 會前摘要：前端卡片、prompt 測試套件、prompt card（apply-patch）
- 日期：2026-11-24（產生）、2026-11-28（依 review 修改）
- 工具和模型：claude.ai 對話（Claude）；11/28 的修改用 Claude Opus 5.5（Cowork）
- Prompt（重點即可）：
  1. 11/24：依 #18 的後端 API 與 DECISION.md 的 AI 條目，產生 Meeting 頁的摘要卡片（`AiSummary.tsx`）、`promptfoo/brief_summary/` 測試套件（9 個案例、`checks.js`、`build.py`）、prompt card 與 README 段落，輸出成 patch。
  2. 11/28：貼上 BrotherHong 在 #26 的三則 review，請它寫出每個案例的預期行為與 P1 預測、新增超過 40 筆紀錄的 L2、填 prompt card 的 Owner 與日期。
- 保留了什麼：11/24 的 patch 全部保留（套用後 `npm run build` 通過）；11/28 的 10 個預期行為、`cases/l2_over_40.json`，以及 `checks.js` 新增的 `citesTogether` 與 `cutIdNotCited`。
- 修改了什麼、為什麼：
  - 依 BrotherHong 的 review（2026-11-28）：9 個案例的 description 從佔位字改成具體的預期行為；新增 L2（45 筆，最舊的 5 筆被截掉，其中有一個仍未解決的 blocker），補足 DECISION.md 要求的 10 個案例；prompt card 填上 Owner 與日期。
  - P1 原本只檢查有沒有引用 D2，但預期行為是「D1、D2 一起引用」，所以改用 `citesTogether`，讓檢查和預期一致。
  - T3 原本在模型回 `insufficient_data`（沒有 points）時也會通過，加上 `statusIs`，確認 status 是 ok。
  - prompt card 的 Known limits 加上 L2 揭露的限制：只送最新 40 筆，比它們都舊、但仍未解決的 blocker 不會出現在摘要裡。
  - `promptfooconfig.yaml` 加上 `thinking: {type: disabled}`，和 #29 修正後的 `llm.py` 用同樣的方式呼叫模型。Haiku 5.5 預設會 thinking，可能把 800 tokens 全部用掉，測試結果就不能代表 app 的行為。
