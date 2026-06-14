const CACHE_NAME = 'aetherauth-cache-v1';
const URLS_TO_CACHE = [
  '/',
  '/manifest.json',
  '/dashboard',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(URLS_TO_CACHE))
  );
});

self.addEventListener('fetch', (event) => {
  // Only cache GET requests
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request)
      .then((response) => response || fetch(event.request))
  );
});

self.addEventListener('push', (event) => {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch {
      data = { title: "AetherAuth Security", body: event.data.text() };
    }
  }
  
  const options = {
    body: data.body || "New security notification",
    icon: '/icon-192x192.png',
    badge: '/icon-192x192.png'
  };

  event.waitUntil(
    self.registration.showNotification(data.title || "AetherAuth", options)
  );
});
