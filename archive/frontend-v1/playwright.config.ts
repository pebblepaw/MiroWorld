import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'bash ../quick_start.sh --mode demo',
    url: 'http://127.0.0.1:5173',
    timeout: 120000,
    reuseExistingServer: true,
  },
});
