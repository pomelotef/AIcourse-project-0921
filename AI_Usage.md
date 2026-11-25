# AI Usage Guidelines

> Week 3 first draft，Week 12 依 review 證據修訂（見文末修訂紀錄）。

# Section 1 — What AI tools we plan to use, and what we will use each for

1. 可以使用任何 AI 工具（例如 Claude Code、claude.ai、Gemini、Copilot）。但含有 AI 撰寫程式碼的 PR，必須有「AI assistance」段落，寫出使用的工具和模型，並列出 AI 寫了哪些檔案或函式。沒有這段的 PR 不得 merge。 **（Week 12 修訂）**
2. AI 可以協助起草 PR 描述或 DECISION.md，但內容要由作者自己檢查並修改，而且要在「AI assistance」段落註明。
3. AI 可以用來發想、比較架構方案，但最後決定由團隊討論，並記錄在 DECISION.md。

# Section 2 — How we will document AI interactions

4. prompt log 放在 repo 的 `docs/prompt-log.md`。含有 AI 撰寫程式碼的 PR，要在**同一個 PR** 裡新增對應紀錄（prompt 內容、使用的模型、保留和修改了什麼），並在「AI assistance」段落附上連結。一次性的 debug 問題和語法查詢不用記錄。 **（Week 12 修訂）**

# Section 3 — How we will handle disagreements about AI output quality

5. 兩人對 AI 程式碼是否可以 merge 意見不同時，先討論，必要時投票。
6. merge 前必須：通過現有測試、通過 PR template 的 checklist，並且有一位**非作者**的 approve。review 裡要用自己的話說明至少一段 AI 寫的程式，或指出發現的問題。只按 Approve、沒寫內容的不算。 **（Week 12 修訂）**
7. 如果爭議是風格或偏好，而不是正確性，以團隊的 style guide 和 linter 設定為準，不逐案爭論。

# 修訂紀錄

| 日期 | 規則 | 修改原因 |
|---|---|---|
| 2026-11-24 | 1 | 最近兩週 3 個主要由 AI 產生的 PR，用的工具都不在舊規則裡（#13、#19 用 Claude Code，#18 用 claude.ai），而且 #13 沒說 AI 寫了哪些部分 |
| 2026-11-24 | 4 | #18 寫 prompt 已記錄在 log，但 repo 裡沒有這個檔案 |
| 2026-11-24 | 6 | #19 的 review 抓到 3 個測試沒抓到的 bug；#18 是空白 approve，無法判斷有沒有別人能解釋 |
| 2026-11-24 | 2、3 | 檔名改正：`DECISIONS.md` → `DECISION.md`（repo 實際檔名） |
