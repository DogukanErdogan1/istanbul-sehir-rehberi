"use strict";
// Exercise the real UI module against the page's IDs, without a browser or dependencies.
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const html = fs.readFileSync("static/index.html", "utf8");
const source = fs.readFileSync("static/day-planner.js", "utf8");
const nodes = new Map([...html.matchAll(/<[^>]*\bid="([^"]+)"[^>]*>/g)].map(match => [match[1], {
  id: match[1], value: match[0].match(/value="([^"]*)"/)?.[1] || "", textContent: "", innerHTML: "",
  hidden: /\bhidden\b/.test(match[0]), dataset: {}, listeners: {}, checked: false,
  setAttribute(key, value) { this[key] = value; }, addEventListener(key, value) { this.listeners[key] = value; },
  showModal() { this.open = true; }, close() { this.open = false; this.listeners.close?.(); }
}]));
const interests = ["museum", "history", "view", "nature", "culture"].map(value => ({ value, checked: value === "museum" }));
const listeners = {};
const node = id => { assert(nodes.has(id), "Missing HTML ID: " + id); return nodes.get(id); };
const document = {
  querySelector(selector) { return node(selector.slice(1)); },
  querySelectorAll(selector) { return selector.includes("plannerInterest") ? interests.filter(input => input.checked) : [...nodes.values()].filter(item => item.id.startsWith("planner")); },
  addEventListener(key, value) { listeners[key] = value; }
};
const window = {};
vm.runInNewContext(source, { window, document, Intl, Date, Math, Number, String, JSON, Error, URL });
const fixture = () => ({ status: "ready", message: "Plan hazır.", notes: ["Saatler tahmindir."],
  route: { title: "Ankara · Benim bir günüm", notes: "Önerilen plan", places: [{ slug: "place-a" }, { slug: "place-b" }] },
  summary: { start_time: "09:00", end_time: "11:45", total_minutes: 165, free_minutes: 75, visit_minutes: 120, estimated_transfer_minutes: 15, break_minutes: 30, stop_count: 2 },
  schedule: [{ kind: "visit", title: "Birinci durak", start: "09:00", end: "10:00", minutes: 60, description: "Müzeler", place_slug: "place-a", source_url: "javascript:alert(1)" },
    { kind: "break", title: "Mola", start: "10:00", end: "10:30", minutes: 30, description: "Dinlenme" },
    { kind: "transfer", title: "Tahmini geçiş", start: "10:30", end: "10:45", minutes: 15, description: "A → B" },
    { kind: "visit", title: "İkinci durak", start: "10:45", end: "11:45", minutes: 60, description: "Müzeler", place_slug: "place-b", source_url: "https://example.org/venue" }] });
const requests = [];
let authOpened = 0, routesLoaded = 0, resolveSave, resolvePlan, mode = "ready";
const app = { state: { user: null, sessionReady: true, city: "ankara" },
  escapeHtml: value => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;"),
  openAuth() { authOpened++; }, showDetails() {}, loadRoutes: async () => { routesLoaded++; },
  fetchJson: async (url, options) => { requests.push({ url, options });
    if (url === "/api/routes") return new Promise(resolve => { resolveSave = resolve; });
    if (mode === "pending") return new Promise(resolve => { resolvePlan = resolve; });
    if (mode === "empty") return { status: "empty", message: "Süreyi artır.", route: null };
    if (mode === "error") throw new Error("Bağlantı kurulamadı.");
    return fixture();
  }
};
window.GuidePlanner.init(app);
node("plannerDuration").value = "240"; node("plannerBreak").value = "30"; node("plannerPace").value = "balanced";
const tick = () => new Promise(resolve => setImmediate(resolve));
const launch = () => listeners.click({ target: { closest: () => ({ dataset: {}, hasAttribute: name => name === "data-open-day-planner" }) } });
const submit = () => node("dayPlannerForm").listeners.submit({ preventDefault() {} });
(async () => {
  launch(); assert.equal(node("plannerCity").value, "ankara");
  await submit();
  assert.equal(node("plannerResult").hidden, false);
  assert.equal(JSON.parse(requests[0].options.body).available_minutes, 240);
  assert(!node("plannerTimeline").innerHTML.includes("javascript:"));
  assert(node("plannerTimeline").innerHTML.includes("https://example.org/venue"));
  assert.equal(node("plannerSave").textContent, "Kaydetmek için giriş yap");
  app.state.sessionReady = false; window.GuidePlanner.sessionChanged(); assert.equal(node("plannerSave").disabled, true);
  app.state.sessionReady = true; window.GuidePlanner.sessionChanged();
  node("plannerRouteTitle").value = "Benim güzel günüm";
  await node("plannerSave").listeners.click();
  assert.equal(authOpened, 1); assert.equal(node("dayPlannerDialog").open, false);
  assert.equal(window.GuidePlanner.afterLogin(), false);
  app.state.user = { id: 1, name: "Gezgin" }; window.GuidePlanner.sessionChanged();
  assert.equal(window.GuidePlanner.afterLogin(), true); assert.equal(node("dayPlannerDialog").open, true);
  assert.equal(node("plannerRouteTitle").value, "Benim güzel günüm"); assert.equal(window.GuidePlanner.afterLogin(), false);
  const saving = node("plannerSave").listeners.click(); await node("plannerSave").listeners.click();
  assert.equal(requests.filter(r => r.url === "/api/routes").length, 1);
  const payload = JSON.parse(requests.at(-1).options.body); assert.equal(payload.title, "Benim güzel günüm"); assert.deepEqual(payload.place_slugs, ["place-a", "place-b"]);
  resolveSave({ id: 7 }); await saving;
  assert.equal(routesLoaded, 1); assert.equal(node("plannerSavedLink").hidden, false);
  await node("plannerSave").listeners.click(); assert.equal(requests.filter(r => r.url === "/api/routes").length, 1);
  node("dayPlannerForm").listeners.input(); assert.equal(node("plannerSave").disabled, true); assert.equal(node("plannerMap").disabled, true);
  const count = requests.length; interests.forEach(input => { input.checked = false; }); await submit(); assert.equal(requests.length, count);
  assert(node("plannerStatus").textContent.includes("ilgi alanı"));
  interests[0].checked = true; node("plannerStart").value = "23:30"; await submit(); assert.equal(requests.length, count);
  node("plannerStart").value = "09:00";
  mode = "empty"; await submit(); assert.equal(node("plannerResult").hidden, true); assert.equal(node("plannerStatus").textContent, "Süreyi artır.");
  mode = "error"; await submit(); assert.equal(node("plannerStatus").textContent, "Bağlantı kurulamadı.");
  mode = "pending"; const pending = submit(); node("dayPlannerDialog").close(); resolvePlan(fixture()); await pending;
  assert.equal(node("plannerResult").hidden, true); assert.equal(node("plannerGenerate").disabled, false);
  mode = "ready"; launch(); await submit(); assert.equal(node("plannerResult").hidden, false);
  console.log("PASS: planner form, login resume, one-time save, dirty preferences, invalid time/interests, empty/error states, stale responses and safe source links.");
})().catch(error => { console.error(error); process.exitCode = 1; });
