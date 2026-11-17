(() => {
  "use strict";
  const I18N = window.GuideI18n || { language: "tr", text: v => v, locale: () => "tr-TR", link: v => v, fold: v => String(v).toLocaleLowerCase("tr-TR"), html: (parts, ...values) => parts.reduce((out, part, index) => out + part + (index < values.length ? values[index] : ""), "") };
  const $ = selector => document.querySelector(selector);
  let app, result = null;
  let request = 0, phase = null, dirty = false, pendingResume = false, opened = false;
  const h = value => app.escapeHtml(value);
  const duration = minutes => (Math.floor(minutes / 60) ? Math.floor(minutes / 60) + I18N.text(" sa ") : "") + (minutes % 60 ? minutes % 60 + I18N.text(" dk") : minutes ? "" : I18N.text("0 dk"));
  const safeUrl = value => { try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) ? url.href : ""; } catch { return ""; } };

  function status(message = "", error = false) {
    $("#plannerStatus").textContent = message;
    $("#plannerStatus").dataset.error = String(error);
  }

  function actions() {
    const saved = Boolean(result?.saved_route_id);
    $("#plannerSave").hidden = saved && !dirty;
    $("#plannerSave").disabled = !result || Boolean(phase) || dirty || !app.state.sessionReady;
    $("#plannerMap").disabled = !result || Boolean(phase) || dirty;
    $("#plannerSavedLink").hidden = !saved || dirty;
    $("#plannerRouteTitle").readOnly = saved;
    $("#plannerRouteTitle").disabled = Boolean(phase);
    $("#plannerSave").textContent = phase === "saving" ? I18N.text("Kaydediliyor…") : dirty ? I18N.text("Önce planı güncelle") : !app.state.sessionReady ? I18N.text("Oturum kontrol ediliyor…") : app.state.user ? I18N.text("Rotalarıma kaydet +") : I18N.text("Kaydetmek için giriş yap");
  }

  function setPhase(value) {
    phase = value;
    $("#dayPlannerForm").setAttribute("aria-busy", String(Boolean(value)));
    document.querySelectorAll("#dayPlannerForm input, #dayPlannerForm select, #dayPlannerForm button").forEach(node => { node.disabled = Boolean(value); });
    $("#plannerGenerate").textContent = value === "generating" ? I18N.text("Günün planlanıyor…") : I18N.text("Günümü planla ↗");
    actions();
  }

  function render() {
    const summary = result.summary;
    $("#plannerResultTitle").textContent = result.route.title;
    $("#plannerResultWindow").textContent = summary.start_time + " – " + summary.end_time + I18N.text(" · Tahmini gezi aralığın");
    $("#plannerSummary").innerHTML = I18N.html`<div><strong>${summary.stop_count}</strong><span>güzel durak</span></div><div><strong>${h(duration(summary.total_minutes))}</strong><span>tahmini plan süresi</span></div><div><strong>${h(duration(summary.free_minutes))}</strong><span>serbest zaman</span></div>`;
    $("#plannerTimingNote").textContent = duration(summary.visit_minutes) + I18N.text(" ziyaret · ") + duration(summary.estimated_transfer_minutes) + I18N.text(" tahmini geçiş · ") + duration(summary.break_minutes) + I18N.text(" mola");
    $("#plannerTimeline").innerHTML = result.schedule.map(entry => {
      const source = safeUrl(entry.source_url);
      return `<li data-kind="${h(entry.kind)}"><time datetime="${h(entry.start)}">${h(entry.start)} – ${h(entry.end)} · ${h(duration(entry.minutes))}</time><h4>${entry.kind === "visit" ? `<button type="button" data-plan-stop="${h(entry.place_slug)}">${h(entry.title)}</button>` : h(entry.title)}</h4><p>${h(entry.description)}</p>${source ? I18N.html`<a href="${h(source)}" target="_blank" rel="noopener">Resmî bilgi ↗</a>` : ""}</li>`;
    }).join("");
    $("#plannerNotes").innerHTML = result.notes.map(note => "<li>" + h(note) + "</li>").join("");
    $("#plannerRouteTitle").value = result.route.title;
    $("#plannerPlaceholder").hidden = true;
    $("#plannerResult").hidden = false;
    actions();
  }

  function open() {
    if (!opened) { $("#plannerCity").value = app.state.city || "istanbul"; opened = true; }
    if (!$("#dayPlannerDialog").open) $("#dayPlannerDialog").showModal();
    actions();
  }

  function preferences() {
    const interests = [...document.querySelectorAll('input[name="plannerInterest"]:checked')].map(input => input.value);
    const start = $("#plannerStart").value;
    const available = Number($("#plannerDuration").value);
    const pause = Number($("#plannerBreak").value);
    if (!interests.length) throw new Error(I18N.text("En az bir ilgi alanı seç."));
    if (!/^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/.test(start)) throw new Error(I18N.text("Geçerli bir başlangıç saati seç."));
    const [hours, minutes] = start.split(":").map(Number);
    if (hours * 60 + minutes + available >= 1440) throw new Error(I18N.text("Plan aynı gün içinde bitmeli. Başlangıç saatini veya süreyi değiştir."));
    if (pause >= available) throw new Error(I18N.text("Mola süresi ayırdığın toplam süreden kısa olmalı."));
    return { city: $("#plannerCity").value, available_minutes: available, start_time: start, interests,
      pace: $("#plannerPace").value, break_minutes: pause, indoor_only: $("#plannerIndoor").checked,
      family_friendly: $("#plannerFamily").checked, accessible_only: $("#plannerAccessible").checked };
  }

  async function generate(event) {
    event.preventDefault();
    if (phase) return;
    let payload;
    try { payload = preferences(); } catch (error) { status(error.message, true); return; }
    const token = ++request;
    result = null; dirty = false; pendingResume = false;
    $("#plannerResult").hidden = true;
    $("#plannerPlaceholder").hidden = false;
    setPhase("generating");
    status(I18N.text("Merakına ve vaktine göre yakın durakları bir araya getiriyoruz…"));
    try {
      const data = await app.fetchJson("/api/day-plans", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (token !== request) return;
      if (data.status !== "ready") { status(data.message, true); return; }
      result = data;
      render();
      status(data.message);
    } catch (error) { if (token === request) status(error.message, true); }
    finally { if (token === request) setPhase(null); }
  }

  async function save() {
    if (!result || phase || dirty || result.saved_route_id || !app.state.sessionReady) return;
    const title = $("#plannerRouteTitle").value.trim();
    if (title.length < 3 || title.length > 70) { status(I18N.text("Rota adı 3–70 karakter olmalı."), true); return; }
    if (!app.state.user) {
      pendingResume = true;
      $("#dayPlannerDialog").close();
      app.openAuth("login");
      return;
    }
    const snapshot = result;
    setPhase("saving"); status(I18N.text("Planın rotalarına kaydediliyor…"));
    try {
      const route = await app.fetchJson("/api/routes", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, notes: snapshot.route.notes, place_slugs: snapshot.route.places.map(place => place.slug) }) });
      snapshot.saved_route_id = route.id;
      snapshot.route.title = title;
      if (result === snapshot) { $("#plannerResultTitle").textContent = title; status(I18N.text("Planın rotalarına kaydedildi. Rotalarım sayfasından düzenleyebilir ve bütçesini oluşturabilirsin.")); actions(); }
      await app.loadRoutes();
    } catch (error) { if (result === snapshot) status(error.message, true); }
    finally { if (phase === "saving") setPhase(null); }
  }

  function afterLogin() {
    if (!pendingResume || !result || dirty || !app.state.user) return false;
    pendingResume = false;
    open();
    status(I18N.text("Planın burada seni bekliyor. Şimdi rotalarına kaydedebilirsin."));
    return true;
  }

  function init(api) {
    app = api;
    $("#dayPlannerForm").addEventListener("submit", generate);
    const changed = () => { pendingResume = false; if (result) { dirty = true; status(I18N.text("Tercihlerini değiştirdin. Yeni planını oluşturduktan sonra kaydedebilirsin.")); actions(); } else status(); };
    $("#dayPlannerForm").addEventListener("input", changed);
    $("#dayPlannerForm").addEventListener("change", changed);
    $("#dayPlannerDialog").addEventListener("close", () => { if (phase === "generating") { request++; setPhase(null); status(); } });
    $("#plannerSave").addEventListener("click", save);
    $("#plannerMap").addEventListener("click", () => {
      if (!result || phase || dirty) return;
      if (!window.GuideFeatures?.previewRoute) { status(I18N.text("Harita şu anda açılamadı. Sayfayı yenileyerek yeniden deneyebilirsin."), true); return; }
      $("#dayPlannerDialog").close();
      window.GuideFeatures.previewRoute(result.route);
    });
    document.addEventListener("click", event => {
      const button = event.target.closest("button"); if (!button) return;
      if (button.hasAttribute("data-open-day-planner")) open();
      if (button.dataset.planStop && result && !phase && !dirty) { $("#dayPlannerDialog").close(); app.showDetails(button.dataset.planStop); }
    });
  }
  window.GuidePlanner = Object.freeze({ init, afterLogin, sessionChanged: () => { if (app) actions(); } });
})();
