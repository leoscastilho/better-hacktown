// Bump this version whenever the cached app shell changes.
const CACHE_NAME = 'hacktown-shell-v2';

// Precache only the app shell. Paths are relative to the service worker's
// scope (e.g. /better-hacktown/), so they work regardless of the deploy path.
// Event data is intentionally NOT precached: it is organized per year under
// events/<year>/ and fetched on demand with cache-busting, so only the
// selected year's data is ever loaded (runtime caching still applies below).
const urlsToCache = [
  './',
  './index.html',
  './logo.png'
];

// Install event - cache resources
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
      .catch((error) => {
        console.error('Cache install failed:', error);
        // Don't let the installation fail if some resources can't be cached
        return Promise.resolve();
      })
  );
  // Force the waiting service worker to become the active service worker
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  // Ensure the service worker takes control immediately
  self.clients.claim();
});

// Offline fallback page for navigations when network AND cache both miss.
function offlinePage() {
  return new Response(
    `
    <!DOCTYPE html>
    <html>
      <head>
        <title>HackTown - Offline</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
          body { font-family: Inter, sans-serif; text-align: center; padding: 50px; background: #f8fafc; }
          .offline-message { background: white; padding: 40px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); max-width: 400px; margin: 0 auto; }
          h1 { color: #393F73; margin-bottom: 20px; }
          p { color: #64748b; line-height: 1.6; }
          button { background: linear-gradient(135deg, #393F73, #6366f1); color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; margin-top: 20px; }
        </style>
      </head>
      <body>
        <div class="offline-message">
          <h1>HackTown</h1>
          <p>Você está offline. Algumas funcionalidades podem não estar disponíveis.</p>
          <button onclick="window.location.reload()">Tentar Novamente</button>
        </div>
      </body>
    </html>
    `,
    { headers: { 'Content-Type': 'text/html' } }
  );
}

// Fetch event
self.addEventListener('fetch', (event) => {
  // Only handle GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // NETWORK-FIRST for page navigations (the app shell / index.html).
  // This guarantees a fresh index.html after a deploy or restructure, so a
  // stale cached shell can never keep pointing at old data paths (e.g. after
  // events/ was reorganized into events/<year>/). Falls back to cache, then
  // to the offline page, when the network is unavailable.
  if (event.request.mode === 'navigate' || event.request.destination === 'document') {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          return response;
        })
        .catch(async () => {
          return (
            (await caches.match(event.request)) ||
            (await caches.match('./index.html')) ||
            (await caches.match('./')) ||
            offlinePage()
          );
        })
    );
    return;
  }

  // CACHE-FIRST for everything else (static assets, images).
  // Event data is fetched with a ?t= cache-buster, so it always hits the
  // network and is never served stale from here.
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) {
        return cached;
      }
      return fetch(event.request).then((response) => {
        if (!response || response.status !== 200 || response.type !== 'basic') {
          return response;
        }
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return response;
      });
    })
  );
});