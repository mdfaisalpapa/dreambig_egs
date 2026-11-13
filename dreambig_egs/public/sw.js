// DREAM BIG - Early Goal Setting Progressive Web App (PWA) Service Worker
const CACHE_NAME = 'dreambig-egs-v1';

const STATIC_ASSETS = [
  '/manifest.json',
  '/assets/dreambig_egs/icons/dreambig-icon.svg',
  '/assets/dreambig_egs/icons/icon-192.png',
  '/assets/dreambig_egs/icons/icon-512.png',
  '/assets/dreambig_egs/css/pwa-app.css',
  '/assets/dreambig_egs/js/pwa-install.js'
];

// Install: Cache critical static shell assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('[DREAM BIG PWA] Non-fatal caching notice during install:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// Activate: Clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            console.log('[DREAM BIG PWA] Removing outdated cache:', key);
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch: Network First with Cache Fallback for navigation & dynamic pages; Cache First for static assets
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Skip non-GET requests and Frappe RPC / API calls to ensure live transactional data
  if (req.method !== 'GET' || url.pathname.startsWith('/api/')) {
    return;
  }

  // Static Assets: Cache-first
  if (url.pathname.startsWith('/assets/dreambig_egs/')) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) return cached;
        return fetch(req).then((networkResp) => {
          if (networkResp && networkResp.status === 200) {
            const clone = networkResp.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
          }
          return networkResp;
        });
      })
    );
    return;
  }

  // Web Pages / Documents: Network first, fall back to cached copy
  event.respondWith(
    fetch(req).catch(() => {
      return caches.match(req);
    })
  );
});
