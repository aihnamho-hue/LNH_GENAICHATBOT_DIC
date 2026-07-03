// 최소 서비스 워커 — PWA 설치 요건 충족용
// 실시간 음성 스트리밍 앱이므로 오프라인 캐싱은 하지 않고,
// 정적 리소스만 가볍게 캐싱한다.
const CACHE_NAME = 'masamasa-v1';
const STATIC_ASSETS = [
  '/static/hamster.png',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/manifest.json'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  // WebSocket, API 요청은 절대 가로채지 않음 — 정적 파일만 캐시 우선
  if (event.request.method === 'GET' && url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
});
