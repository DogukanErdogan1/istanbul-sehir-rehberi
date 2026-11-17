"use strict";
// Validate the real trip UI against the page's IDs without external dependencies.
const fs = require("node:fs"), vm = require("node:vm"), assert = require("node:assert/strict");
const html = fs.readFileSync("static/index.html", "utf8");
const nodes = new Map([...html.matchAll(/<[^>]*\bid="([^"]+)"[^>]*>/g)].map(match => [match[1], {
  id: match[1], hidden: /\bhidden\b/.test(match[0]), value: "", textContent: "", innerHTML: "", dataset: {}, listeners: {},
  setAttribute(key, value) { this[key] = value; }, addEventListener(key, value) { this.listeners[key] = value; }, focus() {},
  showModal() { this.open = true; }, close() { this.open = false; this.listeners.close?.(); }
}]));
const node = id => { assert(nodes.has(id), "Missing HTML node " + id); return nodes.get(id); };
const listeners = {};
const document = { querySelector: selector => node(selector.slice(1)), querySelectorAll: () => [...nodes.values()].filter(item => item.id.startsWith("trip")), addEventListener: (key, callback) => { listeners[key] = callback; } };
const window = { GUIDE_PHOTOS: { "stop-a": "/static/photos/test.jpg" } };
vm.runInNewContext(fs.readFileSync("static/trip.js", "utf8"), { window, document, URLSearchParams, Math, Number, String, JSON });
let state = "not_started", revision = 0, completed = new Set(), mode = "ready", resolveGet, resolvePost, loginCount = 0;
let places = ["a", "b", "c"].map((key, index) => ({ id: index + 1, slug: "stop-" + key, name: "Durak " + key, number: index + 1, city_name: "İstanbul", district: "Semt", address: "Adres", latitude: 41 + index * .001, longitude: 29, visit_minutes: 60, summary: "Bir durak." }));
const requests = [];
function snapshot() {
  const stops = places.map(place => ({ ...place, completed: completed.has(place.slug) })), remaining = stops.filter(place => !place.completed);
  const total = stops.length, done = total - remaining.length;
  return { route_id: 1, title: "Örnek gezi", status: !total ? "paused" : state, revision, stops, next_stop: remaining[0] || null,
    summary: { total_count: total, completed_count: done, remaining_count: remaining.length, completed_percent: total ? Math.round(done / total * 100) : 0,
      remaining_visit_minutes: remaining.length * 60, remaining_estimated_minutes: remaining.some(p => p.latitude == null) ? null : remaining.length * 70 }, estimate_note: "Süreler tahmindir." };
}
function apply(payload) {
  assert.equal(payload.expected_revision, revision);
  if (payload.action === "start" || payload.action === "resume") state = "active";
  if (payload.action === "pause") state = "paused";
  if (payload.action === "complete_stop") { assert.equal(payload.place_slug, snapshot().next_stop.slug); completed.add(payload.place_slug); if (completed.size === places.length) state = "completed"; }
  if (payload.action === "undo_stop") { completed.delete(payload.place_slug); if (state === "completed") state = "paused"; }
  if (payload.action === "restart") { completed.clear(); state = "active"; }
  revision++; return snapshot();
}
const app = { state: { user: null, routes: [{ id: 1, title: "Örnek gezi" }] }, openAuth() { loginCount++; }, showDetails() {},
  escapeHtml: value => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;"),
  fetchJson: async (url, options) => { requests.push({ url, options });
    if (!options) { if (mode === "pending-get") return new Promise(resolve => { resolveGet = resolve; }); return snapshot(); }
    const payload = JSON.parse(options.body);
    if (mode === "pending-post") return new Promise(resolve => { resolvePost = () => resolve(apply(payload)); });
    if (mode === "conflict") { mode = "ready"; completed.add(snapshot().next_stop.slug); revision++; const error = new Error("Eski ilerleme."); error.status = 409; throw error; }
    const result = apply(payload);
    if (mode === "lost-response") { mode = "ready"; throw new Error("Bağlantı kesildi."); }
    return result;
  }
};
window.GuideTrip.init(app);
const tick = () => new Promise(resolve => setImmediate(resolve));
const launch = () => listeners.click({ target: { closest: () => ({ dataset: { routeTrip: "1" } }) } });
const press = id => node(id).listeners.click();
const writes = () => requests.filter(r => r.options).length;
(async () => {
  launch(); assert.equal(loginCount, 1); assert.equal(requests.length, 0);
  app.state.user = { id: 1 }; launch(); await tick();
  assert.equal(node("tripStopTitle").textContent, "Durak a"); assert.equal(node("tripProgress").value, 0);
  assert(node("tripDirections").href.startsWith("https://www.google.com/maps/dir/")); assert(!node("tripDirections").href.includes("origin="));
  await press("tripPrimary"); assert.equal(state, "active"); assert.equal(node("tripPause").hidden, false);
  mode = "pending-post"; const before = writes(), pending = press("tripPrimary"); await press("tripPrimary"); assert.equal(writes(), before + 1); assert.equal(node("tripPrimary").disabled, true);
  resolvePost(); await pending; mode = "ready"; assert.equal(node("tripStopTitle").textContent, "Durak b");
  await press("tripPause"); assert.equal(state, "paused"); assert(node("tripPrimary").textContent.includes("devam"));
  await press("tripPrimary"); await press("tripPrimary"); await press("tripPrimary");
  assert.equal(state, "completed"); assert.equal(node("tripFinished").hidden, false); assert.equal(node("tripPrimary").hidden, true); assert.equal(node("tripProgress").value, 100);
  listeners.click({ target: { closest: () => ({ dataset: { tripUndo: "stop-b" } }) } }); await tick();
  assert.equal(state, "paused"); assert.equal(node("tripStopTitle").textContent, "Durak b");
  const count = writes(); press("tripRestart"); assert.equal(node("tripRestartConfirm").hidden, false); assert.equal(writes(), count);
  press("tripCancelRestart"); assert.equal(node("tripRestartConfirm").hidden, true);
  press("tripRestart"); await press("tripConfirmRestart"); assert.equal(completed.size, 0); assert.equal(node("tripStopTitle").textContent, "Durak a");
  mode = "conflict"; const conflicts = writes(); await press("tripPrimary");
  assert.equal(writes(), conflicts + 1); assert.equal(completed.size, 1); assert.equal(node("tripStopTitle").textContent, "Durak b"); assert(node("tripStatus").textContent.includes("Güncel durum"));
  mode = "lost-response"; await press("tripPrimary"); assert.equal(node("tripPrimary").disabled, true); assert.equal(node("tripRetry").hidden, false); assert.equal(node("tripDirections")["aria-disabled"], "true");
  press("tripRetry"); await tick(); assert.equal(node("tripStopTitle").textContent, "Durak c"); assert.equal(node("tripPrimary").disabled, false);
  mode = "pending-get"; launch(); node("tripDialog").close(); resolveGet(snapshot()); await tick(); assert.equal(node("tripData").hidden, true);
  mode = "ready"; places[2].latitude = null; launch(); await tick(); assert(node("tripTimeLabel").textContent.includes("bilinmiyor")); assert(node("tripDirections").href.includes("/search/"));
  places = []; launch(); await tick(); assert.equal(node("tripEmpty").hidden, false); assert.equal(node("tripJourney").hidden, true); assert.equal(node("tripPrimary").hidden, true);
  const core = fs.readFileSync("static/app.js", "utf8");
  const fetchCode = core.slice(core.indexOf("  async function fetchJson("), core.indexOf("  async function loadFilters("));
  const scope = { fetch: async () => ({ ok: false, status: 409, json: async () => ({ detail: "Conflict" }) }) };
  vm.createContext(scope); vm.runInContext(fetchCode, scope); await assert.rejects(scope.fetchJson("/example"), error => error.status === 409 && error.message === "Conflict");
  console.log("PASS: trip launch, persistent-state display, pause/resume, ordered completion, duplicate protection, undo, confirmed restart, 409 refresh, lost-response recovery, stale loads, empty routes, safe directions and HTTP error status.");
})().catch(error => { console.error(error); process.exitCode = 1; });
