/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Relative asset paths: the built shell is copied into each generated project's web/ folder.
export default defineConfig({
  base: "./",
  plugins: [react()],
  test: { environment: "jsdom", include: ["src/**/*.test.{ts,tsx}"] },
});
