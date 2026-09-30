import { readFile, rm } from "node:fs/promises";

const pidFile = ".next/e2e-server.pid";
export default async function teardown() {
try {
  const pid = Number(await readFile(pidFile, "utf8"));
  if (Number.isInteger(pid) && pid > 0) process.kill(pid);
} catch {
  // Setup may fail before the server starts.
} finally {
  await rm(pidFile, { force: true });
}
}
