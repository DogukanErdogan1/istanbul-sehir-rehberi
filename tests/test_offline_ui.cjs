"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const origin = "https://guide.example";
const fixture = {
  version: 1, downloaded_at: "2026-11-17T12:00:00Z",
  cities: [{ slug: "istanbul" }, { slug: "izmir" }],
  categories: [{ slug: "history", name: "Historic places" }],
  places: [
    { slug: "yerebatan-sarnici", name: "Basilica Cistern", city_slug: "istanbul", district: "Fatih", category_slug: "history", indoor: true, original_content: { name: "Yerebatan Sarnıcı" } },
    { slug: "saat-kulesi", name: "Clock Tower", city_slug: "izmir", district: "Konak", category_slug: "history", indoor: false },
  ],
  templates: [{ city_slug: "istanbul", title: "A historic walk" }, { city_slug: "izmir", title: "By the coast" }],
};

async function checkApp() {
  const nodes = new Map();
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, { addEventListener(event, action) { this[event] = action; } });
    return nodes.get(id);
  };
  const listeners = {};
  const requests = [];
  let online = true;
  let saved = false;
  let downloadFails = false;
  const context = {
    window: { isSecureContext: true, addEventListener(event, action) { listeners[event] = action; }, GUIDE_PHOTOS: { cistern: "/static/photos/yerebatan-sarnici.jpg" }, GuideI18n: {
      language: "en", locale: () => "en-GB", fold: value => value.toLowerCase().replaceAll("ı", "i"),
    } },
    navigator: { get onLine() { return online; }, serviceWorker: { register: async path => {
      assert.equal(path, "/offline-worker.js"); return { active: {} };
    } } },
    document: { addEventListener(event, action) { listeners[event] = action; }, getElementById: node,
      querySelectorAll: () => [{ src: origin + "/static/app.js?v=offline-1" }] },
    location: { href: origin + "/?lang=en", origin }, URL, Request, Response,
    fetch: async path => { requests.push(path); return new Response("{}", { status: 404 }); },
    caches: {
      match: async key => saved && key === "/api/offline-guide?lang=en" ? Response.json(fixture) : undefined,
      open: async () => ({ addAll: async files => {
        assert(files.every(file => file.credentials === "omit"));
        assert(files.some(file => file.url.endsWith("/api/offline-guide?lang=tr")));
        assert(files.some(file => file.url.endsWith("/api/offline-guide?lang=en")));
        assert(files.some(file => /yerebatan-sarnici\.jpg$/.test(file.url)));
        assert(files.some(file => file.url.endsWith("/static/app.js?v=offline-1")));
        if (downloadFails) throw Error("quota");
        saved = true;
      }, keys: async () => [] }),
      delete: async () => { saved = false; },
    },
  };
  context.window.caches = context.caches;
  vm.runInNewContext(fs.readFileSync("static/offline.js", "utf8"), context);
  await listeners.DOMContentLoaded();
  await node("offlineDownload").click();
  assert.equal(node("offlineDownload").textContent, "Update downloaded guide");
  downloadFails = true;
  await node("offlineDownload").click();
  assert.match(node("offlineFeedback").textContent, /could not finish/);
  assert.equal(saved, true);
  const { request } = context.window.GuideOffline;
  assert.equal((await request("/api/places/yerebatan-sarnici")).status, 404, "HTTP errors must not serve stale data");
  online = false;
  listeners.offline();
  assert.equal(node("offlineBanner").hidden, false);
  assert.equal(node("offlineDownload").disabled, true);
  for (const query of ["Basilica", "Yerebatan%20Sarnici"]) {
    assert.equal((await (await request(`/api/places?city=istanbul&indoor=true&q=${query}`)).json()).items[0].name, "Basilica Cistern");
  }
  assert.equal((await (await request("/api/places/yerebatan-sarnici")).json()).offline, true);
  assert.equal((await (await request("/api/route-templates?city=izmir")).json()).items[0].title, "By the coast");
  for (const path of ["/api/auth/me", "/api/journal", "/api/routes/1/trip", "/api/shared-routes/example"]) {
    await assert.rejects(request(path), /needs an internet connection/);
  }
  await assert.rejects(request("/api/places/yerebatan-sarnici/reviews", { method: "POST" }), /needs an internet connection/);
  assert.equal(requests.length, 1, "No fetches or queued writes offline");
  await node("offlineRemove").click();
  await assert.rejects(request("/api/places"), /needs an internet connection/);
  assert.match(node("offlineBanner").textContent, /Download the guide/);
}

async function checkWorker() {
  const listeners = {};
  const hits = [];
  vm.runInNewContext(fs.readFileSync("static/offline-worker.js", "utf8"), {
    self: { location: { origin }, addEventListener(event, action) { listeners[event] = action; } }, URL,
    fetch: async () => { throw Error("offline"); },
    caches: { match: async (key, options) => { hits.push(key.url || key); assert.match(options.cacheName, /offline-pack/); return new Response("Saved"); } },
  });
  function intercept(path, mode, method = "GET") {
    let result;
    listeners.fetch({ request: { url: new URL(path, origin).href, mode, method }, respondWith(response) { result = response; } });
    return result;
  }
  assert.equal(await (await intercept("/?lang=en", "navigate")).text(), "Saved");
  assert.equal(await (await intercept("/rotalarim?lang=en", "navigate")).text(), "Saved");
  assert.equal(await (await intercept("/static/app.js?v=offline-1", "cors")).text(), "Saved");
  assert.deepEqual(hits, ["/", "/static/rotalarim.html", origin + "/static/app.js?v=offline-1"]);
  assert.equal(intercept("/api/auth/me", "cors"), undefined);
  assert.equal(intercept("/api/routes", "cors", "POST"), undefined);
  assert.equal(intercept("/r/share-token", "navigate"), undefined);
  assert.equal(intercept("https://tile.openstreetmap.org/1/1/1.png", "cors"), undefined);
}

Promise.all([checkApp(), checkWorker()]).then(() => {
  console.log("PASS: bilingual download, failed refresh, reload and assets, offline search/details/routes, removal, account and tile exclusions.");
}).catch(error => { console.error(error); process.exitCode = 1; });
