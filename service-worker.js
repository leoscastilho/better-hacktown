const CACHE_NAME = 'hacktown-2025-v1';
const urlsToCache = [
  '/hacktown-events/',
  '/hacktown-events/index.html',
  '/hacktown-events/logo.png',
  '/hacktown-events/manifest.json',
  '/hacktown-events/events/summary.json',
  '/hacktown-events/events/locations.json',
  '/hacktown-events/events/hacktown_events_2025-07-30.json',
  '/hacktown-events/events/hacktown_events_2025-07-31.json',
  '/hacktown-events/events/hacktown_events_2025-08-01.json',
  '/hacktown-events/events/hacktown_events_2025-08-02.json',
  '/hacktown-events/events/hacktown_events_2025-08-03.json'
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

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
  // Only handle GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Return cached version if available
        if (response) {
          return response;
        }

        // Otherwise, fetch from network
        return fetch(event.request).then((response) => {
          // Don't cache non-successful responses
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }

          // Clone the response for caching
          const responseToCache = response.clone();

          caches.open(CACHE_NAME)
            .then((cache) => {
              cache.put(event.request, responseToCache);
            });

          return response;
        });
      })
      .catch(() => {
        // If both cache and network fail, return a custom offline page for navigation requests
        if (event.request.destination === 'document') {
          return new Response(
            `
            <!DOCTYPE html>
            <html>
              <head>
                <title>HackTown 2025 - Offline</title>
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
                  <h1>HackTown 2025</h1>
                  <p>Você está offline. Algumas funcionalidades podem não estar disponíveis.</p>
                  <button onclick="window.location.reload()">Tentar Novamente</button>
                </div>
              </body>
            </html>
            `,
            {
              headers: { 'Content-Type': 'text/html' }
            }
          );
        }
      })
  );
});