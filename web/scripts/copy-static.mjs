import { cpSync, mkdirSync } from "node:fs";
if (process.env.GITHUB_PAGES === "true") process.exit(0);
mkdirSync(".next/standalone/.next", { recursive: true });
cpSync(".next/static", ".next/standalone/.next/static", { recursive: true });
