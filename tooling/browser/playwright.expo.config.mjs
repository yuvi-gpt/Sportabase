import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/expo', fullyParallel: false, workers: 1, retries: 0,
  reporter: 'list', outputDir: './test-results/expo',
  projects: [{ name: 'expo-product', use: { baseURL: 'http://127.0.0.1:4174', browserName: 'chromium', colorScheme: 'dark', viewport: { width: 1440, height: 1000 }, trace: 'retain-on-failure', screenshot: 'only-on-failure' } }],
});
