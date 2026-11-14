import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

function listFiles(directory: string): string[] {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const entryPath = path.join(directory, entry.name);
    return entry.isDirectory() ? listFiles(entryPath) : [entryPath];
  });
}

function serviceWorkerPlugin(): Plugin {
  return {
    name: "pika-service-worker",
    apply: "build",
    generateBundle(_options, bundle) {
      const publicDir = path.resolve(__dirname, "public");
      const publicAssets = listFiles(publicDir)
        .filter((file) => path.basename(file) !== "sw.js")
        .map((file) => "/" + path.relative(publicDir, file).split(path.sep).join("/"));
      const bundledAssets = Object.values(bundle)
        .filter((output) => output.fileName !== "sw.js" && !output.fileName.endsWith(".map"))
        .map((output) => "/" + output.fileName);
      const precacheAssets = Array.from(
        new Set(["/index.html", ...bundledAssets, ...publicAssets]),
      );
      const workerPath = path.resolve(__dirname, "src/sw.js");
      const workerTemplate = fs.readFileSync(workerPath, "utf8");
      const cacheHash = createHash("sha256")
        .update(workerTemplate)
        .update(JSON.stringify(precacheAssets));
      for (const asset of publicAssets) {
        cacheHash.update(fs.readFileSync(path.join(publicDir, asset.slice(1))));
      }
      for (const output of Object.values(bundle)) {
        cacheHash.update(output.type === "asset" ? output.source : output.code);
      }
      const cacheVersion = cacheHash.digest("hex").slice(0, 12);
      const worker = workerTemplate
        .replace("__PRECACHE_ASSETS__", JSON.stringify(precacheAssets))
        .replace("__CACHE_NAME__", JSON.stringify("pika-precache-" + cacheVersion));

      this.emitFile({
        type: "asset",
        fileName: "sw.js",
        source: worker,
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), serviceWorkerPlugin()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:5000",
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
