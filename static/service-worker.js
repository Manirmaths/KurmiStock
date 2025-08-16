const CACHE = 'kurmistock-static-v3';
const ASSETS = [
  '/static/app.js',
  '/static/styles.css',
  '/static/manifest.webmanifest',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png'
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
  self.skipWaiting();          // activate new SW immediately
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)));
      await self.clients.claim();
    })()
  );
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  const accept = e.request.headers.get('accept') || '';

  // Never cache API, auth, or ANY HTML views (/, /dashboard, etc.)
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/auth/') || accept.includes('text/html')) {
    e.respondWith(fetch(e.request).catch(() =>
      new Response('<!doctype html><meta charset="utf-8"><div style="font:16px system-ui;padding:1rem">You are offline.</div>', { headers: { 'Content-Type': 'text/html; charset=utf-8' }})
    ));
    return;
  }

  // Static files: cache-first
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});

// Allow page to request cache clearing (on logout)
self.addEventListener('message', async (e) => {
  if (e.data === 'CLEAR_CACHES') {
    const keys = await caches.keys();
    await Promise.all(keys.map(k => caches.delete(k)));
  }
});
