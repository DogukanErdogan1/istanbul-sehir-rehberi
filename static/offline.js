(() => {
  "use strict";
  const PACK = "sehir-arasi-offline-pack-v1";
  const I18N = window.GuideI18n;
  const en = I18N.language === "en";
  const choose = (tr, english) => en ? english : tr;
  const copy = {
    title: choose("Çevrimdışı rehber", "Offline guide"),
    intro: choose("İstanbul, Ankara ve İzmir’in duraklarını, fotoğraflarını ve hazır rotalarını iki dilde cihazına kaydet. Yaklaşık 8 MB.", "Save stops, photos and suggested routes for Istanbul, Ankara and Izmir in both languages. About 8 MB."),
    download: choose("Rehberi indir", "Download guide"),
    refresh: choose("İndirilen rehberi güncelle", "Update downloaded guide"),
    remove: choose("İndirmeyi kaldır", "Remove download"),
    downloading: choose("Rehber indiriliyor…", "Downloading guide…"),
    failed: choose("İndirme tamamlanamadı. Bağlantını ve cihazındaki boş alanı kontrol edip yeniden dene.", "The download could not finish. Check your connection and available storage, then try again."),
    removed: choose("İndirilen rehber bu cihazdan kaldırıldı.", "The downloaded guide was removed from this device."),
    unsupported: choose("İndirme için siteyi HTTPS üzerinden veya yerel tarayıcıda aç.", "Open the guide over HTTPS or on localhost to download it."),
    offline: choose("Çevrimdışısın. İndirilen durakları ve hazır rotaları kullanabilirsin. Takvim, hesap işlemleri ve yol tarifi için internet gerekir.", "You’re offline. Browse downloaded stops and suggested routes. The calendar, account features and directions need a connection."),
    noPack: choose("Bağlantı yok. Çevrimdışı kullanmak için yeniden bağlandığında rehberi indir.", "No connection. Download the guide when you reconnect to use it offline."),
    needsConnection: choose("Bu işlem için internet bağlantısı gerekiyor.", "This action needs an internet connection."),
    reviews: choose("Gezgin yorumlarını görmek için internete bağlan.", "Connect to the internet to see traveller reviews."),
    map: choose("Çevrimdışı haritada durak noktalarını görebilirsin. Harita zemini için internet gerekir.", "Stop markers are available offline. The base map needs an internet connection."),
  };
  const supported = window.isSecureContext && "serviceWorker" in navigator && "caches" in window;
  const endpoint = language => `/api/offline-guide?lang=${language}`;
  let registration;
  let operation = false;
  let unavailable = navigator.onLine === false;
  let stored;
  const $ = id => document.getElementById(id);

  async function readPack() {
    if (!supported) return null;
    try {
      const response = await caches.match(endpoint(I18N.language), { cacheName: PACK, ignoreVary: true });
      const pack = await response?.json();
      return pack?.version === 1 && Array.isArray(pack.places) ? pack : null;
    } catch {
      return null;
    }
  }

  function render() {
    const banner = $("offlineBanner");
    if (!banner) return;
    banner.hidden = !unavailable;
    banner.textContent = stored ? copy.offline : copy.noPack;
    const download = $("offlineDownload");
    download.textContent = stored ? copy.refresh : copy.download;
    download.disabled = operation || navigator.onLine === false || !supported;
    $("offlineRemove").hidden = !stored;
    $("offlineRemove").disabled = operation;
    const timestamp = $("offlineTimestamp");
    const date = new Date(stored?.downloaded_at || "");
    timestamp.hidden = !stored || !Number.isFinite(date.getTime());
    if (!timestamp.hidden) timestamp.textContent = choose("Cihazda kayıtlı · ", "Saved on this device · ") +
      date.toLocaleString(I18N.locale(), { dateStyle: "medium", timeStyle: "short" });
  }

  function setUnavailable(value) {
    unavailable = value;
    render();
  }

  function matchingPlaces(pack, params) {
    const city = params.get("city") ?? "istanbul";
    const query = I18N.fold(params.get("q") || "");
    const matches = pack.places.filter(place => {
      if (city && place.city_slug !== city) return false;
      if (params.get("category") && place.category_slug !== params.get("category")) return false;
      if (params.get("district") && place.district !== params.get("district")) return false;
      for (const field of ["indoor", "family_friendly", "wheelchair_accessible"]) {
        if (params.has(field) && place[field] !== (params.get(field) === "true")) return false;
      }
      const terms = [place.name, place.district, place.summary, place.description, place.category_name,
        place.city_name, place.original_content?.name, place.original_content?.summary];
      return !query || I18N.fold(terms.join(" ")).includes(query);
    });
    const nameOrder = (a, b) => a.name.localeCompare(b.name, I18N.locale());
    const ratingOrder = (a, b) => b.average_rating - a.average_rating || b.review_count - a.review_count || nameOrder(a, b);
    const popularOrder = (a, b) => Number(b.featured) - Number(a.featured) || b.review_count - a.review_count || b.average_rating - a.average_rating || nameOrder(a, b);
    const sort = params.get("sort");
    const limit = Math.max(1, Math.min(100, Number(params.get("limit")) || 50));
    const items = matches.sort(sort === "az" ? nameOrder : sort === "rating" ? ratingOrder : popularOrder).slice(0, limit);
    return { items, total: items.length };
  }

  function getSavedData(pack, url) {
    const city = url.searchParams.get("city") ?? "istanbul";
    const places = pack.places.filter(place => !city || place.city_slug === city);
    switch (url.pathname) {
      case "/api/places": return matchingPlaces(pack, url.searchParams);
      case "/api/cities": return pack.cities;
      case "/api/categories": return pack.categories.map(category => ({ ...category, place_count: places.filter(place => place.category_slug === category.slug).length }));
      case "/api/districts": return [...new Set(places.map(place => place.district))].sort((a, b) => a.localeCompare(b, I18N.locale()));
      case "/api/route-templates": return { items: pack.templates.filter(route => route.city_slug === city) };
      default: {
        const slug = url.pathname.match(/^\/api\/places\/([a-z0-9-]+)$/)?.[1];
        if (!slug) return undefined;
        const place = pack.places.find(item => item.slug === slug);
        return place ? { place, reviews: [], user_has_reviewed: false, offline: true } : undefined;
      }
    }
  }

  async function request(input, options) {
    const url = new URL(input, location.href);
    if (url.origin !== location.origin) return fetch(input, options);
    const method = (options?.method || "GET").toUpperCase();
    try {
      if (navigator.onLine === false) throw new Error(copy.needsConnection);
      const response = await fetch(input, options);
      if (response.ok && unavailable) setUnavailable(false);
      return response;
    } catch (error) {
      if (options?.signal?.aborted) throw error;
      setUnavailable(true);
      if (method === "GET" && /^\/api\/(?:cities|categories|districts|route-templates|places(?:\/[a-z0-9-]+)?)$/.test(url.pathname)) {
        stored = await readPack();
        render();
        if (stored) {
          const result = getSavedData(stored, url);
          if (result !== undefined) return Response.json(result);
        }
      }
      throw new Error(copy.needsConnection);
    }
  }

  function filesToDownload() {
    const files = ["/", "/static/hesabim.html", "/static/rotalarim.html", "/static/gunlugum.html",
      "/static/photos/credits.html", "/static/photos/city-credits.html", "/static/fonts/Manrope.ttf", "/static/fonts/Caveat.ttf",
      ...Object.values(window.GUIDE_PHOTOS || {}), endpoint("tr"), endpoint("en")];
    document.querySelectorAll('script[src], link[rel="stylesheet"], link[rel="preload"]').forEach(element => {
      const url = new URL(element.src || element.href, location.href);
      if (url.origin === location.origin && url.pathname.startsWith("/static/")) files.push(url.pathname + url.search);
    });
    return [...new Set(files)].map(file => new Request(new URL(file, location.origin), { cache: "reload", credentials: "omit" }));
  }

  async function download() {
    if (operation) return;
    operation = true;
    $("offlineFeedback").textContent = copy.downloading;
    render();
    try {
      await registration;
      const cache = await caches.open(PACK);
      // Cache.addAll replaces the previous download only when every request succeeds.
      const files = filesToDownload();
      await cache.addAll(files);
      stored = await readPack();
      if (!stored) throw new Error(copy.failed);
      $("offlineFeedback").textContent = "";
      setUnavailable(false);
      // Remove superseded versioned files after a successful update.
      const current = new Set(files.map(file => file.url));
      for (const file of await cache.keys()) if (!current.has(file.url)) await cache.delete(file);
    } catch {
      $("offlineFeedback").textContent = copy.failed;
    } finally {
      operation = false;
      render();
    }
  }

  async function remove() {
    if (operation) return;
    operation = true;
    render();
    try {
      await caches.delete(PACK);
      stored = null;
      $("offlineFeedback").textContent = copy.removed;
    } catch {
      $("offlineFeedback").textContent = copy.failed;
    } finally {
      operation = false;
      render();
    }
  }

  window.GuideOffline = Object.freeze({ request, copy, isOffline: () => unavailable || navigator.onLine === false });
  window.addEventListener("offline", () => setUnavailable(true));
  window.addEventListener("online", () => setUnavailable(false));
  document.addEventListener("DOMContentLoaded", async () => {
    $("offlineTitle").textContent = copy.title;
    $("offlineIntro").textContent = copy.intro;
    $("offlineRemove").textContent = copy.remove;
    $("offlineDownload").addEventListener("click", download);
    $("offlineRemove").addEventListener("click", remove);
    if (supported) {
      registration = navigator.serviceWorker.register("/offline-worker.js").then(async result => {
        const worker = result.installing;
        if (!result.active && worker) {
          await new Promise((resolve, reject) => {
            function check() {
              if (worker.state === "activated" || worker.state === "redundant") {
                worker.removeEventListener("statechange", check);
                if (worker.state === "activated") resolve();
                else reject(new Error(copy.failed));
              }
            }
            worker.addEventListener("statechange", check);
            check();
          });
        }
      });
      registration.catch(() => { $("offlineFeedback").textContent = copy.failed; });
      stored = await readPack();
    } else {
      $("offlineFeedback").textContent = copy.unsupported;
    }
    render();
  });
})();
