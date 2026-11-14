import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const distDir = path.join(frontendDir, "dist");
const read = (file) => fs.readFileSync(path.join(distDir, file), "utf8");

const manifest = JSON.parse(read("manifest.webmanifest"));
assert.equal(manifest.id, "/", "PWA id must remain stable");
assert.equal(manifest.start_url, "/");
assert.equal(manifest.scope, "/");
assert.ok(manifest.name && manifest.short_name);
for (const icon of manifest.icons) {
  assert.ok(fs.existsSync(path.join(distDir, icon.src.slice(1))), `Missing icon ${icon.src}`);
}
for (const screenshot of manifest.screenshots) {
  assert.ok(fs.existsSync(path.join(distDir, screenshot.src.slice(1))), `Missing screenshot ${screenshot.src}`);
}
assert.ok(manifest.icons.some((icon) => icon.sizes === "192x192"));
assert.ok(manifest.icons.some((icon) => icon.sizes === "512x512"));
assert.ok(manifest.icons.some((icon) => icon.purpose === "maskable"));
assert.ok(manifest.screenshots.some((shot) => shot.form_factor === "wide"));
assert.ok(manifest.screenshots.some((shot) => shot.form_factor !== "wide"));
assert.ok(fs.existsSync(path.join(distDir, "offline.html")));

const html = read("index.html");
assert.match(html, /rel="manifest"/);
assert.match(html, /apple-touch-icon/);
assert.ok(fs.existsSync(path.join(distDir, "icons", "apple-touch-icon.png")));
assert.ok(html.includes(`content="${manifest.theme_color}"`), "Theme color metadata must match the manifest");

const sw = read("sw.js");
assert.ok(!sw.includes("__CACHE_NAME__") && !sw.includes("__PRECACHE_ASSETS__"));
assert.ok(sw.includes("/index.html") && sw.includes("/offline.html"));
assert.match(sw, /pathname\.startsWith\("\/api\/"\)/);
assert.match(sw, /addEventListener\("sync"/);

const deployment = JSON.parse(fs.readFileSync(path.join(frontendDir, "vercel.json"), "utf8"));
const cacheHeaders = deployment.headers.map((entry) => ({
  source: entry.source,
  cacheControl: entry.headers.find((header) => header.key.toLowerCase() === "cache-control")?.value,
}));
assert.ok(cacheHeaders.some((header) => header.source === "/sw.js" && header.cacheControl.includes("no-cache")));
assert.ok(cacheHeaders.some((header) => header.source === "/manifest.webmanifest" && header.cacheControl.includes("no-cache")));
assert.ok(cacheHeaders.some((header) => header.source === "/" && header.cacheControl.includes("no-cache")));
assert.ok(cacheHeaders.some((header) => header.source === "/assets/(.*)" && header.cacheControl.includes("immutable")));

console.log("PWA build artifacts and cache headers look valid.");
