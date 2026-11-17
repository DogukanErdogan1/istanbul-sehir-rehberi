(() => {
  "use strict";
  const $ = selector => document.querySelector(selector);
  const duration = minutes => (Math.floor(minutes / 60) ? Math.floor(minutes / 60) + " sa " : "") + (minutes % 60 ? minutes % 60 + " dk" : minutes ? "" : "0 dk");
  let app, data = null, routeId = null, generation = 0, busy = false, needsReload = false;
  const h = value => app.escapeHtml(value);

  function status(message = "", error = false) {
    $("#tripStatus").textContent = message;
    $("#tripStatus").dataset.error = String(error);
  }

  function setBusy(value) {
    busy = value;
    const locked = value || needsReload || !data;
    $("#tripData").setAttribute("aria-busy", String(value));
    document.querySelectorAll("#tripData button").forEach(button => { button.disabled = locked; });
    $("#tripRetry").disabled = value;
    $("#tripDirections").setAttribute("aria-disabled", String(locked));
    $("#tripDirections").tabIndex = locked ? -1 : 0;
    $("#tripPrimary").textContent = value && data ? "Biraz bekle…" : data?.status === "paused" ? "Kaldığım yerden devam et ↗" : data?.status === "active" ? "Bu durağı tamamladım ✓" : "Geziye başla ↗";
  }

  function directions(stop) {
    const located = Number.isFinite(stop.latitude) && Number.isFinite(stop.longitude) && Math.abs(stop.latitude) <= 90 && Math.abs(stop.longitude) <= 180;
    const params = located ? new URLSearchParams({ api: "1", destination: stop.latitude + "," + stop.longitude, travelmode: "walking" }) : new URLSearchParams({ api: "1", query: [stop.name, stop.address, stop.city_name].filter(Boolean).join(" ") });
    $("#tripDirections").href = "https://www.google.com/maps/" + (located ? "dir/" : "search/") + "?" + params;
    $("#tripDirections").textContent = located ? "Yol tarifi ↗" : "Haritada ara ↗";
  }

  function render() {
    if (!data) return;
    const summary = data.summary, next = data.next_stop;
    $("#tripRouteName").textContent = data.title;
    $("#tripEmpty").hidden = summary.total_count > 0;
    $("#tripJourney").hidden = !summary.total_count;
    $("#tripData").hidden = false;
    $("#tripStateLabel").textContent = ({ not_started: "Başlamaya hazır.", active: "Gezidesin.", paused: "Mola verdin.", completed: "Gezi tamamlandı." })[data.status];
    $("#tripProgressLabel").textContent = summary.completed_count + " / " + summary.total_count + " durak tamamlandı";
    $("#tripProgress").value = summary.completed_percent;
    $("#tripRemainingTime").textContent = duration(summary.remaining_estimated_minutes ?? summary.remaining_visit_minutes);
    $("#tripTimeLabel").textContent = summary.remaining_estimated_minutes == null ? "önerilen ziyaret süresi · geçiş bilinmiyor" : "tahmini kalan süre";
    $("#tripRemainingCount").textContent = String(summary.remaining_count);
    $("#tripCurrentStop").hidden = !next;
    $("#tripFinished").hidden = data.status !== "completed";
    $("#tripFinishedText").textContent = summary.total_count + " durağı tamamladın. Şehirde yeni bir hikâye daha birikti.";
    if (next) {
      const photo = window.GUIDE_PHOTOS?.[next.slug];
      $("#tripStopPhoto").innerHTML = (photo ? `<img src="${h(photo)}" alt="${h(next.name)}" />` : `<span class="trip-photo-fallback" aria-hidden="true">${h(next.name.charAt(0))}</span>`) + `<span class="trip-stop-number" aria-hidden="true">${next.number}</span>`;
      $("#tripNextLabel").textContent = (data.status === "not_started" ? "İLK DURAK" : data.status === "paused" ? "KALDIĞIN DURAK" : "SIRADAKİ DURAK") + " · " + next.number + " / " + summary.total_count;
      $("#tripStopTitle").textContent = next.name;
      $("#tripStopLocation").textContent = [next.city_name, next.district].filter(Boolean).join(" · ");
      $("#tripStopSummary").textContent = next.summary || "Bu durağı keşfetmek için kendine zaman ayır.";
      $("#tripVisitDuration").textContent = duration(next.visit_minutes || 90) + " önerilen ziyaret";
      directions(next);
    }
    $("#tripPrimary").hidden = !next;
    $("#tripPause").hidden = data.status !== "active" || !next;
    $("#tripRestart").hidden = data.status === "not_started" || !summary.total_count;
    $("#tripStops").innerHTML = data.stops.map(stop => `<li data-completed="${stop.completed}" data-current="${next?.slug === stop.slug}"><span class="trip-checkpoint-number" aria-hidden="true">${stop.completed ? "✓" : stop.number}</span><div class="trip-checkpoint-copy"><strong>${h(stop.name)}</strong><span>${stop.completed ? "Tamamlandı" : next?.slug === stop.slug ? "Sıradaki durak" : "Seni bekliyor"}</span></div>${stop.completed ? `<button class="text-button" type="button" data-trip-undo="${h(stop.slug)}" aria-label="${h(stop.name)} tamamlamasını geri al">Geri al</button>` : ""}</li>`).join("");
    $("#tripEstimateNote").textContent = data.estimate_note;
    setBusy(busy);
  }

  async function open(id) {
    if (!Number.isSafeInteger(id) || id < 1) return;
    if (!app.state.user) return app.openAuth("login");
    const token = ++generation;
    routeId = id; data = null; needsReload = false;
    $("#tripRouteName").textContent = app.state.routes.find(route => route.id === id)?.title || "Gezi rotan";
    $("#tripData").hidden = true;
    $("#tripRetry").hidden = true;
    $("#tripRestartConfirm").hidden = true;
    for (const name of ["routeViewDialog", "dayPlannerDialog"]) { if ($("#" + name)?.open) $("#" + name).close(); }
    if (!$("#tripDialog").open) $("#tripDialog").showModal();
    status("Gezi defterin açılıyor…"); setBusy(true);
    try {
      const result = await app.fetchJson("/api/routes/" + id + "/trip");
      if (token !== generation || !$("#tripDialog").open) return;
      data = result; render(); status();
    } catch (error) {
      if (token !== generation) return;
      needsReload = true; status(error.message, true); $("#tripRetry").hidden = false;
    } finally { if (token === generation) setBusy(false); }
  }

  async function change(action, slug = null) {
    if (!data || busy || needsReload) return;
    const token = generation, id = routeId;
    const payload = { action, expected_revision: data.revision };
    if (slug) payload.place_slug = slug;
    status("Gezi ilerlemen kaydediliyor…"); $("#tripRetry").hidden = true; setBusy(true);
    let saved = false;
    try {
      const result = await app.fetchJson("/api/routes/" + id + "/trip", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (token !== generation || !$("#tripDialog").open) return;
      data = result; needsReload = false; saved = true;
      $("#tripRestartConfirm").hidden = true;
      render();
      const messages = { start: "Güzel bir gün olsun. İlk duraktan başlayalım!", pause: "Mola kaydedildi. Hazır olduğunda devam edebilirsin.", resume: "Kaldığın yerden devam ediyorsun.", complete_stop: data.status === "completed" ? "Bu rotadaki tüm durakları tamamladın!" : "Durak tamamlandı. Sıradaki durak seni bekliyor.", undo_stop: "Durak yeniden sıraya alındı.", restart: "Gezi yeniden başladı. İlk duraktan devam edebilirsin." };
      status(messages[action]);
    } catch (error) {
      if (token !== generation) return;
      needsReload = true;
      if (error.status === 409) {
        try {
          const latest = await app.fetchJson("/api/routes/" + id + "/trip");
          if (token !== generation) return;
          data = latest; needsReload = false; $("#tripRestartConfirm").hidden = true; render();
          status(error.message + " Güncel durum yüklendi; işlemini yeniden seç.", true);
        } catch (reloadError) {
          if (token !== generation) return;
          status(reloadError.message + " Son durumu yükleyerek yeniden dene.", true); $("#tripRetry").hidden = false;
        }
      } else { status(error.message + " Son durumu yükleyerek yeniden dene.", true); $("#tripRetry").hidden = false; }
    } finally {
      if (token === generation) {
        setBusy(false);
        if (saved && $("#tripDialog").open) (data.next_stop ? $("#tripStopTitle") : $("#tripFinishedTitle")).focus();
      }
    }
  }

  function init(api) {
    app = api;
    $("#tripDialog").addEventListener("close", () => { generation++; routeId = null; data = null; });
    $("#tripRetry").addEventListener("click", () => { if (routeId) open(routeId); });
    $("#tripPrimary").addEventListener("click", () => {
      if (!data) return;
      return change(data.status === "not_started" ? "start" : data.status === "paused" ? "resume" : "complete_stop", data.status === "active" ? data.next_stop?.slug : null);
    });
    $("#tripPause").addEventListener("click", () => change("pause"));
    $("#tripRestart").addEventListener("click", () => { if (data && !busy && !needsReload) $("#tripRestartConfirm").hidden = false; });
    $("#tripCancelRestart").addEventListener("click", () => { $("#tripRestartConfirm").hidden = true; });
    $("#tripConfirmRestart").addEventListener("click", () => { if (!$("#tripRestartConfirm").hidden) return change("restart"); });
    $("#tripDetails").addEventListener("click", () => { if (data?.next_stop && !busy && !needsReload) { const slug = data.next_stop.slug; $("#tripDialog").close(); app.showDetails(slug); } });
    document.addEventListener("click", event => {
      const button = event.target.closest("button"); if (!button) return;
      if (button.dataset.routeTrip) open(Number(button.dataset.routeTrip));
      if (button.dataset.tripUndo) change("undo_stop", button.dataset.tripUndo);
    });
  }
  window.GuideTrip = Object.freeze({ init });
})();
