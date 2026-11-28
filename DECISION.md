# Decisions Log

## 2026-09-21 — Initial code steward
**What:** SamTsai0316 is the initial code steward for the team.
**Why:** Volunteered

## 2026-11-20 — MVP 技術選型：FastAPI + React/TypeScript + SQLite
**What:** 後端 FastAPI + SQLAlchemy + Alembic（uv 管理），前端 React + TypeScript + Vite，資料庫先用 SQLite，E2E 用 Playwright，CI 用 GitHub Actions。
**Why:** repo 原本沒有程式碼；這組合 API 清楚、好測試，四人都能在本機一鍵啟動。SQLite 免安裝，之後要多人部署時改 `LABPULSE_DATABASE_URL` 即可換 PostgreSQL。
**Alternative rejected:** 一開始就上 PostgreSQL + Docker（增加每位組員的啟動成本）。

## 2026-11-20 — 不做 Workspace 層，用「專案成員 + 角色」控管權限
**What:** 權限只看 ProjectMember；角色（advisor / student）是每個專案的屬性，同一人可以在 A 專案當指導者、B 專案當學生。
**Why:** CP1 的結構是「計畫 → 研究目標 → 進度／阻礙／下一步／meeting 決定」，MVP 不需要再多一層 workspace；少一層就少一組權限規則要測。
**Alternative rejected:** 交接文件建議的 Workspace → Project 兩層。

## 2026-11-20 — 可見範圍只有「專案共享」和「作者私人」兩種
**What:** 目標可設為私人；私人目標不能有子目標、進度、blocker、待辦或 meeting 結論，也不能指派給別人。已有共享紀錄的目標不能改回私人；改為私人時，它過去的時間軸事件也一併改為私人。私人筆記獨立成一張表、不產生時間軸事件。未發布的進度草稿只有作者看得到。
**Why:** 交接文件要求教授的私人規劃不能透過關聯、列表、統計或 API 洩漏。直接禁止私人目標被關聯，比在每個查詢都過濾更不容易出錯。所有檢查都在後端，看不到的資料一律回 404，避免用 ID 探測。
**Alternative rejected:** 「指定參與者可見」第三種範圍（等有實際需求再加）。

## 2026-11-20 — Meeting 結論：教授與學生都能記錄，學生記錄需教授確認
**What:** 指導者記錄的結論直接是「已確認」；學生記錄的標示「待指導者確認」，教授確認前作者可以修改。已確認的結論不能直接改，補充或修正用留言。
**Why:** CP1 寫的是「由教授記錄結論」，但受訪者也提到教授不一定會使用系統；標示確認狀態可以避免把單方筆記當成雙方共識，同時保留決策歷史。

## 2026-11-20 — Meeting 分類與 Brief 的比較範圍
**What:** Meeting 有固定分類：Lab Meeting、產學 Meeting、個別 Meeting、其他。Brief 只跟「同專案、同分類」的上一次 meeting 比較，範圍是（上次 meeting 時間, 本次 meeting 時間]。
**Why:** 受訪者 Student1 每週有兩次 Lab Meeting 和一次產學 Meeting，希望兩種紀錄不要混在一起，也要能分辨教授與產學合作方的建議。固定分類比自訂分類簡單，之後有需要再開放自訂。

## 2026-11-20 — 待辦加入優先度，取消或改期必須填原因
**What:** 待辦有優先度（高／中／低）與可選期限，列表依「未完成 → 優先度 → 期限」排序。取消、移動既有期限都必須填原因並寫入時間軸。進度更新裡的「下一步」不會自動變成待辦，要使用者按「轉成待辦」。
**Why:** Student1 希望「將 Meeting 中交代的工作轉成待辦事項，標記優先順序、期限及完成狀態」。保留取消與改期原因，避免把「沒做」和「做完」混在一起。

## 2026-11-20 — 教授多專案總覽納入 MVP，規則明示且不排名
**What:** 總覽只列使用者擔任指導者的專案，可依專案或依成員檢視。「需要關注」的規則都寫在畫面上：超過更新週期（預設 14 天，可選 7／14／21／30）沒有新進度、blocker 開啟超過 7 天、待辦超過期限、學生記錄的結論待確認。
**Why:** CP1 承諾「教授能快速了解各計畫近況」。顯示的是「資訊可能過期」，不是「學生沒進度」，也不做學生排名，避免變成監控工具。

## 2026-11-20 — 實驗版本比較延後
**What:** MVP 不做實驗版本比較；進度更新與目標可以附「實驗紀錄」類型的外部連結。
**Why:** 先驗證集中記錄研究脈絡是否有效（CP1 評估重點），版本比較的資料結構等有使用者回饋再設計。

## 2026-11-20 — Windows 上改用 SQLAlchemy 純 Python 實作
**What:** `app/__init__.py` 預設設定 `DISABLE_SQLALCHEMY_CEXT_RUNTIME=1`；所有指令透過 `uv run python manage.py …` 與 `uv run python -m pytest` 執行。
**Why:** 組員電腦上的 Windows 智慧型應用程式控制會擋下 SQLAlchemy 未簽章的 C 擴充與 `.venv` 裡的 exe。MVP 的資料量下效能差異可以忽略。

