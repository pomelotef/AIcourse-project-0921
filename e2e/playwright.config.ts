import { defineConfig } from '@playwright/test'
import { mkdirSync, rmSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Separate ports and a throw-away database so E2E never touches your dev data.
const here = path.dirname(fileURLToPath(import.meta.url))
const dataDir = path.join(here, '.e2e-data')
// The config is evaluated again inside every worker process; only the main process
// (which starts the servers) may reset the database.
if (!process.env.TEST_WORKER_INDEX) {
  rmSync(dataDir, { recursive: true, force: true })
  mkdirSync(dataDir, { recursive: true })
}
const dbUrl = `sqlite:///${path.join(dataDir, 'e2e.db').replace(/\\/g, '/')}`
const API_PORT = 8011
const WEB_PORT = 5181
const backendDir = path.join(here, '..', 'backend')
const frontendDir = path.join(here, '..', 'frontend')

export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: 'retain-on-failure',
    // CI uses Playwright's Chromium. Locally you can reuse an installed browser instead of
    // downloading one, e.g. PW_CHANNEL=msedge (Windows) or PW_CHANNEL=chrome.
    channel: process.env.PW_CHANNEL || undefined,
  },
  webServer: [
    {
      command: `uv run python manage.py migrate && uv run python manage.py serve --port ${API_PORT}`,
      cwd: backendDir,
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      env: { LABPULSE_DATABASE_URL: dbUrl },
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1',
      cwd: frontendDir,
      url: `http://127.0.0.1:${WEB_PORT}`,
      env: { LABPULSE_API_URL: `http://127.0.0.1:${API_PORT}`, LABPULSE_WEB_PORT: String(WEB_PORT) },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
})
