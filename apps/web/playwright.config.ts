import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  use: { baseURL: 'http://127.0.0.1:5174', trace: 'retain-on-failure' },
  webServer: [
    { command: 'cd ../api && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001', url: 'http://127.0.0.1:8001/api/v1/health', reuseExistingServer: true, timeout: 120_000 },
    { command: 'npm run dev -- --host 127.0.0.1 --port 5174', url: 'http://127.0.0.1:5174', reuseExistingServer: true, timeout: 120_000 },
  ],
})
