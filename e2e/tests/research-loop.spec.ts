import { expect, test, type Browser, type Page } from '@playwright/test'

/**
 * The CP1 two-person loop, through the real UI with two independent browser sessions:
 * advisor creates project + goal -> student publishes progress with a blocker ->
 * advisor opens the meeting brief, records a decision and a next action ->
 * student reloads and sees the feedback and action -> timeline keeps the history.
 */

const run = Date.now()
const advisor = { name: '教授E2E', email: `advisor-${run}@e2e.example`, password: 'password123' }
const student = { name: '學生E2E', email: `student-${run}@e2e.example`, password: 'password123' }

async function register(browser: Browser, who: typeof advisor): Promise<Page> {
  const ctx = await browser.newContext()
  const page = await ctx.newPage()
  await page.goto('/')
  await page.getByRole('button', { name: '還沒有帳號？註冊' }).click()
  await page.getByLabel('名字').fill(who.name)
  await page.getByLabel('Email').fill(who.email)
  await page.getByLabel('密碼').fill(who.password)
  await page.getByRole('button', { name: '建立帳號' }).click()
  await expect(page.getByRole('heading', { name: '我的研究' })).toBeVisible()
  return page
}

test('advisor and student complete one research meeting loop', async ({ browser }) => {
  const prof = await register(browser, advisor)
  const alice = await register(browser, student)

  // Student has nothing yet: empty state, not an error
  await expect(alice.getByText('你還沒有加入任何研究專案')).toBeVisible()

  // --- advisor: project, member, goal ---
  await prof.getByRole('link', { name: '專案', exact: true }).click()
  await prof.getByRole('button', { name: '建立專案' }).click()
  await prof.getByLabel('專案名稱').fill('E2E 地端 LLM 記憶體')
  await prof.getByRole('button', { name: '建立', exact: true }).click()
  await expect(prof.getByRole('heading', { name: 'E2E 地端 LLM 記憶體' })).toBeVisible()
  const projectUrl = prof.url()

  await prof.getByRole('tab', { name: '成員' }).click()
  await prof.getByLabel('Email（對方需先註冊）').fill(student.email)
  await prof.getByRole('button', { name: '加入成員' }).click()
  await expect(prof.getByText(student.name)).toBeVisible()

  await prof.getByRole('tab', { name: '研究目標' }).click()
  await prof.getByRole('button', { name: '新增目標' }).click()
  const goalForm = prof.getByRole('form', { name: '新增研究目標' })
  await goalForm.getByLabel('目標名稱').fill('Vulkan profiling')
  await goalForm.getByLabel('研究問題').fill('加速器如何影響記憶體行為？')
  await goalForm.getByLabel('負責人').selectOption({ label: student.name })
  await goalForm.getByLabel('研究狀態').selectOption('investigating')
  await goalForm.getByRole('button', { name: '建立目標' }).click()
  await expect(prof.getByRole('link', { name: 'Vulkan profiling' })).toBeVisible()

  // --- student: sees the goal after reload, publishes progress with a blocker ---
  await alice.reload()
  await alice.getByRole('link', { name: '+ 新增進度' }).click()
  const form = alice.getByRole('form', { name: '進度更新' })
  await form.getByLabel('這段時間完成了什麼').fill('完成 Gemma / Llama 記憶體比較')
  await form.getByLabel('新發現 / 失敗嘗試').fill('Gemma 峰值記憶體較低')
  await form.getByRole('button', { name: '+ 新增 blocker' }).click()
  await form.getByLabel('新 blocker').fill('Vulkan backend 編譯失敗')
  await form.getByLabel('下一步').fill('修正 Vulkan build')
  await form.getByRole('button', { name: '發布更新' }).click()
  const summary = alice.getByRole('region', { name: '目前狀態摘要' })
  await expect(summary.getByText('完成 Gemma / Llama 記憶體比較')).toBeVisible()
  await expect(summary.getByText(/Vulkan backend 編譯失敗/)).toBeVisible()

  // --- advisor: meeting brief shows the student's update and blocker ---
  await prof.goto(projectUrl)
  await prof.getByRole('tab', { name: 'Meetings' }).click()
  await prof.getByRole('button', { name: '新增 Meeting' }).click()
  const mform = prof.getByRole('form', { name: '新增 Meeting' })
  await mform.getByLabel('標題').fill('Lab Meeting E2E')
  await mform.getByRole('button', { name: '建立並開啟 Brief' }).click()
  await expect(prof.getByRole('heading', { name: 'Lab Meeting E2E' })).toBeVisible()
  await expect(prof.getByText('這是此專案第一次 Lab Meeting')).toBeVisible()
  await expect(prof.getByText('完成 Gemma / Llama 記憶體比較')).toBeVisible()
  await expect(prof.getByText(/#\d+ Vulkan backend 編譯失敗/).first()).toBeVisible()

  // decision + feedback, then a prioritized next action
  const oform = prof.getByRole('form', { name: '記錄 meeting 結論' })
  await oform.getByLabel('相關研究目標').selectOption({ label: 'Vulkan profiling' })
  await oform.getByLabel('決策').fill('先驗證量測方法，再給 Vulkan 一週')
  await oform.getByLabel('理由').fill('數據可信度優先')
  await oform.getByRole('button', { name: '儲存結論' }).click()
  await expect(prof.getByTestId('outcome-card').getByText('已確認')).toBeVisible()

  await prof.getByRole('button', { name: '新增待辦' }).click()
  const aform = prof.getByRole('form', { name: '新增待辦' })
  await aform.getByLabel('待辦事項').fill('驗證量測方法')
  await aform.getByLabel('負責人').selectOption({ label: student.name })
  await aform.getByLabel('優先度').selectOption('high')
  await aform.getByRole('button', { name: '新增待辦' }).click()
  await expect(prof.getByTestId('action-row').getByText('驗證量測方法')).toBeVisible()

  // --- student: reload, sees feedback and the new action ---
  await alice.goto('/')
  await expect(alice.getByTestId('action-row').getByText('驗證量測方法')).toBeVisible()
  await expect(alice.getByText('先驗證量測方法，再給 Vulkan 一週').first()).toBeVisible()
  await alice.getByTestId('action-row').getByRole('button', { name: '完成' }).click()
  await expect(alice.getByText('沒有未完成的待辦')).toBeVisible()

  // --- timeline keeps the round ---
  await alice.goto(projectUrl + '?tab=timeline')
  const items = alice.getByTestId('timeline-item')
  await expect(items.filter({ hasText: '決策：先驗證量測方法' })).toHaveCount(1)
  await expect(items.filter({ hasText: '提出 blocker：Vulkan backend 編譯失敗' })).toHaveCount(1)
  await expect(items.filter({ hasText: '待辦「驗證量測方法」狀態：待處理 → 已完成' })).toHaveCount(1)

  // --- the advisor overview shows the project ---
  await prof.goto('/overview')
  await expect(prof.getByRole('link', { name: 'E2E 地端 LLM 記憶體' })).toBeVisible()
})

test('outsider cannot open someone else\'s project', async ({ browser }) => {
  const eve = await register(browser, { name: 'Eve', email: `eve-${run}@e2e.example`, password: 'password123' })
  await eve.goto('/projects/1')
  await expect(eve.getByRole('alert')).toContainText('找不到資料，或你沒有存取權限')
})
