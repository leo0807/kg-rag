// v5: fix navigate-on-localhost error + fix clone-after-consumed error
const CACHE = "cps-v5";

self.addEventListener("install", (e) => {
  e.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
    // Removed c.navigate(c.url) — fails on localhost; layout.tsx handles
    // controllerchange → window.location.reload() for production instead.
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // Never intercept: non-GET, API calls, Next.js chunks, SW itself, HTML navigations
  if (
    e.request.method !== "GET" ||
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/_next/") ||
    url.pathname === "/sw.js" ||
    (e.request.headers.get("Accept") ?? "").includes("text/html")
  ) return;

  e.respondWith(
    caches.match(e.request).then((cached) => {
      if (cached) return cached;
      return fetch(e.request).then((res) => {
        if (res.ok) {
          // Clone synchronously BEFORE returning res to the browser.
          // Cloning inside caches.open().then() is too late — res.body
          // is already consumed by the time that async callback runs.
          const clone = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, clone));
        }
        return res;
      });
    })
  );
});
