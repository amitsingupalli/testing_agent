import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 15000,
  use: {
    baseURL: "http://127.0.0.1:8901",
  },
  projects: [
    { name: "chromium", use: { browserName: "chromium" } },
  ],
});
