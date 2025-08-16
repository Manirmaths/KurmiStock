const CACHE = 'stockwise-v1';
const ASSETS = [
  '/', '/dashboard', '/products',
  '/static/app.js', '/static/styles.css',
  '/static/manifest.webmanifest',
  '/static/icons/icon-192.png', '/static/icons/icon-512.png'
];

self.addEventListener('install', (e)=>{
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)));
  self.skipWaiting();
});
self.addEventListener('activate', (e)=>{ self.clients.claim(); });

self.addEventListener('fetch', (e)=>{
  const url = new URL(e.request.url);
  if (url.origin === location.origin && ASSETS.includes(url.pathname)) {
    e.respondWith(caches.match(e.request).then(r=>r || fetch(e.request)));
  }
});
