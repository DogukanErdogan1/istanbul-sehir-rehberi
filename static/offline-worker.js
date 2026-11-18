/* The only stored responses come from the visitor's explicit guide download. */
const PACK = "sehir-arasi-offline-pack-v1";
const PAGES = new Map([
  ["/", "/"],
  ["/hesabim", "/static/hesabim.html"],
  ["/rotalarim", "/static/rotalarim.html"],
  ["/gunlugum", "/static/gunlugum.html"],
  ["/static/hesabim.html", "/static/hesabim.html"],
  ["/static/rotalarim.html", "/static/rotalarim.html"],
  ["/static/gunlugum.html", "/static/gunlugum.html"],
  ["/static/photos/credits.html", "/static/photos/credits.html"],
  ["/static/photos/city-credits.html", "/static/photos/city-credits.html"],
]);

self.addEventListener("install", event => event.waitUntil(self.skipWaiting()));
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));

self.addEventListener("fetch", event => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin ||
      (request.cache === "reload" && request.credentials === "omit")) return;

  if (request.mode === "navigate") {
    const savedPage = PAGES.get(url.pathname);
    if (!savedPage) return;
    event.respondWith(fetch(request).catch(async error => {
      const saved = await caches.match(savedPage, { cacheName: PACK, ignoreVary: true });
      if (saved) return saved;
      throw error;
    }));
  } else if (url.pathname.startsWith("/static/")) {
    // Fetch new deployments normally, and keep the saved release intact until the
    // visitor refreshes the download. Never cache live responses or external tiles.
    event.respondWith(fetch(request).catch(async error => {
      const saved = await caches.match(request, { cacheName: PACK, ignoreVary: true });
      if (saved) return saved;
      throw error;
    }));
  }
});