## 2026-11-20 — code steward
**What:** SamTsai0316 is the code steward for this PR#13.
**Why:** Volunteered

## 2026-11-22 — 加入選用的 AI 會前摘要
**What:** Meeting 頁面新增「AI 會前摘要」：把該場 Meeting Brief 的紀錄交給模型，產生 1–3 句摘要與最多 6 個討論重點（阻礙、需要決定、待追蹤、進度），每一點都標出依據的紀錄。AI 只負責整理與引用，所有決策仍由教授在 meeting 中做；`Draft_Evaluation_Plan.md` 的 Human-AI boundary 同步改為「AI 只做摘要與引用，決策由人做」。
**Why:** 對應評估計畫的成功定義「會前準備時間減少 10%」，也補上 CP2 的 AI 元件。

## 2026-11-22 — AI 只讀 Brief 已公開的紀錄，只送角色不送姓名
**What:** `POST /api/meetings/{id}/brief/ai-summary` 直接呼叫 `meeting_brief()` 取得紀錄（已發布的進度、共享目標的 blocker、待辦、上次的決策），轉成 P／B／A／D 編號後才送出；草稿、私人筆記、私人目標一律不送；作者只送角色（student／advisor），不送姓名與 email；只送最近 40 筆，每筆截到 400 字。
**Why:** 摘要會顯示給整個專案，必須和 Brief 用同一套權限。不採用「另外查資料庫」，因為要再寫一套過濾，容易漏掉草稿與私人資料。姓名對摘要沒有幫助，卻會把個資送到外部 API；筆數與字數上限用來控制成本。

## 2026-11-22 — AI 功能預設關閉，金鑰只放環境變數
**What:** 後端有 `ANTHROPIC_API_KEY` 才啟用，否則 endpoint 回 `disabled`；模型預設 `claude-haiku-5-5`，可用 `LABPULSE_AI_MODEL` 更換；`anthropic` 透過 `uv add` 加入，同時更新 `uv.lock`。
**Why:** CI 與沒有金鑰的組員都要能正常執行；CI 使用 `uv sync --locked`，lock 檔沒一起更新就會失敗；金鑰只放在 shell，不進 repo。

## 2026-11-22 — 程式檢查 AI 回覆，失敗就退回原本的 Brief
**What:** 模型必須回固定格式的 JSON；`validate()` 檢查欄位、允許值、長度，以及「每個引用的紀錄 ID 都存在於輸入中」。不合格就附上問題清單重試一次，仍失敗回 `unavailable`，頁面只顯示原本的 Brief；Brief 沒有任何紀錄時不呼叫模型。
**Why:** 格式錯誤通常重試一次就能修好；引用不存在的紀錄代表模型編造出處，必須擋下。不採用無限重試或第二個模型審查，因為成本高，也不保證更正確；AI 失敗時 meeting 頁面不能跟著壞掉。

## 2026-11-22 — 摘要按下按鈕才產生，不存進資料庫
**What:** 摘要卡片只在按下「產生 AI 摘要」時呼叫模型，結果標示為 AI 產生並列出依據的紀錄；切換「只看某位成員」時清空重來；摘要不寫入資料庫。
**Why:** 每次產生都是付費的模型呼叫，而大多數人打開頁面只是要看 Brief。列出依據讓使用者能回頭對照原始紀錄。不存資料庫，可以避免紀錄更新後看到過期的摘要，MVP 先保持簡單。

## 2026-11-22 — AI 摘要的兩層測試
**What:** 第 1 層：`test_brief_summary.py` 與 `test_ai_summary_api.py` 用假模型，隨 CI 執行，不需要金鑰。第 2 層：`promptfoo/brief_summary/` 用真模型手動執行，至少 10 個案例、`--repeat 3`、一次修正循環；每個案例的預期行為由全組在第一次執行前寫好。
**Why:** 權限、驗證、退回這些程式行為必須每次都一樣，所以用假模型測。模型的回覆有隨機性，要重複執行才算證據。這也對應 CP2 的 prompt 測試套件要求。

## 2026-11-22 — code steward
**What:** AlanCheng1000 is the code steward for this PR (Commit 3bf4669).
**Why:** Volunteered

## 2026-11-28 — AI 摘要呼叫模型時關閉 thinking
**What:** `AnthropicClient.complete()` 送出時加上 `thinking={"type": "disabled"}`，`max_tokens` 維持 800。
**Why:** `claude-haiku-5-5` 預設會先 thinking，用 demo 資料實測時 800 tokens 全部用在 thinking，沒有任何文字回覆，所以每次摘要都是 `unavailable`。摘要只是把紀錄整理成固定格式的 JSON，不需要推理；關閉後實測輸出約 600 tokens，並通過 `validate()`。
**Alternative rejected:** 調高 `max_tokens`（thinking 長度沒有上限，仍可能用光，成本與等待時間也會增加）；調低 effort（模型仍會 thinking，不保證留下足夠的空間給回覆）。Haiku 5.5 只有在 effort 為 high 以下時才能關閉 thinking，目前使用預設的 medium。
