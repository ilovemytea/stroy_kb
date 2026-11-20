// Cache the complete public knowledge base for a repeat visit without a network.
const CACHE='dusovstroimir-8fb8edf4719e';
const ASSETS=['./','./index.html','./style.css?v=8fb8edf4719e','./app.js?v=8fb8edf4719e','./engine.js','./graph.js','./knowledge.json?v=8fb8edf4719e','./review.js?v=8fb8edf4719e','./icon.svg','./manifest.webmanifest'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('dusovstroimir-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET'||new URL(e.request.url).origin!==self.location.origin)return;
  if(e.request.mode==='navigate'){
    e.respondWith(fetch(e.request).catch(()=>caches.match(new URL('./index.html',self.location.href))));return;
  }
  e.respondWith(fetch(e.request).then(response=>{
    if(response.ok){const copy=response.clone();e.waitUntil(caches.open(CACHE).then(c=>c.put(e.request,copy)));}
    return response;
  }).catch(()=>caches.match(e.request)));
});
