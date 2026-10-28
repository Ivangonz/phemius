import path from "path"
import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { tanstackRouter } from "@tanstack/router-plugin/vite"

const API_SERVER = "http://127.0.0.1:8000"

export default defineConfig({
  plugins: [
    tanstackRouter({
      target: "react",
      autoCodeSplitting: true,
      routeFileIgnorePattern: "^__tests__$",
    }),
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // Keep the browser's Host (the string shorthand would rewrite it): the
      // API refuses changes whose Origin does not match Host.
      "/api": { target: API_SERVER, changeOrigin: false },
    },
  },
  build: {
    // FastAPI serves this folder and the Python package ships it, so the
    // runtime never needs Node.
    outDir: path.resolve(import.meta.dirname, "../src/phemius/static"),
    emptyOutDir: true,
  },
  test: {
    environment: "happy-dom",
    pool: "threads",
    // Node 25's built-in localStorage shadows happy-dom's and is unusable
    // without `--localstorage-file`; turning it off restores happy-dom's.
    execArgv: ["--no-experimental-webstorage"],
    setupFiles: ["./src/test/setup.ts"],
  },
})
