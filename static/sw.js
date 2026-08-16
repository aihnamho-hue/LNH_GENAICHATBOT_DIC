// 최소 서비스 워커 — PWA 설치 요건 충족용
// 실시간 음성 스트리밍 앱이므로 오프라인 캐싱은 하지 않고,
// 정적 리소스만 가볍게 캐싱한다.
// ★ 전략: 네트워크 우선(network-first). 예전엔 캐시 우선이라 캐릭터 이미지를
//   교체해도 옛 이미지(마사마사 햄스터)가 계속 보이는 문제가 있었다.
//   이제 온라인이면 항상 새 파일을 받고, 오프라인일 때만 캐시로 대체한다.
const CACHE_NAME = 'hoarang-v102';
const STATIC_ASSETS = [
  '/static/hamster.png?v=85',
  '/static/icon-192.png?v=85',
  '/static/icon-512.png?v=85',
  '/static/manifest.json?v=85'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)).catch(() => {})
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
  if (event.request.method !== 'GET') return;

  // 글꼴·사운드는 파일명이 바뀌지 않고 ?v= 로 버전을 구분하므로 캐시 우선이 안전하다.
  // (매번 다시 받으면 지마켓 산스 1MB를 접속할 때마다 내려받게 된다)
  if (/^\/static\/(fonts\/|.*\.(woff2|mp3|mp4)$)/.test(url.pathname)) {
    event.respondWith(
      caches.match(event.request).then((hit) => hit || fetch(event.request).then((res) => {
        const copy = res.clone();
        caches.open(CACHE_NAME).then((c) => c.put(event.request, copy)).catch(() => {});
        return res;
      }))
    );
    return;
  }

  // 나머지 정적 파일(이미지·manifest 등)은 네트워크 우선
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          // 받아온 최신 파일을 캐시에 갱신(오프라인 대비)
          const copy = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(event.request, copy)).catch(() => {});
          return res;
        })
        .catch(() => caches.match(event.request))   // 오프라인 → 캐시 사용
    );
  }
});

/* ── 알림 ──
   서버가 하루 세 번(한국시간 10·14·20시) 보내는 알림을 받아 띄운다. */
self.addEventListener('push', (event) => {
  let d = { title: '호아랑', body: '같이 한국어로 이야기해요!' };
  try { if (event.data) d = Object.assign(d, event.data.json()); } catch (e) {}
  event.waitUntil(
    self.registration.showNotification(d.title, {
      body: d.body,
      icon: '/static/icon-192.png',
      badge: '/static/icon-192.png',
      tag: 'hoarang-daily',        // 같은 태그 = 알림이 쌓이지 않고 최신 것으로 대체
      renotify: true,
      data: { url: d.url || '/' },
    })
  );
});

/* 알림을 누르면 이미 열려 있는 창으로, 없으면 새로 연다 */
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if ('focus' in c) return c.focus();
      }
      return self.clients.openWindow(target);
    })
  );
});
