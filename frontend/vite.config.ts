import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    clearMocks: true,
    restoreMocks: true,
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.test.{ts,tsx}",
        "src/test/**",
        "src/main.tsx",
        "src/vite-env.d.ts",
        "src/types.ts",
        "src/data.ts",
        "src/components/icons.tsx",
      ],
      reporter: ["text", "json-summary"],
      thresholds: {
        statements: 85,
        branches: 75,
        functions: 80,
        lines: 90,
      },
    },
  },
  server: {
    port: 5173,
    host: "127.0.0.1",
    // Proxy API calls through Vite in dev — avoids CORS and localhost vs 127.0.0.1 mismatches.
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
