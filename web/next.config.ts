import type { NextConfig } from "next";

const githubPages = process.env.GITHUB_PAGES === "true";
const repositoryName = process.env.GITHUB_REPOSITORY?.split("/")[1];
const basePath = githubPages && repositoryName && !repositoryName.endsWith(".github.io")
  ? `/${repositoryName}`
  : "";

const config: NextConfig = {
  output: githubPages ? "export" : "standalone",
  ...(basePath ? { basePath } : {}),
  env: { NEXT_PUBLIC_BASE_PATH: basePath },
};
export default config;
