import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const sourceDirectory = fileURLToPath(new URL("./src", import.meta.url));

export default defineConfig({
  resolve: {
    alias: { "@": sourceDirectory },
  },
  esbuild: {
    jsx: "automatic",
  },
  test: {
    environment: "node",
    include: ["src/components/**/*.test.ts"],
  },
});
