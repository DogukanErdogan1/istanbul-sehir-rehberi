(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const grid = $("#placeGrid");
  const searchInput = $("#searchInput");
  const categoryChips = $("#categoryChips");
  const districtSelect = $("#districtSelect");
  const sortSelect = $("#sortSelect");
  const favoritesToggle = $("#favoritesToggle");
  const favoriteCount = $("#favoriteCount");
  const resultCount = $("#resultCount");
  const emptyState = $("#emptyState");
  const detailDialog = $("#detailDialog");
  const dialogContent = $("#dialogContent");
  const toast = $("#toast");
  const authDialog = $("#authDialog");
  const profileSection = $("#profile");
  const routeDialog = $("#routeDialog");
  const adminDialog = $("#adminDialog");
  const routesGrid = $("#routesGrid");
  const adminList = $("#adminList");
  const categoryNames = new Map();
  const categoryArt = {
    museum: "MÜZE & SANAT",
    history: "TARİHÎ ROTA",
    view: "ŞEHİR MANZARASI",
    nature: "AÇIK HAVA",
    culture: "KÜLTÜR",
  };
  const markLetters = {
    ayasofya: "A",
    "topkapi-sarayi": "T",
    "yerebatan-sarnici": "Y",
    "istanbul-arkeoloji-muzeleri": "İ",
    "galata-kulesi": "G",
    "pera-muzesi": "P",
    "masumiyet-muzesi": "M",
    "dolmabahce-sarayi": "D",
    "rahmi-koc-muzesi": "R",
    "sakip-sabanci-muzesi": "S",
    "emirgan-korusu": "E",
    "moda-sahili": "M",
    "pierreloti-tepesi": "P",
    "suleymaniye-camii": "S",
    "istanbul-modern": "İ",
  };

  const state = { query: "", category: "", district: "", city: "istanbul", indoor: false, family: false, accessible: false, sort: "popular", favoritesOnly: false, showAll: false, allPlaces: [], catalog: [], catalogStatus: "idle", catalogError: "", catalogLegacy: false, categories: [], routes: [], journal: [], journalError: "", routesError: "", sessionReady: false, user: null };
  const photos = window.GUIDE_PHOTOS || {};
  const cityDisplayNames = { istanbul: "İstanbul", ankara: "Ankara", izmir: "İzmir" };
  const suggestedSlugs = ["istanbul-modern", "yerebatan-sarnici", "emirgan-korusu"];
  let searchTimer;
  let toastTimer;
  let placesRequestId = 0;
  let filtersRequestId = 0;
  let catalogRequest = null;
  let authMode = "login";
  let selectedRouteSlugs = [];
  let favorites = readFavorites();

  function readFavorites() {
    try {
      const data = JSON.parse(localStorage.getItem("sehir-arasi:favorites") || "[]");
      return new Set(Array.isArray(data) ? data.filter((value) => typeof value === "string") : []);
    } catch {
      return new Set();
    }
  }

  function saveFavorites() {
    if (!state.user) {
      try { localStorage.setItem("sehir-arasi:favorites", JSON.stringify([...favorites])); } catch { /* Storage may be disabled. */ }
    }
    favoriteCount.textContent = String(favorites.size);
    renderProfile();
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("is-visible"), 2200);
  }

  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data.detail === "string" ? data.detail : Array.isArray(data.detail) && data.detail[0]?.msg ? data.detail[0].msg.replace(/^Value error,\s*/, "") : "İşlem tamamlanamadı.";
      throw new Error(detail);
    }
    return data;
  }

  async function loadFilters() {
    const requestId = ++filtersRequestId;
    try {
      const [categories, districts] = await Promise.all([
        fetchJson(`/api/categories?city=${encodeURIComponent(state.city)}`),
        fetchJson(`/api/districts?city=${encodeURIComponent(state.city)}`),
      ]);
      if (requestId !== filtersRequestId) return;
      categories.forEach((category) => categoryNames.set(category.slug, category.name));
      state.categories = categories;
      categoryChips.innerHTML = [
        '<button class="chip is-active" data-category="" type="button">Hepsi</button>',
        ...categories.map((category) => `<button class="chip" data-category="${escapeHtml(category.slug)}" type="button">${escapeHtml(category.name)}</button>`),
      ].join("");
      updateCategorySelection();
      districtSelect.innerHTML = '<option value="">Tüm semtler</option>' + districts
        .map((district) => `<option value="${escapeHtml(district)}">${escapeHtml(district)}</option>`).join("");
      $("#adminCategory").innerHTML = categories
        .map((category) => `<option value="${escapeHtml(category.slug)}">${escapeHtml(category.name)}</option>`).join("");
    } catch {
      showToast("Filtreler yüklenemedi. Sayfayı yenileyip tekrar dene.");
    }
  }

  function heartIcon() {
    return '<svg class="icon" aria-hidden="true"><use href="#i-heart"/></svg>';
  }

  function placeImage(place) {
    const photo = photos[place.slug];
    const letter = markLetters[place.slug] || place.name.charAt(0).toLocaleUpperCase("tr-TR");
    return `<span class="photo-fallback" aria-hidden="true">${escapeHtml(letter)}</span>${photo
      ? `<img class="place-photo" src="${escapeHtml(photo)}" alt="${escapeHtml(place.name)}" loading="lazy" decoding="async" />`
      : ""}`;
  }

  function makeCard(place) {
    const active = favorites.has(place.slug);
    const category = categoryNames.get(place.category_slug) || categoryArt[place.category_slug] || "İSTANBUL";
    const reviewText = place.review_count === 1 ? "1 yorum" : `${place.review_count} yorum`;
    return `
      <article class="place-card" data-category="${escapeHtml(place.category_slug)}">
        <button class="card-image-button" data-open="${escapeHtml(place.slug)}" type="button" aria-label="${escapeHtml(place.name)} ayrıntılarını aç">
          <span class="card-art art-${escapeHtml(place.art)}">
            ${placeImage(place)}
            <span class="card-category-label">${escapeHtml(category)}</span>
          </span>
        </button>
        <div class="card-content">
          <div class="card-title-row">
            <h3 class="card-title"><button data-open="${escapeHtml(place.slug)}" type="button">${escapeHtml(place.name)}</button></h3>
            <button class="favorite-button ${active ? "is-active" : ""}" data-favorite="${escapeHtml(place.slug)}" type="button" aria-label="${active ? "Favorilerden çıkar" : "Favorilere ekle"}: ${escapeHtml(place.name)}" aria-pressed="${active}">${heartIcon()}</button>
          </div>
          <div class="card-footer">
            <span class="card-location">${escapeHtml(place.district)}</span>
            <span class="card-rating" aria-label="${Number(place.average_rating).toFixed(1)} puan, ${reviewText}"><span class="rating-star" aria-hidden="true">★</span><b>${Number(place.average_rating).toFixed(1)}</b></span>
          </div>
        </div>
      </article>`;
  }

  function renderPlaces(places) {
    state.allPlaces = places;
    const visible = state.favoritesOnly ? places.filter((place) => favorites.has(place.slug)) : places;
    const filtered = Boolean(state.query.trim() || state.category || state.district || state.favoritesOnly || state.indoor || state.family || state.accessible || state.sort !== "popular");
    const suggested = !filtered && !state.showAll;
    const picks = suggestedSlugs.map((slug) => visible.find((place) => place.slug === slug)).filter(Boolean);
    const displayed = suggested ? [...picks, ...visible.filter((place) => !suggestedSlugs.includes(place.slug))].slice(0, 3) : visible;
    grid.innerHTML = displayed.map(makeCard).join("");
    grid.setAttribute("aria-busy", "false");
    emptyState.hidden = visible.length > 0;
    const showAllButton = $("#showAllPlaces");
    showAllButton.hidden = filtered || visible.length <= 3;
    showAllButton.setAttribute("aria-expanded", String(state.showAll));
    showAllButton.innerHTML = `${state.showAll ? "Daha az göster" : `Tüm yerleri keşfet (${visible.length})`} <svg class="icon" aria-hidden="true"><use href="#i-arrow"/></svg>`;
    if (state.favoritesOnly) {
      resultCount.textContent = `${visible.length} kaydedilmiş durak`;
    } else if (suggested) {
      resultCount.textContent = `${displayed.length} küçük öneri · Keşfedilecek ${visible.length} durak`;
    } else {
      resultCount.textContent = `${visible.length} güzel durak seni bekliyor`;
    }
    window.GuideFeatures?.placesChanged(visible);
  }

  async function loadPlaces() {
    const requestId = ++placesRequestId;
    grid.setAttribute("aria-busy", "true");
    resultCount.textContent = "Duraklar aranıyor…";
    const params = new URLSearchParams({ sort: state.sort, limit: "100", city: state.city });
    if (state.indoor) params.set("indoor", "true");
    if (state.family) params.set("family_friendly", "true");
    if (state.accessible) params.set("wheelchair_accessible", "true");
    if (state.query.trim()) params.set("q", state.query.trim());
    if (state.category) params.set("category", state.category);
    if (state.district) params.set("district", state.district);
    try {
      const result = await fetchJson(`/api/places?${params}`);
      if (requestId !== placesRequestId) return;
      renderPlaces(result.items);
    } catch {
      if (requestId !== placesRequestId) return;
      grid.innerHTML = "";
      grid.setAttribute("aria-busy", "false");
      emptyState.hidden = false;
      resultCount.textContent = "Duraklar yüklenemedi";
      window.GuideFeatures?.placesChanged([]);
      showToast("Sunucuya ulaşılamadı. Uygulamanın çalıştığından emin ol.");
    }
  }

  function updateCategorySelection() {
    categoryChips.querySelectorAll(".chip").forEach((chip) => {
      const active = chip.dataset.category === state.category;
      chip.classList.toggle("is-active", active);
      chip.setAttribute("aria-pressed", String(active));
    });
  }

  async function toggleFavorite(slug) {
    const wasSaved = favorites.has(slug);
    if (state.user) {
      try {
        await fetchJson(`/api/favorites/${encodeURIComponent(slug)}`, { method: wasSaved ? "DELETE" : "POST" });
      } catch (error) {
        showToast(error.message);
        return;
      }
    }
    if (wasSaved) favorites.delete(slug); else favorites.add(slug);
    saveFavorites();
    favoritesToggle.classList.toggle("is-active", state.favoritesOnly);
    favoritesToggle.setAttribute("aria-pressed", String(state.favoritesOnly));
    const detailFavorite = dialogContent.querySelector(`[data-favorite="${CSS.escape(slug)}"]`);
    if (detailFavorite) {
      detailFavorite.classList.toggle("is-active", !wasSaved);
      detailFavorite.setAttribute("aria-pressed", String(!wasSaved));
      detailFavorite.innerHTML = heartIcon();
      detailFavorite.setAttribute("aria-label", `${wasSaved ? "Favorilere ekle" : "Favorilerden çıkar"}: ${state.allPlaces.find((place) => place.slug === slug)?.name || slug}`);
    }
    renderPlaces(state.allPlaces);
    showToast(wasSaved ? "Kaydedilenlerden çıkarıldı." : "Favorilerine kaydedildi.");
  }

  function stars(rating) {
    return `<span class="rating-star" aria-label="${rating} üzerinden 5 yıldız">${"★".repeat(rating)}${"☆".repeat(5 - rating)}</span>`;
  }

  function reviewMarkup(review) {
    const date = new Date(review.created_at);
    const dateText = Number.isNaN(date.valueOf()) ? "" : new Intl.DateTimeFormat("tr-TR", { dateStyle: "medium" }).format(date);
    return `<article class="review-item">
      <div class="review-item-top"><strong>${escapeHtml(review.author)}</strong><time>${escapeHtml(dateText)}</time></div>
      <div>${stars(Number(review.rating))}</div>
      <p>${escapeHtml(review.body)}</p>
    </article>`;
  }

  async function showDetails(slug) {
    detailDialog.showModal();
    dialogContent.innerHTML = '<div class="dialog-loading">Durak bilgileri yükleniyor…</div>';
    try {
      const result = await fetchJson(`/api/places/${encodeURIComponent(slug)}`);
      renderDetails(result);
    } catch (error) {
      dialogContent.innerHTML = `<p role="alert">${escapeHtml(error.message)}</p>`;
    }
  }

  function renderDetails({ place, reviews, user_has_reviewed: hasReviewed }) {
    const category = categoryNames.get(place.category_slug) || categoryArt[place.category_slug] || "İSTANBUL";
    const mapsQuery = encodeURIComponent(`${place.name}, ${place.district}, ${place.city_name || "İstanbul"}`);
    const reviewForm = !state.user
      ? '<p class="review-login">Yorum yazmak için <button class="text-button" data-review-login type="button">giriş yap</button>.</p>'
      : hasReviewed
        ? '<p class="review-login">Bu durak için yorumunu paylaştın. Teşekkürler!</p>'
        : `<form class="review-form" id="reviewForm" data-slug="${escapeHtml(place.slug)}">
          <h3>Senin deneyimin?</h3><p>Bu durağı ziyaret ettiysen kısa bir not bırak.</p>
          <div class="form-grid">
            <div class="form-field"><label for="reviewRating">Puanın</label><select id="reviewRating" name="rating"><option value="5">★★★★★ · Harika</option><option value="4">★★★★☆ · Çok iyi</option><option value="3">★★★☆☆ · İyi</option><option value="2">★★☆☆☆ · Olabilir</option><option value="1">★☆☆☆☆ · Beklentimin altında</option></select></div>
            <div class="form-field form-field-wide"><label for="reviewBody">Yorumun</label><textarea id="reviewBody" name="body" minlength="8" maxlength="600" required placeholder="Neyi sevdin? Başka gezginlere ne önerirsin?"></textarea></div>
          </div>
          <button class="button button-dark" type="submit">Yorumunu ekle <span aria-hidden="true">↗</span></button>
          <p class="form-message" id="formMessage" aria-live="polite"></p>
        </form>`;
    dialogContent.innerHTML = `
      <div class="dialog-hero card-art art-${escapeHtml(place.art)}">
        ${placeImage(place)}
      </div>
      <div class="dialog-title-row">
        <div><span class="card-category">${escapeHtml(category)}</span><h2 id="dialogTitle">${escapeHtml(place.name)}</h2><p class="dialog-location">⌖ ${escapeHtml(place.district)} · ${escapeHtml(place.address)}</p></div>
        <button class="favorite-button ${favorites.has(place.slug) ? "is-active" : ""}" data-favorite="${escapeHtml(place.slug)}" type="button" aria-label="${favorites.has(place.slug) ? "Favorilerden çıkar" : "Favorilere ekle"}: ${escapeHtml(place.name)}" aria-pressed="${favorites.has(place.slug)}">${heartIcon()}</button>
      </div>
      <div class="dialog-stats"><span class="dialog-stat">★ ${Number(place.average_rating).toFixed(1)} · ${place.review_count} yorum</span><span class="dialog-stat">◷ ${escapeHtml(place.duration)}</span><span class="dialog-stat">${escapeHtml(place.best_for)}</span></div>
      <p class="dialog-description">${escapeHtml(place.description)}</p>
      <a class="dialog-map" href="https://www.google.com/maps/search/?api=1&query=${mapsQuery}" target="_blank" rel="noopener noreferrer">Haritada aç <span aria-hidden="true">↗</span></a>
      <section class="review-section" aria-labelledby="reviewsTitle">
        <div class="review-heading"><h3 id="reviewsTitle">Gezgin notları</h3><span>${reviews.length} yorum gösteriliyor</span></div>
        <div class="review-list">${reviews.length ? reviews.map(reviewMarkup).join("") : '<p class="no-reviews">Henüz yorum yok. İlk notu sen bırak.</p>'}</div>
        ${reviewForm}
      </section>`;
    window.GuideFeatures?.detailsChanged(place);
  }

  async function loadCatalog() {
    if (catalogRequest) return catalogRequest;
    state.catalogStatus = "loading";
    state.catalogError = "";
    if (routeDialog.open) renderRoutePicker();
    catalogRequest = (async () => {
      try {
        const result = await fetchJson("/api/places?sort=az&limit=100&city=");
        if (!Array.isArray(result.items)) throw new Error("Durak listesi okunamadı.");
        const items = result.items.filter((place) => typeof place.slug === "string" && typeof place.name === "string");
        state.catalogLegacy = items.some((place) => !place.city_slug);
        state.catalog = items.map((place) => {
          // The original API only had these 15 Istanbul landmarks and no city field.
          const city = place.city_slug || (Object.prototype.hasOwnProperty.call(markLetters, place.slug) ? "istanbul" : "");
          return { ...place, city_slug: city, city_name: place.city_name || ({ istanbul: "İstanbul", ankara: "Ankara", izmir: "İzmir" })[city] || "Şehir bilgisi eksik" };
        });
        state.catalogStatus = "ready";
        renderAdminList();
        renderProfile();
      } catch (error) {
        state.catalogStatus = "error";
        state.catalogError = error.message;
      } finally {
        catalogRequest = null;
        if (routeDialog.open) renderRoutePicker();
      }
    })();
    return catalogRequest;
  }

  async function loadSavedFavorites() {
    if (!state.user) return;
    const result = await fetchJson("/api/favorites");
    favorites = new Set(result.slugs);
    saveFavorites();
    renderPlaces(state.allPlaces);
    renderProfile();
  }

  async function mergeGuestFavorites() {
    if (!state.user) return;
    const guestFavorites = [...readFavorites()];
    if (!guestFavorites.length) return;
    const transfers = await Promise.allSettled(guestFavorites.map((slug) =>
      fetchJson("/api/favorites/" + encodeURIComponent(slug), { method: "POST" })
    ));
    const pendingFavorites = guestFavorites.filter((_, index) => transfers[index].status === "rejected");
    try { localStorage.setItem("sehir-arasi:favorites", JSON.stringify(pendingFavorites)); } catch { /* Storage may be disabled. */ }
  }

  async function loadSession() {
    try {
      const result = await fetchJson("/api/auth/me");
      state.user = result.user;
    } catch {
      state.user = null;
    }
    state.sessionReady = true;
    if (!state.user) favorites = readFavorites();
    renderAccountUi();
    if (state.user) {
      try {
        await mergeGuestFavorites();
        await loadSavedFavorites();
      } catch (error) {
        showToast(error.message);
      }
    }
    saveFavorites();
    await loadRoutes();
  }

  function renderAccountUi() {
    const signedIn = Boolean(state.user);
    window.GuidePages?.setSession(state.user, state.sessionReady);
    $("#accountButton").textContent = signedIn ? "Hesabım" : "Giriş yap";
    $("#accountButton").setAttribute("aria-label", signedIn ? "Hesabım: " + state.user.name : "Giriş yap");
    $("#accountButton").disabled = !state.sessionReady;
    $("#accountButton").setAttribute("aria-busy", String(!state.sessionReady));
    $("#demoLoginButton").hidden = !state.sessionReady || signedIn;
    profileSection.hidden = !signedIn;
    $("#adminPanel").hidden = state.user?.role !== "admin";
    if (state.user) {
      $("#accountName").textContent = state.user.name;
      $("#accountEmail").textContent = state.user.email;
    }
    renderRoutes();
    renderAdminList();
    renderProfile();
    window.GuideFeatures?.sessionChanged();
  }

  function setAuthMode(mode) {
    authMode = mode;
    $("#authForm").reset();
    $("#authMessage").textContent = "";
    $("#authNameField").hidden = mode !== "register";
    $("#authName").required = mode === "register";
    $("#authPassword").autocomplete = mode === "register" ? "new-password" : "current-password";
    $("#authSubmit").innerHTML = mode === "register" ? 'Hesap oluştur <span aria-hidden="true">↗</span>' : 'Giriş yap <span aria-hidden="true">↗</span>';
    authDialog.querySelectorAll("[data-auth-mode]").forEach((tab) => tab.classList.toggle("is-active", tab.dataset.authMode === mode));
  }

  function openAuth(mode = "login") {
    setAuthMode(mode);
    authDialog.showModal();
  }

  function renderRoutes() {
    const count = $("#routesCount");
    if (!state.user) {
      routesGrid.innerHTML = '<div class="route-guest"><strong>Rotan henüz başlamadı.</strong><span>Durakları bir araya getirmek için hesabına giriş yap.</span><button data-open-auth type="button">Giriş yap ↗</button></div>';
      count.textContent = "";
      return;
    }
    if (state.routesError) {
      routesGrid.innerHTML = '<div class="personal-empty"><h3>Rotalarını açamadık.</h3><p>' + escapeHtml(state.routesError) + '</p><button class="button button-dark" data-retry-routes type="button">Yeniden dene</button></div>';
      return;
    }
    const query = $("#personalRouteSearch").value.trim().toLocaleLowerCase("tr-TR");
    const city = $("#personalRouteCity").value;
    const routes = state.routes.filter(route => {
      const haystack = [route.title, route.notes, ...route.places.map(place => place.name)].join(" ").toLocaleLowerCase("tr-TR");
      return (!query || haystack.includes(query)) && (!city || route.places.some(place => place.city_slug === city));
    });
    count.textContent = routes.length + " rota" + (routes.length !== state.routes.length ? " · Toplam " + state.routes.length : " · Yola çıkmaya hazır");
    if (!routes.length) {
      const filtered = Boolean(query || city);
      routesGrid.innerHTML = `<div class="personal-empty route-page-empty"><svg class="empty-route-doodle" viewBox="0 0 230 100" fill="none" aria-hidden="true"><path d="M10 75C25 5 70 110 100 45S160 15 180 55S210 80 220 30" stroke="currentColor" stroke-width="2" stroke-dasharray="6 7"/><circle cx="10" cy="75" r="6" fill="#dc2d1d"/><path d="m207 35 13-5-1 14" stroke="currentColor" stroke-width="2"/></svg><p class="eyebrow">${filtered ? "BİRAZ BAŞKA BİR YERDEN BAK" : "İLK ADIMI SEN AT"}</p><h3>${filtered ? "Bu aramada bir rota bulamadık." : "Henüz çizilmemiş güzel yollar var."}</h3><p>${filtered ? "Aramanı veya şehir filtresini değiştirerek yeniden deneyebilirsin." : "Bir kahve molası, bir müze kapısı, bir sahil yürüyüşü. İlk rotanı birlikte bir araya getirelim."}</p>${filtered ? '<button class="text-button" data-clear-route-filters type="button">Filtreleri temizle ↗</button>' : '<button class="button button-coral" data-new-route type="button">İlk rotamı çiz ↗</button>'}</div>`;
      return;
    }
    routesGrid.innerHTML = routes.map((route, index) => {
      const places = route.places;
      const cities = [...new Set(places.map(place => place.city_name || cityDisplayNames[place.city_slug]).filter(Boolean))].join(" · ");
      const photo = photos[places[0]?.slug] || "/static/photos/galata-sokak.jpg";
      return `<article class="route-card">
        <button class="route-card-photo" data-route-view="${route.id}" type="button" aria-label="${escapeHtml(route.title)} rotasını görüntüle"><img src="${escapeHtml(photo)}" alt="${escapeHtml(places[0]?.name || "Şehir keşfi")}" loading="lazy" /><span class="route-card-number">${String(index + 1).padStart(2, "0")}</span><span class="route-city-badge">${escapeHtml(cities || "Şehir rotası")}</span></button>
        <div class="route-card-body"><div class="route-card-top"><span>SANA AİT BİR PLAN</span><span>${places.length} DURAK</span></div>
        <h3><button data-route-view="${route.id}" type="button">${escapeHtml(route.title)}</button></h3>
        <p class="route-card-note">${escapeHtml(route.notes || "Bu yolculuğa kendi hikâyeni ekle.")}</p>
        ${window.GuideFeatures?.statsMarkup(route.metrics) || ""}
        <ol class="route-places">${places.map((place, placeIndex) => `<li><b>${placeIndex + 1}</b><span>${escapeHtml(place.name)}</span></li>`).join("")}</ol>
        <div class="route-card-actions"><button data-route-view="${route.id}" type="button">Rotayı aç ↗</button><button data-route-edit="${route.id}" type="button">Düzenle</button><button data-route-share="${route.id}" type="button">${route.share_enabled ? "Paylaşımı yönet" : "Paylaş"}</button><button class="route-delete" data-route-delete="${route.id}" type="button">Sil</button></div></div>
      </article>`;
    }).join("");
  }

  async function loadRoutes() {
    if (!state.user) {
      state.routes = [];
      renderRoutes();
      renderProfile();
      return;
    }
    try {
      state.routesError = "";
      const result = await fetchJson("/api/routes");
      state.routes = result.items;
      renderRoutes();
      renderProfile();
    } catch (error) {
      state.routesError = error.message;
      renderRoutes();
      showToast(error.message);
    }
  }

  function profileDate(value) {
    const date = new Date(value + "T12:00:00");
    return Number.isNaN(date.valueOf()) ? "" : date.toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" });
  }

  function renderProfile() {
    $("#profileFavoriteCount").textContent = String(favorites.size);
    $("#profileRouteCount").textContent = String(state.routes.length);
    $("#profileVisitCount").textContent = String(state.journal.length);
    window.GuidePages?.refresh(state, favorites.size);
    profileSection.hidden = !state.user;
    if (!state.user) return;

    const favoriteGrid = $("#profileFavoritesGrid");
    const query = $("#profileFavoriteSearch").value.trim().toLocaleLowerCase("tr-TR");
    const favoritePlaces = [...favorites].map((slug) => state.catalog.find((place) => place.slug === slug)).filter(Boolean)
      .filter(place => !query || [place.name, place.city_name, place.district].join(" ").toLocaleLowerCase("tr-TR").includes(query));
    $("#favoritesListCount").textContent = favoritePlaces.length + " durak · Tüm şehirlerde";
    if (favorites.size && state.catalogStatus === "loading") {
      favoriteGrid.innerHTML = '<div class="profile-empty">Favori durakların yükleniyor…</div>';
    } else if (favoritePlaces.length) {
      favoriteGrid.innerHTML = favoritePlaces.map((place) =>
        '<article class="profile-place-card">' +
          '<div class="profile-place-art">' + placeImage(place) + '</div>' +
          '<div class="profile-place-copy"><p>' + escapeHtml(place.city_name || "Şehir") + ' · ' + escapeHtml(place.district || "") + '</p>' +
            '<h4><button class="profile-item-title" data-profile-open-place="' + escapeHtml(place.slug) + '" type="button">' + escapeHtml(place.name) + '</button></h4>' +
            '<button class="text-button" data-profile-remove-favorite="' + escapeHtml(place.slug) + '" type="button">Favorilerimden çıkar</button>' +
          '</div></article>'
      ).join("");
    } else {
      const message = favorites.size && state.catalogStatus === "error"
        ? "Favoriler yüklenemedi. Sayfayı yenileyip yeniden deneyebilirsin."
        : query ? "Bu aramada bir favori bulamadık. Farklı bir durak veya şehir adı deneyebilirsin."
        : "Henüz bir kalp bırakmadın. Merak ettiğin duraklardaki kalp simgesine dokun; bir gün gideceğin yerler burada biriksin.";
      favoriteGrid.innerHTML = '<div class="profile-empty"><p>' + escapeHtml(message) + '</p><a class="text-link" href="/#places">Durakları keşfet ↗</a></div>';
    }

    const routeGrid = $("#profileRoutesGrid");
    routeGrid.innerHTML = state.routes.length ? state.routes.slice(0, 2).map((route) => {
      const places = route.places || [];
      const cities = [...new Set(places.map((place) => place.city_name || cityDisplayNames[place.city_slug]).filter(Boolean))].join(" · ");
      return '<article class="profile-route-item"><div><p class="profile-item-meta">' +
        places.length + ' DURAK' + (cities ? ' · ' + escapeHtml(cities) : '') + '</p><h4>' +
        escapeHtml(route.title) + '</h4><p class="profile-item-note">' +
        escapeHtml(route.notes || "Kendi şehir keşif planın.") + '</p></div>' +
        '<button class="text-button" data-profile-edit-route="' + Number(route.id) + '" type="button">Rotayı düzenle</button></article>';
    }).join("") : '<div class="profile-empty"><p>Henüz kayıtlı rotan yok. Hazır rotalardan birini ekleyebilir veya yeni bir rota oluşturabilirsin.</p><a class="text-link" href="/#routeTemplates">Hazır rotalara bak ↗</a></div>';

    const journalGrid = $("#profileJournalGrid");
    if (state.journalError) {
      journalGrid.innerHTML = '<div class="profile-empty" role="alert">' + escapeHtml(state.journalError) + '</div>';
    } else if (state.journal.length) {
      journalGrid.innerHTML = state.journal.slice(0, 2).map((entry) =>
        '<article class="profile-journal-item"><div class="profile-item-meta"><time datetime="' + escapeHtml(entry.visited_on) + '">' +
        escapeHtml(profileDate(entry.visited_on)) + '</time><span>' + escapeHtml(entry.city_name || "Şehir") +
        '</span></div><h4><button class="profile-item-title" data-profile-open-place="' + escapeHtml(entry.slug) +
        '" type="button">' + escapeHtml(entry.name) + '</button></h4><p class="profile-item-note">' +
        escapeHtml(entry.notes || "Bugünden küçük bir hatıra.") + '</p><button class="text-button" data-profile-edit-journal="' +
        escapeHtml(entry.slug) + '" type="button">Gezi notunu düzenle</button></article>'
      ).join("");
    } else {
      journalGrid.innerHTML = '<div class="profile-empty"><p>Günlüğünde henüz ziyaret kaydı yok. Bir durağın ayrıntılarından “Ziyaret ettim” seçeneğini kullanabilirsin.</p><a class="text-link" href="/#places">Bir durak keşfet ↗</a></div>';
    }
  }

  function renderRoutePicker() {
    const city = state.routeCity || state.city;
    const places = state.catalog.filter((place) => place.city_slug === city || selectedRouteSlugs.includes(place.slug));
    const options = $("#routePlaceOptions");
    const status = $("#routePickerStatus");
    options.setAttribute("aria-busy", String(state.catalogStatus === "loading"));
    const cityName = ({ istanbul: "İstanbul", ankara: "Ankara", izmir: "İzmir" })[city] || "Bu şehir";
    if (status) {
      status.textContent = state.catalogStatus === "loading" ? "Duraklar yükleniyor…" : state.catalogStatus === "error" ? "Duraklar yüklenemedi. Listeyi yeniden yükleyebilirsin." : state.catalogLegacy ? "Sunucunun önceki sürümü açık. İstanbul durakları kullanılabilir; yeni şehirler ve diğer özellikler için uygulamayı yeniden başlat." : `${cityName} · ${places.length} durak seçilebilir.`;
    }
    options.innerHTML = places.map((place) => `
      <label class="place-option"><input type="checkbox" value="${escapeHtml(place.slug)}" ${selectedRouteSlugs.includes(place.slug) ? "checked" : ""} />
      <span>${escapeHtml(place.name)}</span><small>${escapeHtml(place.city_name || "")} · ${escapeHtml(place.district)}</small></label>`).join("");
    if (!places.length && state.catalogStatus !== "loading") {
      options.innerHTML = `<div class="picker-empty"><p>${state.catalogStatus === "error" ? "Durak listesine ulaşılamadı." : state.catalogLegacy ? "Bu şehrin duraklarını açmak için sunucuyu yeniden başlat." : `${escapeHtml(cityName)} için henüz durak eklenmemiş.`}</p><button class="text-button" data-retry-catalog type="button">${state.catalogStatus === "error" ? "Yeniden dene" : "Listeyi yenile"}</button></div>`;
    } else if (state.catalogStatus === "error") {
      options.insertAdjacentHTML("beforeend", '<button class="text-button picker-retry" data-retry-catalog type="button">Durak listesini yeniden yükle</button>');
    }
    $("#routeForm button[type='submit']").disabled = places.length === 0 || $("#routeForm").dataset.saving === "true";
    renderSelectedOrder();
  }

  function renderSelectedOrder() {
    $("#routeSelectedOrder").innerHTML = selectedRouteSlugs.length
      ? `<p>Gezi sırası · Oklarla düzenleyebilirsin</p>${selectedRouteSlugs.map((slug, index) => {
        const place = state.catalog.find((item) => item.slug === slug);
        return `<div class="selected-order-item"><b>${index + 1}.</b><span>${escapeHtml(place?.name || slug)}</span><button data-move-up="${index}" type="button" aria-label="Yukarı taşı" ${index === 0 ? "disabled" : ""}>↑</button><button data-move-down="${index}" type="button" aria-label="Aşağı taşı" ${index === selectedRouteSlugs.length - 1 ? "disabled" : ""}>↓</button></div>`;
      }).join("")}`
      : "";
    window.GuideFeatures?.selectionChanged([...selectedRouteSlugs]);
  }

  function openRouteDialog(route = null) {
    if (!state.user) return openAuth("login");
    state.routeCity = route?.places?.[0]?.city_slug || state.city;
    $("#routeForm").reset();
    $("#routeCitySelect").value = state.routeCity;
    $("#routeMessage").textContent = "";
    $("#routeId").value = route?.id || "";
    $("#routeName").value = route?.title || "";
    $("#routeNotes").value = route?.notes || "";
    $("#routeDialogTitle").innerHTML = route?.id ? 'Rotayı <em>düzenle.</em>' : 'Yeni <em>rota.</em>';
    selectedRouteSlugs = route ? route.places.map((place) => place.slug) : [];
    renderRoutePicker();
    routeDialog.showModal();
    loadCatalog();
  }

  function renderAdminList() {
    if (state.user?.role !== "admin") return;
    adminList.innerHTML = state.catalog.map((place) => `
      <div class="admin-row"><div><strong>${escapeHtml(place.name)}</strong><small>${escapeHtml(place.district)} · ${escapeHtml(categoryNames.get(place.category_slug) || place.category_slug)}</small></div>
      <div class="admin-row-actions"><button data-admin-edit="${escapeHtml(place.slug)}" type="button">Düzenle</button><button data-admin-delete="${escapeHtml(place.slug)}" type="button">Sil</button></div></div>`).join("");
  }

  function openAdminDialog(place = null) {
    if (state.user?.role !== "admin") return;
    $("#adminForm").reset();
    $("#adminMessage").textContent = "";
    $("#adminOriginalSlug").value = place?.slug || "";
    $("#adminDialogTitle").innerHTML = place ? 'Durağı <em>düzenle.</em>' : 'Yeni <em>durak.</em>';
    const values = {
      adminName: place?.name || "", adminSlug: place?.slug || "", adminCategory: place?.category_slug || state.categories[0]?.slug || "",
      adminDistrict: place?.district || "", adminAddress: place?.address || "", adminSummary: place?.summary || "",
      adminDescription: place?.description || "", adminDuration: place?.duration || "", adminBestFor: place?.best_for || "",
      adminArt: place?.art || "gallery",
    };
    Object.entries(values).forEach(([id, value]) => { $(`#${id}`).value = value; });
    $("#adminFeatured").checked = Boolean(place?.featured);
    window.GuideFeatures?.populateAdmin(place);
    adminDialog.showModal();
  }

  async function refreshPlacesAndFilters() {
    await Promise.all([loadFilters(), loadCatalog(), loadPlaces()]);
    if (state.user) await loadSavedFavorites();
    await loadRoutes();
  }

  categoryChips.addEventListener("click", (event) => {
    const chip = event.target.closest("[data-category]");
    if (!chip) return;
    state.category = chip.dataset.category;
    updateCategorySelection();
    loadPlaces();
  });

  grid.addEventListener("click", (event) => {
    const favorite = event.target.closest("[data-favorite]");
    if (favorite) return toggleFavorite(favorite.dataset.favorite);
    const open = event.target.closest("[data-open]");
    if (open) showDetails(open.dataset.open);
  });

  dialogContent.addEventListener("click", (event) => {
    if (event.target.closest("[data-review-login]")) {
      detailDialog.close();
      openAuth("login");
      return;
    }
    const favorite = event.target.closest("[data-favorite]");
    if (favorite) toggleFavorite(favorite.dataset.favorite);
  });

  dialogContent.addEventListener("submit", async (event) => {
    if (event.target.id !== "reviewForm") return;
    event.preventDefault();
    const form = event.target;
    const message = $("#formMessage", form);
    const values = new FormData(form);
    const payload = {
      rating: Number(values.get("rating")),
      body: String(values.get("body") || "").trim(),
    };
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    message.textContent = "Yorumun ekleniyor…";
    try {
      await fetchJson(`/api/places/${encodeURIComponent(form.dataset.slug)}/reviews`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      message.textContent = "Yorumun eklendi, teşekkürler!";
      showToast("Gezgin notun eklendi.");
      await loadPlaces();
      const result = await fetchJson(`/api/places/${encodeURIComponent(form.dataset.slug)}`);
      renderDetails(result);
    } catch (error) {
      message.textContent = error.message;
      submit.disabled = false;
    }
  });

  $("#accountButton").addEventListener("click", () => {
    if (!state.user) return openAuth("login");
    if (window.GuidePages?.page === "account") window.scrollTo({ top: 0, behavior: "smooth" });
    else window.GuidePages.navigate("account");
  });

  $("#demoLoginButton").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const result = await fetchJson("/api/auth/demo-login", { method: "POST" });
      state.user = result.user;
      state.sessionReady = true;
      await loadSavedFavorites();
      renderAccountUi();
      await loadRoutes();
      window.GuidePages?.afterLogin();
      showToast("Hoş geldin, " + state.user.name.split(" ")[0] + "!");
    } catch (error) {
      showToast(error.message);
    } finally {
      button.disabled = false;
    }
  });

  $("#personalNewRouteButton").addEventListener("click", () => openRouteDialog());
  $("#personalRouteSearch").addEventListener("input", renderRoutes);
  $("#personalRouteCity").addEventListener("change", renderRoutes);
  $("#profileFavoriteSearch").addEventListener("input", renderProfile);
  profileSection.addEventListener("click", async (event) => {
    const target = event.target.closest("button");
    if (!target) return;
    if (target.dataset.profileRemoveFavorite) return toggleFavorite(target.dataset.profileRemoveFavorite);
    if (target.dataset.profileOpenPlace) return showDetails(target.dataset.profileOpenPlace);
    if (target.dataset.profileEditRoute) {
      const route = state.routes.find((item) => item.id === Number(target.dataset.profileEditRoute));
      if (route) openRouteDialog(route);
      return;
    }
    if (target.dataset.profileEditJournal) window.GuideFeatures?.openJournal(target.dataset.profileEditJournal);
  });

  authDialog.querySelector(".auth-tabs").addEventListener("click", (event) => {
    const tab = event.target.closest("[data-auth-mode]");
    if (tab) setAuthMode(tab.dataset.authMode);
  });

  $("#authForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const submit = $("#authSubmit");
    const message = $("#authMessage");
    const payload = { email: $("#authEmail").value.trim(), password: $("#authPassword").value };
    if (authMode === "register") payload.name = $("#authName").value.trim();
    submit.disabled = true;
    message.textContent = "İşlem yapılıyor…";
    try {
      const result = await fetchJson(`/api/auth/${authMode === "register" ? "register" : "login"}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      state.user = result.user;
      state.sessionReady = true;
      await mergeGuestFavorites();
      await loadSavedFavorites();
      renderAccountUi();
      await loadRoutes();
      authDialog.close();
      form.reset();
      window.GuidePages?.afterLogin();
      showToast(`Hoş geldin, ${state.user.name.split(" ")[0]}!`);
    } catch (error) {
      message.textContent = error.message;
    } finally {
      submit.disabled = false;
    }
  });

  $("#logoutButton").addEventListener("click", async () => {
    try {
      await fetchJson("/api/auth/logout", { method: "POST" });
      state.user = null;
      favorites = readFavorites();
      saveFavorites();
      renderPlaces(state.allPlaces);
      renderAccountUi();
      await loadRoutes();
      window.scrollTo({ top: 0, behavior: "smooth" });
      showToast("Çıkış yapıldı.");
    } catch (error) { showToast(error.message); }
  });

  $("#newRouteButton").addEventListener("click", () => openRouteDialog());
  routesGrid.addEventListener("click", async (event) => {
    if (event.target.closest("[data-new-route]")) return openRouteDialog();
    if (event.target.closest("[data-retry-routes]")) return loadRoutes();
    if (event.target.closest("[data-clear-route-filters]")) {
      $("#personalRouteSearch").value = ""; $("#personalRouteCity").value = ""; renderRoutes(); return;
    }
    if (event.target.closest("[data-open-auth]")) return openAuth("login");
    const edit = event.target.closest("[data-route-edit]");
    if (edit) return openRouteDialog(state.routes.find((route) => route.id === Number(edit.dataset.routeEdit)));
    const remove = event.target.closest("[data-route-delete]");
    if (!remove || !window.confirm("Bu rotayı silmek istiyor musun?")) return;
    try {
      await fetchJson(`/api/routes/${Number(remove.dataset.routeDelete)}`, { method: "DELETE" });
      await loadRoutes();
      showToast("Rota silindi.");
    } catch (error) { showToast(error.message); }
  });

  $("#routeCitySelect").addEventListener("change", () => {
    state.routeCity = $("#routeCitySelect").value;
    if (selectedRouteSlugs.length) { selectedRouteSlugs = []; showToast("Yeni şehir için duraklarını seçebilirsin."); }
    renderRoutePicker();
  });

  $("#routePlaceOptions").addEventListener("click", (event) => {
    if (event.target.closest("[data-retry-catalog]")) loadCatalog();
  });

  $("#routePlaceOptions").addEventListener("change", (event) => {
    const checkbox = event.target.closest('input[type="checkbox"]');
    if (!checkbox) return;
    if (checkbox.checked) {
      if (selectedRouteSlugs.length >= 12) {
        checkbox.checked = false;
        showToast("Bir rotada en fazla 12 durak olabilir.");
        return;
      }
      selectedRouteSlugs.push(checkbox.value);
    } else {
      selectedRouteSlugs = selectedRouteSlugs.filter((slug) => slug !== checkbox.value);
    }
    renderSelectedOrder();
  });

  $("#routeSelectedOrder").addEventListener("click", (event) => {
    const up = event.target.closest("[data-move-up]");
    const down = event.target.closest("[data-move-down]");
    if (!up && !down) return;
    const index = Number((up || down).dataset[up ? "moveUp" : "moveDown"]);
    const target = up ? index - 1 : index + 1;
    if (target < 0 || target >= selectedRouteSlugs.length) return;
    [selectedRouteSlugs[index], selectedRouteSlugs[target]] = [selectedRouteSlugs[target], selectedRouteSlugs[index]];
    renderSelectedOrder();
  });

  $("#routeForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    if (form.dataset.saving === "true") return;
    const message = $("#routeMessage");
    if (!selectedRouteSlugs.length) {
      message.textContent = "En az bir durak seç.";
      return;
    }
    const routeId = $("#routeId").value;
    const submit = form.querySelector('button[type="submit"]');
    form.dataset.saving = "true";
    submit.disabled = true;
    message.textContent = "Rota kaydediliyor…";
    try {
      await fetchJson(routeId ? `/api/routes/${routeId}` : "/api/routes", {
        method: routeId ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: $("#routeName").value.trim(), notes: $("#routeNotes").value.trim(), place_slugs: selectedRouteSlugs }),
      });
      routeDialog.close();
      await loadRoutes();
      showToast(routeId ? "Rota güncellendi." : "Rota oluşturuldu.");
      if (window.GuidePages?.page === "home") window.GuidePages.navigate("routes");
    } catch (error) { message.textContent = error.message; }
    finally { delete form.dataset.saving; submit.disabled = false; }
  });

  $("#newPlaceButton").addEventListener("click", () => openAdminDialog());
  adminList.addEventListener("click", async (event) => {
    const edit = event.target.closest("[data-admin-edit]");
    if (edit) return openAdminDialog(state.catalog.find((place) => place.slug === edit.dataset.adminEdit));
    const remove = event.target.closest("[data-admin-delete]");
    if (!remove || !window.confirm("Bu durağı ve bağlı yorum, favori, günlük kayıtları ile rota duraklarını silmek istiyor musun?")) return;
    try {
      await fetchJson(`/api/admin/places/${encodeURIComponent(remove.dataset.adminDelete)}`, { method: "DELETE" });
      await refreshPlacesAndFilters();
      showToast("Durak silindi.");
    } catch (error) { showToast(error.message); }
  });

  $("#adminForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const originalSlug = $("#adminOriginalSlug").value;
    const message = $("#adminMessage");
    const submit = event.target.querySelector('button[type="submit"]');
    const payload = {
      slug: $("#adminSlug").value.trim(), name: $("#adminName").value.trim(),
      category_slug: $("#adminCategory").value, district: $("#adminDistrict").value.trim(),
      address: $("#adminAddress").value.trim(), summary: $("#adminSummary").value.trim(),
      description: $("#adminDescription").value.trim(), duration: $("#adminDuration").value.trim(),
      best_for: $("#adminBestFor").value.trim(), art: $("#adminArt").value, featured: $("#adminFeatured").checked,
      ...(window.GuideFeatures?.adminPayload() || {}),
    };
    submit.disabled = true;
    message.textContent = "Durak kaydediliyor…";
    try {
      await fetchJson(originalSlug ? `/api/admin/places/${encodeURIComponent(originalSlug)}` : "/api/admin/places", {
        method: originalSlug ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      adminDialog.close();
      await refreshPlacesAndFilters();
      showToast(originalSlug ? "Durak güncellendi." : "Durak eklendi.");
    } catch (error) { message.textContent = error.message; }
    finally { submit.disabled = false; }
  });

  document.querySelectorAll("[data-close]").forEach((button) => {
    button.addEventListener("click", () => $(`#${button.dataset.close}`).close());
  });

  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.query = searchInput.value;
      loadPlaces();
    }, 250);
  });

  $("#searchForm").addEventListener("submit", (event) => {
    event.preventDefault();
    clearTimeout(searchTimer);
    state.query = searchInput.value;
    loadPlaces();
  });

  districtSelect.addEventListener("change", () => {
    state.district = districtSelect.value;
    loadPlaces();
  });

  sortSelect.addEventListener("change", () => {
    state.sort = sortSelect.value;
    loadPlaces();
  });

  favoritesToggle.addEventListener("click", () => {
    state.favoritesOnly = !state.favoritesOnly;
    favoritesToggle.classList.toggle("is-active", state.favoritesOnly);
    favoritesToggle.setAttribute("aria-pressed", String(state.favoritesOnly));
    renderPlaces(state.allPlaces);
  });

  $("#clearFilters").addEventListener("click", () => {
    clearTimeout(searchTimer);
    state.query = "";
    state.category = "";
    state.district = "";
    state.favoritesOnly = false;
    state.sort = "popular";
    state.showAll = false;
    searchInput.value = "";
    districtSelect.value = "";
    sortSelect.value = "popular";
    favoritesToggle.classList.remove("is-active");
    favoritesToggle.setAttribute("aria-pressed", "false");
    updateCategorySelection();
    window.GuideFeatures?.resetFilters();
    loadPlaces();
  });

  $("#showAllPlaces").addEventListener("click", () => {
    state.showAll = !state.showAll;
    renderPlaces(state.allPlaces);
  });

  document.addEventListener("error", (event) => {
    if (event.target instanceof HTMLImageElement && event.target.classList.contains("place-photo")) {
      event.target.hidden = true;
    }
  }, true);

  $("#dialogClose").addEventListener("click", () => detailDialog.close());
  detailDialog.addEventListener("click", (event) => {
    if (event.target === detailDialog) detailDialog.close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) {
      event.preventDefault();
      searchInput.focus();
    }
  });

  window.GuideFeatures?.init({ state, escapeHtml, fetchJson, showToast, showDetails, openAuth, openRouteDialog, loadPlaces, loadFilters, loadCatalog, loadRoutes, renderPlaces, renderProfile });
  saveFavorites();
  renderAccountUi();
  Promise.allSettled([loadSession(), loadFilters(), loadCatalog()]).then(async () => {
    await loadPlaces();
  });
})();
