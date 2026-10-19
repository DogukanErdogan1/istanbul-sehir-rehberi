(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  let app;
  let cities = [];
  let templates = [];
  let events = [];
  let journal = [];
  let matchingPlaces = [];
  let discoveryMap, discoveryMarkers, routeMap, routeLayers;
  let selectedSlugs = [];
  let viewedRoute = null;
  let shareRouteId = null;
  let detailPlace = null;
  let pendingTemplate = null;
  let selectedDay = '';
  let estimateTimer;
  let estimateRequest = 0, templateRequest = 0, eventRequest = 0, journalRequest = 0, routeRequest = 0;
  const h = value => app.escapeHtml(value);
  const localDay = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  const niceDate = value => new Date(value + 'T12:00:00').toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' });
  const duration = minutes => `${Math.floor(minutes / 60) ? Math.floor(minutes / 60) + ' sa ' : ''}${minutes % 60 ? minutes % 60 + ' dk' : ''}`.trim() || '0 dk';
  const cityInfo = () => cities.find(city => city.slug === app.state.city) || { name: 'İstanbul', latitude: 41.03, longitude: 28.99, zoom: 12 };
  const safeUrl = value => { try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : '#'; } catch { return '#'; } };

  function statsMarkup(metrics) {
    if (!metrics) return '';
    return `<div class="route-metrics"><span><b>${metrics.distance_km == null ? '—' : Number(metrics.distance_km).toLocaleString('tr-TR', { maximumFractionDigits: 2 }) + ' km'}</b> ${metrics.distance_kind === 'walking' ? 'yürüyüş yolu' : 'kuş uçuşu'}</span><span><b>${h(duration(metrics.visit_minutes || 0))}</b> önerilen ziyaret</span>${metrics.walking_minutes != null ? `<span><b>${h(duration(metrics.walking_minutes))}</b> yürüyüş</span><span><b>${h(duration(metrics.total_minutes))}</b> toplam</span>` : ''}</div>`;
  }
  const fullStats = metrics => statsMarkup(metrics) + `<p class="small-note">${h(metrics.note || '')}</p>`;
  const errorBox = message => `<div class="feature-empty"><p>${h(message)}</p></div>`;

  function mapFactory(id) {
    if (!window.L) return null;
    const city = cityInfo();
    const map = window.L.map(id, { scrollWheelZoom: false }).setView([city.latitude, city.longitude], city.zoom);
    const tiles = window.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> katkıda bulunanlar',
    }).addTo(map);
    tiles.on('tileerror', () => {
      if (id === 'discoveryMap') $('#mapStatus').textContent = 'Harita zemini yüklenemedi. İnternet bağlantını kontrol et; durak noktaları seçilebilir.';
    });
    return map;
  }
  function pin(index) {
    return window.L.divIcon({ className: 'guide-map-pin', html: `<span>${index + 1}</span>`, iconSize: [30, 36], iconAnchor: [15, 36] });
  }
  function fitMap(map, places) {
    if (places.length) map.fitBounds(places.map(place => [place.latitude, place.longitude]), { padding: [35, 35], maxZoom: 15 });
    else { const city = cityInfo(); map.setView([city.latitude, city.longitude], city.zoom); }
  }
  function selectMapPlace(place) {
    const photo = window.GUIDE_PHOTOS?.[place.slug];
    $('#mapPlaceCard').innerHTML = `${photo ? `<img src="${h(photo)}" alt="${h(place.name)}" />` : ''}<p class="eyebrow">${h(place.category_name)}</p><h3>${h(place.name)}</h3><p>${h(place.city_name)} · ${h(place.district)}</p><p>${h(place.summary)}</p><button class="button button-dark" type="button" data-map-place="${h(place.slug)}">Durağı keşfet ↗</button>`;
  }
  function renderMap() {
    if ($('#mapView').hidden) return;
    if (!discoveryMap) {
      discoveryMap = mapFactory('discoveryMap');
      if (!discoveryMap) { $('#mapStatus').textContent = 'Harita başlatılamadı. Kart görünümünü kullanabilirsin.'; return; }
      discoveryMarkers = window.L.layerGroup().addTo(discoveryMap);
    }
    discoveryMarkers.clearLayers();
    const places = matchingPlaces.filter(place => place.latitude != null && place.longitude != null);
    places.forEach((place, index) => window.L.marker([place.latitude, place.longitude], { icon: pin(index) }).addTo(discoveryMarkers).bindTooltip(h(place.name)).on('click', () => selectMapPlace(place)));
    fitMap(discoveryMap, places);
    $('#mapStatus').textContent = `${places.length} durak haritada.${places.length < matchingPlaces.length ? ' Konumu eksik duraklar yalnızca kartlarda gösterilir.' : ''} Noktalar yaklaşık konumlardır; giriş kapısını göstermeyebilir.`;
    $('#resultCount').textContent = `${places.length} durak haritada`;
    $('#showAllPlaces').hidden = true;
    $('#mapPlaceCard').innerHTML = '<p>Haritadaki bir durağı seç.</p>';
    setTimeout(() => discoveryMap.invalidateSize(), 0);
  }
  function placesChanged(places) { matchingPlaces = places; if (app) renderMap(); }

  async function loadCities() {
    cities = await app.fetchJson('/api/cities');
    const options = cities.map(city => `<option value="${h(city.slug)}">${h(city.name)}</option>`).join('');
    for (const id of ['citySelect', 'adminCity', 'eventCity']) { $('#' + id).innerHTML = options; $('#' + id).value = app.state.city; }
    updateHero();
  }
  function updateHero() {
    const city = cityInfo();
    $('#heroCityEyebrow').textContent = `${city.name.toLocaleUpperCase('tr-TR')}${app.state.city === 'ankara' ? "'YI" : "'İ"} YENİDEN GÖR`;
    if (app.state.city === 'istanbul') $('#heroCityEyebrow').textContent = "İSTANBUL'U YENİDEN GÖR";
    const sets = {
      istanbul: ['galata-sokak', 'bogaz-vapuru', 'arkeoloji-salonu', "Galata'dan", 'Boğaz', 'Geçmişle'],
      ankara: ['ankara-kalesi', 'anitkabir', 'anadolu-medeniyetleri-muzesi', "Kale'den", 'Ankara', 'Medeniyetler'],
      izmir: ['izmir-saat-kulesi', 'tarihi-asansor', 'smyrna-agorasi', "Konak'tan", 'İzmir', 'Antik sokaklar'],
    };
    const values = sets[app.state.city] || sets.istanbul;
    ['.photo-galata', '.photo-ferry', '.photo-museum'].forEach((selector, index) => {
      const image = $(selector + ' img');
      if (window.GUIDE_PHOTOS?.[values[index]]) image.src = window.GUIDE_PHOTOS[values[index]];
      image.alt = `${city.name} — ${values[index].replaceAll('-', ' ')}`;
    });
    $('.hero-collage').setAttribute('aria-label', city.name + "'dan bir gezi defteri");
    const captions = {
      istanbul: [["Galata'dan", 'başlayalım.'], ['Boğaz', 'her zaman', 'başka güzel.'], ['Geçmişle', 'bugün arasında', 'bir köprü.']],
      ankara: [["Kale'den", 'başlayalım.'], ['Başkentte', 'her sokak', 'başka güzel.'], ['Geçmişle', 'bugün arasında', 'bir köprü.']],
      izmir: [["Konak'tan", 'başlayalım.'], ['Körfez', 'her zaman', 'başka güzel.'], ['Antik çağdan', 'bugüne kalan', 'bir hikâye.']],
    }[app.state.city];
    ['.galata-note', '.ferry-note', '.museum-note'].forEach((selector, index) => {
      const note = $(selector), arrow = note.querySelector('.note-arrow');
      note.innerHTML = captions[index].map(h).join('<br />');
      if (arrow) note.append(arrow);
    });
  }
  async function changeCity() {
    app.state.city = $('#citySelect').value;
    try { localStorage.setItem('sehir-arasi:city', app.state.city); } catch {}
    app.state.query = app.state.category = app.state.district = '';
    app.state.sort = 'popular'; app.state.favoritesOnly = false; app.state.showAll = false;
    $('#searchInput').value = ''; $('#sortSelect').value = 'popular';
    $('#favoritesToggle').classList.remove('is-active'); $('#favoritesToggle').setAttribute('aria-pressed', 'false');
    resetFilters(); updateHero(); selectedDay = '';
    await Promise.allSettled([app.loadFilters(), app.loadPlaces(), loadTemplates(), loadEvents()]);
    renderJournal();
  }
  function resetFilters() {
    app.state.indoor = app.state.family = app.state.accessible = false;
    for (const id of ['indoorFilter', 'familyFilter', 'accessibleFilter']) $('#' + id).checked = false;
  }

  async function loadTemplates() {
    const request = ++templateRequest;
    try {
      const result = await app.fetchJson('/api/route-templates?city=' + encodeURIComponent(app.state.city));
      if (request !== templateRequest) return;
      templates = result.items;
      $('#templatesGrid').innerHTML = templates.length ? templates.map(route => {
        const photo = window.GUIDE_PHOTOS?.[route.places[0]?.slug];
        return `<article class="template-card">${photo ? `<img src="${h(photo)}" alt="${h(route.places[0].name)}" loading="lazy" />` : ''}<div class="template-content"><p class="eyebrow">${h(route.theme || 'ŞEHİR ROTASI')} · ${route.places.length} DURAK</p><h3>${h(route.title)}</h3><p>${h(route.description)}</p>${statsMarkup(route.metrics)}<div class="feature-actions"><button class="text-button" type="button" data-template-view="${h(route.slug)}">Rotayı incele ↗</button><button class="text-button" type="button" data-template-copy="${h(route.slug)}">Kendime ekle +</button></div></div></article>`;
      }).join('') : errorBox('Bu şehir için henüz hazır rota yok. Kendi rotanı oluşturabilirsin.');
    } catch (error) { if (request === templateRequest) $('#templatesGrid').innerHTML = errorBox(error.message); }
  }
  function copyRoute(route) {
    if (!app.state.user) { pendingTemplate = route; app.openAuth('login'); return; }
    $('#routeViewDialog').close();
    app.openRouteDialog({ title: route.title, notes: route.description || '', places: route.places });
  }
  function drawRouteMap(route) {
    if (!window.L) return;
    if (!routeMap) { routeMap = mapFactory('routeViewMap'); routeLayers = window.L.layerGroup().addTo(routeMap); }
    routeLayers.clearLayers();
    const places = route.places.filter(place => place.latitude != null && place.longitude != null);
    places.forEach((place, index) => window.L.marker([place.latitude, place.longitude], { icon: pin(index) }).addTo(routeLayers).bindTooltip(h(place.name)));
    const geometry = route.metrics?.geometry || [];
    if (geometry.length > 1) window.L.polyline(geometry.map(pair => [pair[1], pair[0]]), { color: '#dc2d1d', weight: 3, dashArray: route.metrics.distance_kind === 'walking' ? null : '7 8' }).addTo(routeLayers);
    fitMap(routeMap, places);
    setTimeout(() => { routeMap.invalidateSize(); fitMap(routeMap, places); }, 0);
  }
  function openRouteView(route, shared = false) {
    routeRequest++;
    viewedRoute = route;
    $('#routeViewTitle').textContent = route.title;
    $('#routeViewEyebrow').textContent = shared ? 'PAYLAŞILAN GEZİ PLANI' : 'GEZİ PLANI';
    $('#routeViewDescription').textContent = route.description || route.notes || '';
    $('#routeViewStats').innerHTML = fullStats(route.metrics);
    $('#routeViewStops').innerHTML = route.places.map((place, index) => `<li><span>${index + 1}</span><div><button type="button" class="text-button" data-view-stop="${h(place.slug)}">${h(place.name)} ↗</button><small>${h(place.district)} · ${h(duration(place.visit_minutes || 90))} ziyaret</small></div></li>`).join('');
    $('#routeViewCopy').hidden = Boolean(route.id);
    $('#routeViewWalking').disabled = route.places.length < 2;
    $('#routeViewDialog').showModal();
    drawRouteMap(route);
  }
  async function calculate(slugs, walking) {
    return app.fetchJson('/api/route-estimate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ place_slugs: slugs, walking }) });
  }
  function selectionChanged(slugs) {
    selectedSlugs = slugs;
    clearTimeout(estimateTimer);
    const request = ++estimateRequest;
    $('#estimateWalkingButton').disabled = slugs.length < 2;
    if (!slugs.length) { $('#routeEstimate').innerHTML = '<p class="small-note">Süre ve mesafe için durak seç.</p>'; return; }
    $('#routeEstimate').textContent = 'Plan hesaplanıyor…';
    estimateTimer = setTimeout(async () => {
      try { const metrics = await calculate(slugs, false); if (request === estimateRequest) $('#routeEstimate').innerHTML = fullStats(metrics); }
      catch (error) { if (request === estimateRequest) $('#routeEstimate').textContent = error.message; }
    }, 180);
  }
  async function shareRoute(id) {
    try {
      const result = await app.fetchJson(`/api/routes/${id}/share`, { method: 'POST' });
      shareRouteId = id;
      $('#shareUrl').value = new URL(result.path, location.origin).href;
      $('#shareMessage').textContent = '';
      $('#shareHint').textContent = ['127.0.0.1', 'localhost'].includes(location.hostname) ? 'Bu sunucu bilgisayarında yerel olarak çalışıyor. Bağlantı başka cihazlardan ancak sunucu o cihazlara erişilebilir olduğunda açılır.' : 'Paylaşımı kapattığında bu bağlantı çalışmaz.';
      $('#shareDialog').showModal();
      await app.loadRoutes();
    } catch (error) { app.showToast(error.message); }
  }

  function detailsChanged(place) {
    detailPlace = place;
    $('#detailExtras')?.remove();
    const extra = document.createElement('section'); extra.id = 'detailExtras'; extra.className = 'detail-extras';
    const entry = journal.find(item => item.slug === place.slug);
    const access = place.wheelchair_accessible === true ? 'Sandalye erişimi: doğrulandı' : place.wheelchair_accessible === false ? 'Sandalye erişimi: uygun değil' : 'Sandalye erişimi: doğrulanmadı';
    extra.innerHTML = `<h3>Ziyaretini planla.</h3><div class="place-tags"><span>${h(access)}</span>${place.indoor != null ? `<span>${place.indoor ? 'Kapalı mekân' : 'Açık alan'}</span>` : '<span>Kapalı / açık alan: karma veya bilinmiyor</span>'}${place.family_friendly ? '<span>Çocukla gezi önerisi</span>' : ''}</div><p class="small-note">${h(place.accessibility_note || 'Erişim bilgisi henüz doğrulanmadı.')} Konum yaklaşık olabilir; giriş kapısı farklı olabilir.</p>${place.source_url ? `<a class="text-link" href="${h(safeUrl(place.source_url))}" target="_blank" rel="noopener">Kurumun bilgi sayfası ↗</a>` : ''}<div class="visit-journal-action"><button class="button button-dark" data-journal-place="${h(place.slug)}" type="button">${entry ? 'Gezi notumu düzenle' : 'Ziyaret ettim · Günlüğüme ekle'}</button><span class="small-note">${entry ? h(niceDate(entry.visited_on)) + ' tarihinde gezdin.' : 'Tarih ve notların sadece sana görünür.'}</span></div>`;
    $('#dialogContent').append(extra);
  }
  async function loadJournal() {
    const request = ++journalRequest;
    if (!app.state.user) { journal = []; renderJournal(); if (detailPlace && $('#detailDialog').open) detailsChanged(detailPlace); return; }
    try {
      const result = await app.fetchJson('/api/journal');
      if (request !== journalRequest) return;
      journal = result.items; renderJournal();
      if (detailPlace && $('#detailDialog').open) detailsChanged(detailPlace);
    } catch (error) { if (request === journalRequest) $('#journalGrid').innerHTML = errorBox(error.message); }
  }
  function renderJournal() {
    if (!app) return;
    const entries = journal.filter(item => item.city_slug === app.state.city);
    $('#journalCount').textContent = app.state.user ? `${entries.length} ziyaret · Tüm şehirlerde ${journal.length}` : '';
    if (!app.state.user) { $('#journalGrid').innerHTML = '<div class="feature-empty"><h3>Senin şehrin, senin hikâyen.</h3><p>Ziyaretlerini ve özel notlarını saklamak için giriş yap.</p><button class="text-button" data-feature-login type="button">Giriş yap ↗</button></div>'; return; }
    $('#journalGrid').innerHTML = entries.length ? entries.map(entry => `<article class="journal-card"><time datetime="${h(entry.visited_on)}">${h(niceDate(entry.visited_on))}</time><h3><button class="text-button" data-journal-detail="${h(entry.slug)}" type="button">${h(entry.name)} ↗</button></h3><p class="journal-note">${h(entry.notes || 'Bugünden küçük bir hatıra.')}</p><button class="text-button" data-journal-place="${h(entry.slug)}" type="button">Notumu düzenle</button></article>`).join('') : errorBox('Bu şehirde henüz ziyaret kaydın yok. Bir durak açıp “Ziyaret ettim” düğmesine bas.');
  }
  function openJournal(slug) {
    if (!app.state.user) { app.openAuth('login'); return; }
    const place = app.state.catalog.find(item => item.slug === slug) || detailPlace;
    const entry = journal.find(item => item.slug === slug);
    $('#journalSlug').value = slug; $('#journalPlaceName').textContent = place?.name || slug;
    $('#journalDate').max = localDay(); $('#journalDate').value = entry?.visited_on || localDay();
    $('#journalNotes').value = entry?.notes || ''; $('#journalMessage').textContent = '';
    $('#removeJournalButton').hidden = !entry;
    $('#journalDialog').showModal();
  }

  async function loadEvents() {
    const request = ++eventRequest;
    const month = $('#eventMonth').value || localDay().slice(0, 7);
    $('#eventMonth').value = month;
    const [year, index] = month.split('-').map(Number);
    const last = new Date(year, index, 0).getDate();
    const params = new URLSearchParams({ city: app.state.city, start: month + '-01', end: month + '-' + last, include_past: String(Boolean($('#pastEvents').checked)) });
    try {
      const result = await app.fetchJson('/api/events?' + params);
      if (request !== eventRequest) return;
      events = result.items;
      renderCalendar(); renderEvents();
    } catch (error) { if (request === eventRequest) { events = []; $('#eventsGrid').innerHTML = errorBox(error.message); renderCalendar(); } }
  }
  function renderCalendar() {
    const month = $('#eventMonth').value;
    const [year, index] = month.split('-').map(Number);
    const offset = (new Date(year, index - 1, 1).getDay() + 6) % 7;
    const last = new Date(year, index, 0).getDate();
    let markup = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'].map(day => `<span class="calendar-weekday">${day}</span>`).join('');
    markup += '<span></span>'.repeat(offset);
    for (let day = 1; day <= last; day++) {
      const key = month + '-' + String(day).padStart(2, '0');
      const count = events.filter(event => event.start_date <= key && event.end_date >= key).length;
      markup += `<button type="button" class="calendar-day${count ? ' has-events' : ''}${key === localDay() ? ' is-today' : ''}" data-event-day="${key}" aria-pressed="${key === selectedDay}" aria-label="${h(niceDate(key))}, ${count} etkinlik">${day}${count ? `<small>${count}</small>` : ''}</button>`;
    }
    $('#eventCalendar').innerHTML = markup;
    $('#clearEventDay').hidden = !selectedDay;
  }
  function renderEvents() {
    const visible = selectedDay ? events.filter(event => event.start_date <= selectedDay && event.end_date >= selectedDay) : events;
    $('#eventsGrid').innerHTML = visible.length ? visible.map(event => `<article class="event-card"><div class="event-dates"><time datetime="${h(event.start_date)}">${h(niceDate(event.start_date))}</time> — <time datetime="${h(event.end_date)}">${h(niceDate(event.end_date))}</time>${event.end_date < localDay() ? ' · Sona erdi' : ''}</div><h3>${h(event.title)}</h3>${event.place_name ? `<button class="text-button" data-event-place="${h(event.place_slug)}" type="button">${h(event.place_name)} ↗</button>` : ''}<p>${h(event.description)}</p><a class="text-link" href="${h(safeUrl(event.source_url))}" target="_blank" rel="noopener">${h(event.source_name)} · Resmî kaynak ↗</a><p class="small-note">Kaynak kontrolü: ${h(niceDate(event.verified_on))}</p>${app.state.user?.role === 'admin' ? `<div class="feature-actions"><button class="text-button" data-event-edit="${event.id}" type="button">Düzenle</button><button class="text-button" data-event-delete="${event.id}" type="button">Sil</button></div>` : ''}</article>`).join('') : errorBox(selectedDay ? 'Bu gün için doğrulanmış etkinlik bulunamadı. Ayın tamamını görüntüleyebilirsin.' : 'Seçili şehir ve ay için doğrulanmış etkinlik bulunamadı. Başka bir ay seçebilir veya geçmiş etkinlikleri açabilirsin.');
  }
  function populateEventPlaces(value = '') {
    $('#eventPlace').innerHTML = '<option value="">Bağımsız etkinlik</option>' + app.state.catalog.filter(place => place.city_slug === $('#eventCity').value).map(place => `<option value="${h(place.slug)}">${h(place.name)}</option>`).join('');
    $('#eventPlace').value = value;
  }
  function openEvent(event = null) {
    if (app.state.user?.role !== 'admin') return;
    $('#eventForm').reset(); $('#eventMessage').textContent = '';
    const values = { eventId: event?.id || '', eventTitle: event?.title || '', eventSlug: event?.slug || '', eventCity: event?.city_slug || app.state.city,
      eventStart: event?.start_date || localDay(), eventEnd: event?.end_date || localDay(), eventDescription: event?.description || '', eventSourceName: event?.source_name || '', eventSourceUrl: event?.source_url || '', eventVerified: event?.verified_on || localDay() };
    Object.entries(values).forEach(([id, value]) => { $('#' + id).value = value; });
    $('#eventVerified').max = localDay(); populateEventPlaces(event?.place_slug || '');
    $('#eventDialogTitle').textContent = event ? 'Etkinliği düzenle.' : 'Yeni etkinlik.';
    $('#eventDialog').showModal();
  }
  function populateAdmin(place) {
    $('#adminCity').value = place?.city_slug || app.state.city;
    $('#adminVisitMinutes').value = place?.visit_minutes || 90;
    $('#adminLatitude').value = place?.latitude ?? ''; $('#adminLongitude').value = place?.longitude ?? '';
    for (const [id, key] of [['adminIndoor', 'indoor'], ['adminFamily', 'family_friendly'], ['adminAccessible', 'wheelchair_accessible']]) $('#' + id).value = place?.[key] == null ? '' : String(place[key]);
    $('#adminSource').value = place?.source_url || ''; $('#adminAccessNote').value = place?.accessibility_note || '';
  }
  function adminPayload() {
    const bool = id => $('#' + id).value === '' ? null : $('#' + id).value === 'true';
    const number = id => $('#' + id).value === '' ? null : Number($('#' + id).value);
    return { city_slug: $('#adminCity').value, latitude: number('adminLatitude'), longitude: number('adminLongitude'), visit_minutes: Number($('#adminVisitMinutes').value), indoor: bool('adminIndoor'), family_friendly: bool('adminFamily'), wheelchair_accessible: bool('adminAccessible'), accessibility_note: $('#adminAccessNote').value.trim(), source_url: $('#adminSource').value.trim() };
  }
  function sessionChanged() {
    if (!app) return;
    $('#newEventButton').hidden = app.state.user?.role !== 'admin';
    loadJournal(); renderEvents();
    if (app.state.user && pendingTemplate) { const route = pendingTemplate; pendingTemplate = null; copyRoute(route); }
  }

  function init(api) {
    app = api;
    try { const city = localStorage.getItem('sehir-arasi:city'); if (['istanbul', 'ankara', 'izmir'].includes(city)) app.state.city = city; } catch {}
    $('#citySelect').value = app.state.city;
    $('#eventMonth').value = localDay().slice(0, 7);
    $('#citySelect').addEventListener('change', changeCity);
    for (const [id, field] of [['indoorFilter', 'indoor'], ['familyFilter', 'family'], ['accessibleFilter', 'accessible']]) $('#' + id).addEventListener('change', () => { app.state[field] = $('#' + id).checked; app.loadPlaces(); });
    $('#mapViewButton').addEventListener('click', () => { $('#mapView').hidden = false; $('#placeGrid').hidden = true; $('#mapViewButton').setAttribute('aria-pressed', 'true'); $('#listViewButton').setAttribute('aria-pressed', 'false'); renderMap(); });
    $('#listViewButton').addEventListener('click', () => { $('#mapView').hidden = true; $('#placeGrid').hidden = false; $('#mapViewButton').setAttribute('aria-pressed', 'false'); $('#listViewButton').setAttribute('aria-pressed', 'true'); app.renderPlaces(app.state.allPlaces); });
    $('#estimateWalkingButton').addEventListener('click', async () => {
      clearTimeout(estimateTimer); const request = ++estimateRequest; $('#estimateWalkingButton').disabled = true;
      $('#routeEstimate').textContent = 'Yürünebilir yol hesaplanıyor…';
      try { const metrics = await calculate([...selectedSlugs], true); if (request === estimateRequest) $('#routeEstimate').innerHTML = fullStats(metrics); }
      catch (error) { if (request === estimateRequest) $('#routeEstimate').textContent = error.message; }
      finally { if (request === estimateRequest) $('#estimateWalkingButton').disabled = selectedSlugs.length < 2; }
    });
    $('#routeViewWalking').addEventListener('click', async () => {
      if (!viewedRoute) return; const request = ++routeRequest; $('#routeViewWalking').disabled = true;
      $('#routeViewStats').textContent = 'Yürünebilir yol hesaplanıyor…';
      try { const metrics = await calculate(viewedRoute.places.map(place => place.slug), true); if (request === routeRequest) { viewedRoute.metrics = metrics; $('#routeViewStats').innerHTML = fullStats(metrics); drawRouteMap(viewedRoute); } }
      catch (error) { if (request === routeRequest) $('#routeViewStats').textContent = error.message; }
      finally { if (request === routeRequest) $('#routeViewWalking').disabled = viewedRoute.places.length < 2; }
    });
    $('#routeViewCopy').addEventListener('click', () => { if (viewedRoute) copyRoute(viewedRoute); });
    $('#copyShareButton').addEventListener('click', async () => {
      try { await navigator.clipboard.writeText($('#shareUrl').value); $('#shareMessage').textContent = 'Bağlantı kopyalandı.'; }
      catch { $('#shareUrl').focus(); $('#shareUrl').select(); $('#shareMessage').textContent = 'Bağlantı seçildi. Ctrl+C ile kopyalayabilirsin.'; }
    });
    $('#revokeShareButton').addEventListener('click', async () => {
      if (!shareRouteId) return;
      try { await app.fetchJson(`/api/routes/${shareRouteId}/share`, { method: 'DELETE' }); $('#shareDialog').close(); app.showToast('Rota paylaşımı kapatıldı.'); await app.loadRoutes(); }
      catch (error) { $('#shareMessage').textContent = error.message; }
    });
    $('#journalForm').addEventListener('submit', async event => {
      event.preventDefault(); const button = $('#journalForm button[type="submit"]'); button.disabled = true;
      try { await app.fetchJson('/api/journal/' + encodeURIComponent($('#journalSlug').value), { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ visited_on: $('#journalDate').value, notes: $('#journalNotes').value }) }); $('#journalDialog').close(); await loadJournal(); app.showToast('Gezi notun kaydedildi.'); }
      catch (error) { $('#journalMessage').textContent = error.message; }
      finally { button.disabled = false; }
    });
    $('#removeJournalButton').addEventListener('click', async () => {
      if (!confirm('Bu özel gezi notunu silmek istiyor musun?')) return;
      try { await app.fetchJson('/api/journal/' + encodeURIComponent($('#journalSlug').value), { method: 'DELETE' }); $('#journalDialog').close(); await loadJournal(); app.showToast('Gezi notu silindi.'); }
      catch (error) { $('#journalMessage').textContent = error.message; }
    });
    $('#eventMonth').addEventListener('change', () => { selectedDay = ''; loadEvents(); });
    $('#pastEvents').addEventListener('change', () => { selectedDay = ''; loadEvents(); });
    $('#clearEventDay').addEventListener('click', () => { selectedDay = ''; renderCalendar(); renderEvents(); });
    $('#newEventButton').addEventListener('click', () => openEvent());
    $('#eventCity').addEventListener('change', () => populateEventPlaces());
    $('#eventForm').addEventListener('submit', async event => {
      event.preventDefault(); const button = $('#eventForm button[type="submit"]'); button.disabled = true;
      const payload = { slug: $('#eventSlug').value, title: $('#eventTitle').value, city_slug: $('#eventCity').value, place_slug: $('#eventPlace').value || null, start_date: $('#eventStart').value, end_date: $('#eventEnd').value, description: $('#eventDescription').value, source_url: $('#eventSourceUrl').value, source_name: $('#eventSourceName').value, verified_on: $('#eventVerified').value };
      try { await app.fetchJson('/api/admin/events' + ($('#eventId').value ? '/' + $('#eventId').value : ''), { method: $('#eventId').value ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); $('#eventDialog').close(); await loadEvents(); app.showToast('Etkinlik kaydedildi.'); }
      catch (error) { $('#eventMessage').textContent = error.message; }
      finally { button.disabled = false; }
    });
    document.addEventListener('click', async event => {
      const target = event.target.closest('button'); if (!target) return;
      if (target.hasAttribute('data-feature-login')) app.openAuth('login');
      if (target.dataset.mapPlace) app.showDetails(target.dataset.mapPlace);
      if (target.dataset.journalDetail) app.showDetails(target.dataset.journalDetail);
      if (target.dataset.journalPlace) openJournal(target.dataset.journalPlace);
      if (target.dataset.eventPlace) app.showDetails(target.dataset.eventPlace);
      if (target.dataset.viewStop) { $('#routeViewDialog').close(); app.showDetails(target.dataset.viewStop); }
      if (target.dataset.templateView) { const route = templates.find(item => item.slug === target.dataset.templateView); if (route) openRouteView(route); }
      if (target.dataset.templateCopy) { const route = templates.find(item => item.slug === target.dataset.templateCopy); if (route) copyRoute(route); }
      if (target.dataset.routeView) { const route = app.state.routes.find(item => item.id === Number(target.dataset.routeView)); if (route) openRouteView(route); }
      if (target.dataset.routeShare) shareRoute(Number(target.dataset.routeShare));
      if (target.dataset.eventDay) { selectedDay = target.dataset.eventDay; renderCalendar(); renderEvents(); }
      if (target.dataset.eventEdit) openEvent(events.find(item => item.id === Number(target.dataset.eventEdit)));
      if (target.dataset.eventDelete && confirm('Bu etkinliği silmek istiyor musun?')) {
        try { await app.fetchJson('/api/admin/events/' + target.dataset.eventDelete, { method: 'DELETE' }); await loadEvents(); }
        catch (error) { app.showToast(error.message); }
      }
    });
    Promise.allSettled([loadCities(), loadTemplates(), loadEvents()]).then(results => { if (results[0].status === 'rejected') app.showToast('Şehirler yüklenemedi. Sunucuyu yeniden başlatıp sayfayı yenile.'); });
    const match = location.pathname.match(/^\/r\/([A-Za-z0-9_-]{20,64})\/?$/);
    if (match) app.fetchJson('/api/shared-routes/' + match[1]).then(route => openRouteView(route, true)).catch(error => { $('#routeViewTitle').textContent = 'Rota açılamadı.'; $('#routeViewDescription').textContent = error.message; $('#routeViewStats').innerHTML = ''; $('#routeViewStops').innerHTML = ''; $('#routeViewWalking').disabled = true; $('#routeViewCopy').hidden = true; $('#routeViewDialog').showModal(); });
  }
  window.GuideFeatures = { init, statsMarkup, placesChanged, detailsChanged, sessionChanged, selectionChanged, populateAdmin, adminPayload, resetFilters };
})();
