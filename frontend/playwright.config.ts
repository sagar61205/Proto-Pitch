import { defineConfig } from "@playwright/test";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// The smoke test runs against the real server: API, worker and the built web interface,
// with a throw-away data directory, no API keys and no model.
const port = Number(process.env.PROTOPITCH_E2E_PORT ?? 8123);
const dataDir = process.env.PROTOPITCH_E2E_DATA ?? mkdtempSync(join(tmpdir(), "protopitch-e2e-"));
process.env.PROTOPITCH_E2E_DATA = dataDir;

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  retries: 0,
  reporter: [["list"]],
  use: { baseURL: `http://127.0.0.1:${port}`, trace: "off" },
  webServer: {
    command: `uv run --project ../backend protopitch serve --with-worker --port ${port}`,
    url: `http://127.0.0.1:${port}/api/health`,
    env: { PROTOPITCH_STORAGE__DATA_DIR: dataDir },
    reuseExistingServer: false,
    timeout: 90_000,
  },
});
