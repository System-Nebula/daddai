const CACHE_NAME = 'gopherbot-v1';
const API_CACHE_TIME = 30000; // 30 seconds

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll([
                '/',
                '/index.html',
                '/styles.css',
                '/app.js'
            ]);
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    // Cache API responses with short TTL
    if (event.request.url.includes('/api/')) {
        event.respondWith(
            caches.open(CACHE_NAME).then((cache) => {
                return cache.match(event.request).then((response) => {
                    if (response) {
                        const cachedTime = response.headers.get('sw-cached-time');
                        const now = Date.now();
                        if (cachedTime && (now - parseInt(cachedTime)) < API_CACHE_TIME) {
                            return response;
                        }
                    }
                    return fetch(event.request).then((fetchResponse) => {
                        if (fetchResponse.ok) {
                            const responseClone = fetchResponse.clone();
                            const headers = new Headers(responseClone.headers);
                            headers.set('sw-cached-time', now.toString());
                            const modifiedResponse = new Response(responseClone.body, {
                                status: responseClone.status,
                                statusText: responseClone.statusText,
                                headers: headers
                            });
                            cache.put(event.request, modifiedResponse);
                        }
                        return fetchResponse;
                    }).catch(() => {
                        // Return cached response if network fails
                        return cache.match(event.request);
                    });
                });
            })
        );
    } else {
        // Cache static assets
        event.respondWith(
            caches.match(event.request).then((response) => {
                return response || fetch(event.request).then((fetchResponse) => {
                    if (fetchResponse.ok) {
                        const cache = caches.open(CACHE_NAME);
                        cache.then(c => c.put(event.request, fetchResponse.clone()));
                    }
                    return fetchResponse;
                });
            })
        );
    }
});

