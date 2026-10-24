(() => {
  "use strict";
  const paths = { "/hesabim": "account", "/rotalarim": "routes", "/gunlugum": "journal" };
  const legacy = { "#profile": "account", "#routes": "routes", "#journal": "journal" };
  const canonical = { account: "/hesabim", routes: "/rotalarim", journal: "/gunlugum" };
  const staticPaths = { account: "/static/hesabim.html", routes: "/static/rotalarim.html", journal: "/static/gunlugum.html" };
  const legacyPage = location.pathname === "/" ? legacy[location.hash] : null;
  const page = paths[location.pathname.replace(/\/$/, "")] || Object.keys(staticPaths).find(key => staticPaths[key] === location.pathname) || legacyPage || "home";
  function navigate(target, replace = false) {
    location[replace ? "replace" : "assign"](staticPaths[target]);
  }
  if (legacyPage) navigate(legacyPage, true);
  document.addEventListener("click", event => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest("a");
    const target = link && Object.keys(canonical).find(key => link.getAttribute("href") === canonical[key]);
    if (target) { event.preventDefault(); navigate(target); }
  });
  const root = document.documentElement;
  root.dataset.page = page;
  root.dataset.auth = "loading";
  const titles = { account: "Hesabım", routes: "Rotalarım", journal: "Gezi Günlüğüm" };
  if (titles[page]) document.title = titles[page] + " — Şehir Arası";
  const put = (id, value) => { const element = document.getElementById(id); if (element) element.textContent = value; };
  function setSession(user, ready = true) {
    root.dataset.auth = ready ? (user ? "member" : "guest") : "loading";
    if (page !== "home") {
      const skip = document.querySelector(".skip-link");
      if (skip) { skip.textContent = "Sayfa içeriğine geç"; skip.href = user ? ({ account: "#profile", routes: "#routes", journal: "#journal" })[page] : "#personalGuest"; }
    }
    if (!user) return;
    const words = user.name.trim().split(/\s+/);
    put("accountInitials", (words[0][0] + (words.length > 1 ? words[words.length - 1][0] : "")).toLocaleUpperCase("tr-TR"));
    put("profileGreeting", "MERHABA " + words[0].toLocaleUpperCase("tr-TR") + ", DEFTERİNE HOŞ GELDİN");
    put("accountRole", user.role === "admin" ? "Şehrin editörü" : "Meraklı bir gezgin");
    document.getElementById("accountButton")?.classList.toggle("is-current", page === "account");
  }
  function refresh(state, favoriteCount) {
    put("routeSummaryCount", state.routes.length);
    put("routeSummaryStops", new Set(state.routes.flatMap(route => route.places.map(place => place.slug))).size);
    put("journalSummaryCount", state.journal.length);
    put("journalSummaryCities", new Set(state.journal.map(entry => entry.city_slug)).size);
    put("favoritesListCount", favoriteCount + " durak · Tüm şehirlerde");
  }
  function afterLogin() {
    if (page === "home" && !document.getElementById("routeDialog")?.open) navigate("account");
    else window.scrollTo({ top: 0, behavior: "smooth" });
  }
  document.addEventListener("DOMContentLoaded", () => {
    const mainLink = document.querySelector('.main-nav a[href="' + (canonical[page] || "/") + '"]');
    if (mainLink) mainLink.setAttribute("aria-current", "page");
    document.querySelectorAll("a").forEach(link => {
      const target = Object.keys(canonical).find(key => link.getAttribute("href") === canonical[key]);
      if (target) link.href = staticPaths[target];
    });
    put("journalToday", new Date().toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" }).toLocaleUpperCase("tr-TR"));
  });
  window.GuidePages = Object.freeze({ page, isPersonal: page !== "home", setSession, refresh, afterLogin, navigate });
})();
