const CACHE_NAME = 'mediconnect-loader-v1';
const urlsToCache = [
  '/',
  '/index.html',
  '/static/images/mediconnect_logo_transparent.png',
  '/static/images/mediconnect_favicon.ico',
  '/static/css/base.css'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        return response || fetch(event.request);
      })
  );
});