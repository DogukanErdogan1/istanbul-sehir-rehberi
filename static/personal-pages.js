(() => {
  "use strict";
  const I18N = window.GuideI18n || { language: "tr", text: v => v, locale: () => "tr-TR", link: v => v, fold: v => String(v).toLocaleLowerCase("tr-TR"), html: (parts, ...values) => parts.reduce((out, part, index) => out + part + (index < values.length ? values[index] : ""), "") };
  const paths = { "/hesabim": "account", "/rotalarim": "routes", "/gunlugum": "journal" };
  const legacy = { "#profile": "account", "#routes": "routes", "#journal": "journal" };
  const canonical = { account: "/hesabim", routes: "/rotalarim", journal: "/gunlugum" };
  const staticPaths = { account: "/static/hesabim.html", routes: "/static/rotalarim.html", journal: "/static/gunlugum.html" };
  const legacyPage = location.pathname === "/" ? legacy[location.hash] : null;
  const page = paths[location.pathname.replace(/\/$/, "")] || Object.keys(staticPaths).find(key => staticPaths[key] === location.pathname) || legacyPage || "home";
  function navigate(target, replace = false) {
    location[replace ? "replace" : "assign"](I18N.link(staticPaths[target]));
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
  const titles = { account: I18N.text("Hesabım"), routes: I18N.text("Rotalarım"), journal: I18N.text("Gezi Günlüğüm") };
  if (titles[page]) document.title = titles[page] + " — Şehir Arası";
  const put = (id, value) => { const element = document.getElementById(id); if (element) element.textContent = value; };
  function setSession(user, ready = true) {
    root.dataset.auth = ready ? (user ? "member" : "guest") : "loading";
    if (page !== "home") {
      const skip = document.querySelector(".skip-link");
      if (skip) { skip.textContent = I18N.text("Sayfa içeriğine geç"); skip.href = user ? ({ account: "#profile", routes: "#routes", journal: "#journal" })[page] : "#personalGuest"; }
    }
    if (!user) return;
    const words = user.name.trim().split(/\s+/);
    put("accountInitials", (words[0][0] + (words.length > 1 ? words[words.length - 1][0] : "")).toLocaleUpperCase(I18N.locale()));
    put("profileGreeting", I18N.text("MERHABA ") + words[0].toLocaleUpperCase(I18N.locale()) + I18N.text(", DEFTERİNE HOŞ GELDİN"));
    put("accountRole", user.role === "admin" ? I18N.text("Şehrin editörü") : I18N.text("Meraklı bir gezgin"));
    document.getElementById("accountButton")?.classList.toggle("is-current", page === "account");
  }
  function refresh(state, favoriteCount) {
    put("routeSummaryCount", state.routes.length);
    put("routeSummaryStops", new Set(state.routes.flatMap(route => route.places.map(place => place.slug))).size);
    put("journalSummaryCount", state.journal.length);
    put("journalSummaryCities", new Set(state.journal.map(entry => entry.city_slug)).size);
    put("favoritesListCount", favoriteCount + I18N.text(" durak · Tüm şehirlerde"));
    if (I18N.language === "en") {
      for (const [id, count, singular, plural] of [
        ["routeSummaryCount", state.routes.length, "saved route", "saved routes"],
        ["routeSummaryStops", new Set(state.routes.flatMap(route => route.places.map(place => place.slug))).size, "different stop", "different stops"],
        ["journalSummaryCount", state.journal.length, "visit", "visits"],
        ["journalSummaryCities", new Set(state.journal.map(entry => entry.city_slug)).size, "city", "cities"]
      ]) {
        const label = document.getElementById(id)?.nextElementSibling;
        if (label) label.textContent = " " + (count === 1 ? singular : plural);
      }
    }
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
      if (target) link.href = I18N.link(staticPaths[target]);
    });
    put("journalToday", new Date().toLocaleDateString(I18N.locale(), { day: "numeric", month: "long", year: "numeric" }).toLocaleUpperCase(I18N.locale()));
  });
  window.GuidePages = Object.freeze({ page, isPersonal: page !== "home", setSession, refresh, afterLogin, navigate });
})();
