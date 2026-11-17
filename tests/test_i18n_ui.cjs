"use strict";
// Exercise the real locale runtime and feature modules without a browser dependency.
const fs = require("node:fs"), vm = require("node:vm"), assert = require("node:assert/strict");
const shell = fs.readFileSync("static/index.html", "utf8");
const decode = value => value.replaceAll("&quot;", '"').replaceAll("&#x27;", "'").replaceAll("&amp;", "&").replaceAll("&lt;", "<").replaceAll("&gt;", ">");

function environment(language, storageWorks = true) {
  const listeners = {}, stored = new Map(), nodes = new Map();
  const location = { href: `https://guide.example/static/rotalarim.html?lang=${language}#routes`, origin: "https://guide.example", search: `?lang=${language}`, assign(value) { this.assigned = value; } };
  function node(id) {
    if (!nodes.has(id)) nodes.set(id, { id, value: "", dataset: {}, listeners: {}, textContent: "", innerHTML: "", hidden: false,
      addEventListener(key, callback) { this.listeners[key] = callback; }, setAttribute(key, value) { this[key] = value; }, getAttribute(key) { return this[key]; }, hasAttribute(key) { return Object.hasOwn(this, key); },
      reset() {}, focus() {}, showModal() { this.open = true; }, close() { this.open = false; this.listeners.close?.(); }
    });
    return nodes.get(id);
  }
  const markers = [...shell.matchAll(/<(i18n-text|option|p)\b[^>]*data-i18n="([^"]*)"[^>]*>([^<]*)<\//g)].map((m, index) => {
    const element = node("translation-" + index); element.dataset.i18n = decode(m[2]); element.textContent = decode(m[3]); return element;
  });
  const buttons = ["tr", "en"].map(code => { const b = node(code); b.dataset.language = code; return b; });
  const document = { documentElement: { dataset: { page: "routes" } },
    addEventListener(key, callback, capture) { (listeners[key] ||= []).push({ callback, capture }); },
    querySelector(selector) { return selector.startsWith("#") ? node(selector.slice(1)) : null; },
    querySelectorAll(selector) {
      if (selector === "[data-i18n]") return markers;
      if (selector === "[data-language]") return buttons;
      if (selector.includes("data-i18n-")) return [];
      return [...nodes.values()].filter(n => n.id.startsWith("trip") || n.id.startsWith("budget"));
    }
  };
  const window = {};
  const context = vm.createContext({ window, document, location, URL, URLSearchParams, Headers, Intl,
    localStorage: { getItem(key) { if (!storageWorks) throw Error("disabled"); return stored.get(key); }, setItem(key, value) { if (!storageWorks) throw Error("disabled"); stored.set(key, value); } }
  });
  const run = filename => vm.runInContext(fs.readFileSync("static/" + filename, "utf8"), context);
  run("i18n-data.js"); run("i18n.js");
  for (const { callback } of listeners.DOMContentLoaded || []) callback();
  const click = dataset => {
    const button = { dataset, hasAttribute: key => key === "data-open-day-planner" && Boolean(dataset.openPlanner) };
    for (const { callback, capture } of listeners.click || []) if (!capture) callback({ target: { closest: () => button } });
  };
  return { window, document, node, buttons, markers, location, run, context, listeners, click, stored };
}

