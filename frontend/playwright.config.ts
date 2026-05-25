import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const root = path.resolve(__dirname, "..");
const posixRoot = root.replace(/\\/g, "/");
const apiPort = 45631;
const webPort = 45632;
const runId = Date.now();
const databaseUrl = `sqlite:///${posixRoot}/.e2e-data/dossier-${runId}.db`;

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  expect: { timeout: 8_000 },
  use: {
    baseURL: `http://127.0.0.1:${webPort}`,
    trace: "retain-on-failure"
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ],
  webServer: [
    {
      command: `cd "${root}" && mkdir -p .e2e-data/uploads .e2e-data/exports && DATABASE_URL=${databaseUrl} .venv/bin/alembic -c backend/alembic.ini upgrade head && DATABASE_URL=${databaseUrl} UPLOAD_DIR="${posixRoot}/.e2e-data/uploads" EXPORT_DIR="${posixRoot}/.e2e-data/exports" .venv/bin/uvicorn app.main:create_app --factory --host 127.0.0.1 --port ${apiPort}`,
      url: `http://127.0.0.1:${apiPort}/health`,
      reuseExistingServer: false,
      timeout: 20_000
    },
    {
      command: `NEXT_PUBLIC_API_URL=http://127.0.0.1:${apiPort} npm run dev -- --hostname 127.0.0.1 --port ${webPort}`,
      url: `http://127.0.0.1:${webPort}/people`,
      reuseExistingServer: false,
      timeout: 20_000
    }
  ]
});
