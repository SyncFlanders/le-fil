// Le Fil — service worker : l'appli s'ouvre même sans réseau (dernière édition lue).
const VERSION = "lefil-v1";
const COQUILLE = ["./", "index.html", "manifest.webmanifest", "icones/icone-192.png", "icones/icone-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(COQUILLE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((cles) => Promise.all(cles.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Réseau d'abord (pour avoir les nouvelles fraîches), cache en secours.
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const memeOrigine = url.origin === self.location.origin;
  const police = url.host.endsWith("fonts.googleapis.com") || url.host.endsWith("fonts.gstatic.com");
  if (!memeOrigine && !police) return;
  const cle = memeOrigine ? url.origin + url.pathname : req.url; // ignore le ?t= anti-cache
  e.respondWith(
    fetch(req)
      .then((rep) => {
        if (rep.ok) caches.open(VERSION).then((c) => c.put(cle, rep.clone()));
        return rep;
      })
      .catch(() => caches.match(cle).then((m) => m || caches.match("index.html")))
  );
});
