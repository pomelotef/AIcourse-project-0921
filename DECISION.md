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
**What:** SamTsai0316 is the code steward for this PR.
**Why:** Volunteered
