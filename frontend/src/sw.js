const CACHE_NAME = __CACHE_NAME__;
const PRECACHE_ASSETS = __PRECACHE_ASSETS__;
const APP_SHELL_URL = new URL("/index.html", self.location.origin).href;
const OFFLINE_URL = new URL("/offline.html", self.location.origin).href;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_ASSETS)),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => Promise.all(
        cacheNames
          .filter((cacheName) => cacheName.startsWith("pika-precache-") && cacheName !== CACHE_NAME)
          .map((cacheName) => caches.delete(cacheName)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    event.waitUntil(self.skipWaiting());
  }
});

// Background Sync is only an accelerator. The open app performs authenticated sync.
self.addEventListener("sync", (event) => {
  if (event.tag !== "pika-outbox") return;
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    if (!windows.length) return;

    await Promise.race(windows.map((client) => new Promise((resolve) => {
      const channel = new MessageChannel();
      const timeout = setTimeout(() => resolve(false), 30000);
      channel.port1.onmessage = (message) => {
        clearTimeout(timeout);
        resolve(Boolean(message.data && message.data.ok));
        channel.port1.close();
      };
      client.postMessage({ type: "PIKA_BACKGROUND_SYNC" }, [channel.port2]);
    })));
  })());
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const requestUrl = new URL(request.url);

  // Leave writes and every API call to the network; never cache authenticated data.
  if (
    request.method !== "GET" ||
    requestUrl.origin !== self.location.origin ||
    requestUrl.pathname === "/api" ||
    requestUrl.pathname.startsWith("/api/")
  ) {
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(async () => {
        const cache = await caches.open(CACHE_NAME);
        const shell = await cache.match(APP_SHELL_URL);
        if (shell) return shell;

        const offlinePage = await cache.match(OFFLINE_URL);
        return offlinePage || Response.error();
      }),
    );
    return;
  }

  event.respondWith(
    caches.open(CACHE_NAME).then((cache) => cache.match(request)).then((cachedResponse) => cachedResponse || fetch(request)),
  );
});
