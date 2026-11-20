# AIcourse-project-team02 — LabPulse（暫定名稱）

研究進度管理工具：讓教授與學生把**研究目標、進度、發現、阻礙（blocker）、meeting 決策與下一步**放在同一個共享紀錄裡，減少每次開會前重新整理脈絡的時間。產品方向與評估方式以 CP1 文件為準。

> 核心功能**不使用 AI**、不需要任何付費 API 或 GitHub token。所有狀態與提醒都來自使用者輸入或明確規則。

## 目前完成的功能（MVP）

| 功能 | 說明 |
|---|---|
| 帳號與專案 | Email + 密碼註冊登入；建立研究專案；指導者以 email 加入成員；角色（指導者／學生）是「每個專案」的屬性 |
| 研究目標 | 目標樹（子目標）、負責人、研究狀態（規劃中／研究中／部分回答／已回答／需重新檢視／已封存）；共享或私人 |
| 進度更新 | 完成事項、新發現／失敗嘗試、blocker、下一步、外部連結（實驗紀錄、GitHub、文件…）；草稿／發布 |
| Blocker | 有固定編號，可在多次更新中延續引用；標記解決並記錄解法 |
| 待辦（Action） | **優先度（高／中／低）**、可選期限、狀態；取消或改期必須填原因，保留在時間軸；更新中的「下一步」可手動「轉成待辦」 |
| Meeting | **分類：Lab Meeting／產學 Meeting／個別 Meeting／其他**；參與者、待討論問題 |
| Meeting Brief | 與「上次同分類 meeting」比較：上次的決策與承諾（含已完成）、更早仍未完成的待辦、期間的進度更新、未解決與期間已解決的 blocker；可只看某位學生 |
| Meeting 結論 | 決策、理由、回饋；指導者記錄的直接是「已確認」，學生記錄的標示「待指導者確認」；可留言補充 |
| 目標頁摘要 | 頁面最上方四格：**最新進度、主要阻礙、下一步、最近一次 meeting 決定**（對應 CP1 評估任務） |
| 研究時間軸 | 依專案、目標（含子目標）、事件類型、meeting 分類篩選；舊決策不會被新 meeting 覆蓋 |
| 指導者多專案總覽 | 依專案或依成員檢視：最近更新、未解決 blocker、過期待辦、待確認結論、各分類最近 meeting；「需要關注」清單明示規則，可調整更新週期 |
| 私人內容 | 私人目標、私人筆記、未發布草稿只有作者看得到，所有權限都在後端檢查 |

尚未實作（之後的擴充）：實驗版本比較、GitHub 整合、通知、匯出、全域搜尋、即時同步（目前是重新整理後看到他人修改）。

## 技術架構

- `backend/`：FastAPI + SQLAlchemy 2 + Alembic，SQLite（設定 `LABPULSE_DATABASE_URL` 可改用 PostgreSQL）；Python 套件用 [uv](https://docs.astral.sh/uv/) 管理
- `frontend/`：React 18 + TypeScript + Vite，繁體中文介面，手機與電腦都能使用
- `e2e/`：Playwright，用兩個獨立瀏覽器 session 跑完整的指導者／學生流程
- `.github/workflows/ci.yml`：PR 時自動跑後端測試、migration、demo seed、前端 build 與 E2E

## 本機啟動

需要：Python 3.11+、[uv](https://docs.astral.sh/uv/getting-started/installation/)、Node.js 20+。

**1. 後端（第一個終端機）**

```powershell
cd backend
uv sync
uv run python manage.py seed --reset
uv run python manage.py serve
```

`seed --reset` 會**清空本機資料庫**並建立 migration 與示範資料。只想套用 migration、不清資料時用 `uv run python manage.py migrate`。

**2. 前端（第二個終端機）**

```powershell
cd frontend
npm install
npm run dev
```

打開 <http://localhost:5173>。

### 示範帳號（虛構資料）

示範資料全部是虛構的，不是訪談結果或真實研究，專案說明裡標有「【示範資料】」。所有帳號的密碼都是 `demo1234`，只能用在本機示範。

| 帳號 | 角色 |
|---|---|
| `advisor@demo.labpulse` | 王老師（示範），兩個專案的指導者 |
| `alice@demo.labpulse` | Alice（示範），On-device LLM Memory 的學生 |
| `bob@demo.labpulse` | Bob（示範），On-device LLM Memory 的學生 |
| `carol@demo.labpulse` | Carol（示範），RAG Optimization 的學生 |

建議的示範路線：用 Alice 登入看「我的研究」→ 進入「Vulkan backend profiling」看目標頁摘要 → 用另一個瀏覽器（或無痕視窗）以老師登入 → 專案 → Meetings →「Lab Meeting #2」看 Brief、記錄結論並新增待辦 → 回到 Alice 重新整理。

## 測試

```powershell
cd backend
uv run python -m pytest -q
```

```powershell
cd frontend
npm run build
```

```powershell
cd e2e
npm install
npx playwright install chromium
npx playwright test
```

E2E 會自己啟動後端（port 8011）與前端（port 5181），使用 `e2e/.e2e-data/` 裡的獨立資料庫，不會動到你的開發資料。

如果不想下載 Playwright 的 Chromium，可以改用電腦上已安裝的瀏覽器（Windows 內建 Edge）：

```powershell
$env:PW_CHANNEL = "msedge"; npx playwright test
```

## Windows 注意事項

有些電腦開了 Windows「智慧型應用程式控制」（Smart App Control），會擋下剛下載、沒有簽章的執行檔與 DLL：

- 一律用 `uv run python manage.py …`、`uv run python -m pytest`，**不要**直接執行 `.venv` 裡的 `pytest.exe`、`alembic.exe`、`uvicorn.exe`
- SQLAlchemy 的 C 擴充可能被擋，所以 `app/__init__.py` 預設改用 SQLAlchemy 的純 Python 實作（`DISABLE_SQLALCHEMY_CEXT_RUNTIME=1`）。這在 MVP 的資料量下沒有可感知的效能差異

## 環境變數

見 [`.env.example`](.env.example)。部署到 HTTPS 時請設定 `LABPULSE_COOKIE_SECURE=true`。不要把真實帳密或研究資料放進 repository。

## 團隊文件

- [DECISION.md](DECISION.md)：重要決策紀錄
- [AI_Usage.md](AI_Usage.md)：AI 工具使用規範
- [CONTRIBUTORS.md](CONTRIBUTORS.md)
