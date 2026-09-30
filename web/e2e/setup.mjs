import { spawn } from "node:child_process";
import { writeFile } from "node:fs/promises";
import { setTimeout as delay } from "node:timers/promises";

const pidFile = ".next/e2e-server.pid";
export default async function setup() {
const server = spawn(process.execPath, [".next/standalone/server.js"], {
  cwd: process.cwd(),
  detached: true,
  stdio: "ignore",
  env: {
    ...process.env,
    PORT: "3100",
    HOSTNAME: "0.0.0.0",
    NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000",
    NEXT_PUBLIC_APP_NAME: "IssueArea",
    NEXT_PUBLIC_MAP_PROVIDER: "leaflet_osm",
    NEXT_PUBLIC_APP_ENV: "development",
  },
});
server.unref();
await writeFile(pidFile, String(server.pid));

for (let attempt = 0; attempt < 120; attempt += 1) {
  if (server.exitCode !== null) throw new Error(`E2E server exited early with code ${server.exitCode}`);
  try {
    const response = await fetch("http://localhost:3100/");
    if (response.ok) return;
  } catch {
    // The server is still starting.
  }
  await delay(1_000);
}
try { process.kill(server.pid); } catch { /* already stopped */ }
throw new Error("E2E server did not become ready on port 3100 within 120 seconds");
}
