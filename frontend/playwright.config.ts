import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import os from "node:os";

// バックエンドはvenvのuvicornで起動する。E2E専用の一時DBを使い、開発DBを汚さない。
const venvUvicorn =
  process.env.PBM_UVICORN ??
  path.join(os.homedir(), ".venvs", "pbm", "Scripts", "uvicorn.exe");
const e2eDb = path.join(os.tmpdir(), `pbm_e2e_${Date.now()}.sqlite3`);

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `"${venvUvicorn}" pbm.api.main:app --port 8000`,
      url: "http://localhost:8000/api/health",
      reuseExistingServer: false,
      timeout: 60_000,
      cwd: "../backend",
      env: { PBM_DATABASE_URL: `sqlite:///${e2eDb.replace(/\\/g, "/")}` },
    },
    {
      command: "npm run start",
      url: "http://localhost:3000",
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