async function main() {
  for (const language of ["tr", "en"]) {
    const env = environment(language), i18n = env.window.GuideI18n;
    assert.equal(env.document.documentElement.lang, language);
    assert.equal(i18n.text("Giriş yap"), language === "en" ? "Sign in" : "Giriş yap");
    assert.equal(env.buttons.find(b => b.dataset.language === language)["aria-pressed"], "true");
    assert.equal(env.markers.find(e => e.dataset.i18n === "Keşfet").textContent, language === "en" ? "Explore" : "Keşfet");
    assert.equal(i18n.html(["Hoş geldin, ", "!"], "Giriş yap"), (language === "en" ? "Welcome, " : "Hoş geldin, ") + "Giriş yap!");
    assert.equal(i18n.html(["", " durak"], 1), language === "en" ? "1 stop" : "1 durak");
    assert.equal(i18n.fold("İZMİR IĞDIR"), "izmir igdir");
    assert.equal(i18n.link("https://external.example/"), "https://external.example/");
    assert(i18n.link("/r/token#map").includes("?lang=" + language + "#map"));
    env.buttons.find(b => b.dataset.language !== language).listeners.click();
    assert(env.location.assigned.includes("lang=" + (language === "en" ? "tr" : "en")));
    assert(env.location.assigned.endsWith("#routes"));
  }
  const fallback = environment("en", false);
  assert.equal(fallback.window.GuideI18n.language, "en");
  const anchor = { href: "/hesabim", getAttribute() { return this.href; }, hasAttribute() { return false; } };
  fallback.listeners.click.find(e => e.capture).callback({ button: 0, target: { closest: () => anchor } });
  assert.equal(anchor.href, "/static/hesabim.html?lang=en");

  const env = environment("en"), h = value => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
  const personal = "Giriş yap <b>özel not</b>";
  const app = { state: { user: { name: "Gezgin" }, sessionReady: true, routes: [{ id: 1, title: personal }] }, escapeHtml: h, openAuth() {}, showDetails() {} };
  const budget = { route_title: personal, currency: "TRY", items: [{ id: 1, title: personal, notes: personal, category: "food", planned_kurus: 125050, spent_kurus: 10000, spent_on: "2026-11-17" }], summary: { planned_kurus: 125050, spent_kurus: 10000, remaining_kurus: 115050, categories: [{ category: "food", label: "Food and drink", planned_kurus: 125050, spent_kurus: 10000, remaining_kurus: 115050, item_count: 1 }] } };
  app.fetchJson = async () => budget;
  env.run("budget.js"); env.window.GuideBudget.init(app); env.click({ routeBudget: "1" });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(env.node("budgetRouteName").textContent, personal);
  assert(env.node("budgetItems").innerHTML.includes(h(personal)));
  assert(env.node("budgetItems").innerHTML.includes("Planned"));
  assert(!env.node("budgetItems").innerHTML.includes("Planlanan"));
  assert.match(env.node("budgetItems").innerHTML, /1,250\.50/);
  env.click({ budgetEdit: "1" });
  assert.equal(env.node("budgetItemPlanned").value, "1250.50");
  assert.equal(env.node("budgetNotes").value, personal);

  const stop = { slug: "galata-kulesi", name: "Galata Tower", city_name: "Istanbul", district: "Beyoğlu", summary: "A historic tower.", number: 1, latitude: 41, longitude: 29, visit_minutes: 75 };
  app.fetchJson = async () => ({ title: personal, status: "active", revision: 1, next_stop: stop, stops: [stop], summary: { total_count: 1, completed_count: 0, remaining_count: 1, completed_percent: 0, remaining_visit_minutes: 75, remaining_estimated_minutes: 75 }, estimate_note: "Visit durations are suggestions." });
  env.run("trip.js"); env.window.GuideTrip.init(app); env.click({ routeTrip: "1" });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(env.node("tripRouteName").textContent, personal);
  assert.equal(env.node("tripStateLabel").textContent, "You are exploring.");
  assert.equal(env.node("tripStopTitle").textContent, "Galata Tower");
  assert.match(env.node("tripRemainingTime").textContent, /1 h 15 min/);
  assert.equal(env.node("tripPrimary").textContent, "I've completed this stop ✓");

  let sent;
  env.context.I18N = env.window.GuideI18n;
  env.context.fetch = async (url, options) => { sent = options; return { ok: false, status: 401, json: async () => ({ detail: "Please sign in to continue." }) }; };
  const appSource = fs.readFileSync("static/app.js", "utf8");
  vm.runInContext(appSource.slice(appSource.indexOf("  async function fetchJson("), appSource.indexOf("  async function loadFilters(")), env.context);
  await assert.rejects(env.context.fetchJson("/api/routes", { headers: { "Content-Type": "application/json" }, method: "POST", body: "{}" }), error => error.status === 401);
  assert.equal(sent.headers.get("Accept-Language"), "en");
  assert.equal(sent.headers.get("Content-Type"), "application/json");
  assert.equal(sent.body, "{}");

  for (const filename of ["index.html", "hesabim.html", "rotalarim.html", "gunlugum.html"]) {
    const html = fs.readFileSync("static/" + filename, "utf8");
    const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(m => m[1]);
    assert.equal(new Set(ids).size, ids.length, filename + " contains duplicate IDs");
    assert(!/\s\/\s+data-i18n/.test(html), filename + " contains malformed attributes");
    assert(html.indexOf("/static/i18n.js") < html.indexOf("/static/personal-pages.js"));
    assert.equal([...html.matchAll(/data-language=/g)].length, 2);
  }
  console.log("PASS: TR/EN selection, persistence, storage fallback, navigation, static copy, plural counts, personal-text safety, English budget/trip rendering, locale formatting, request headers and generated pages.");
}
main().catch(error => { console.error(error); process.exitCode = 1; });
