/* Translate only authored UI strings. Personal data is never passed through a translator. */
(() => {
  "use strict";
  const key = "sehir-arasi:language";
  const requested = new URLSearchParams(location.search).get("lang");
  let saved;
  try { saved = localStorage.getItem(key); } catch { /* The query string also carries the preference. */ }
  const language = ["tr", "en"].includes(requested) ? requested : saved === "en" ? "en" : "tr";
  if (["tr", "en"].includes(requested)) { try { localStorage.setItem(key, language); } catch {} }
  const translations = window.GuideTranslations || { ui: {}, fragments: {} };
  const text = value => {
    if (language !== "en") return value;
    const trimmed = value.trim();
    if (!Object.hasOwn(translations.ui, trimmed)) return value;
    return value.slice(0, value.indexOf(trimmed)) + translations.ui[trimmed] + value.slice(value.indexOf(trimmed) + trimmed.length);
  };
  const singular = { "stops": "stop", "STOPS": "STOP", "reviews": "review", "cities": "city", "memories": "memory", "lovely memories": "lovely memory", "places to explore": "place to explore", "places await you": "place awaits you", "saved stops": "saved stop" };
  const html = (parts, ...values) => parts.reduce((out, part, index) => {
    let authored = language === "en" ? translations.fragments[part] ?? part : part;
    if (language === "en" && index > 0 && values[index - 1] === 1) {
      authored = authored.replace(/^((?:\s|<[^>]*>)*)(lovely memories|places to explore|places await you|saved stops|stops|STOPS|reviews|cities|memories)\b/, (_, prefix, noun) => prefix + singular[noun]);
    }
    return out + authored + (index < values.length ? values[index] : "");
  }, "");
  const link = value => {
    const url = new URL(value, location.href);
    if (url.origin !== location.origin) return value;
    url.searchParams.set("lang", language);
    return url.pathname + url.search + url.hash;
  };
  window.GuideI18n = Object.freeze({ language, text, html, link,
    locale: () => language === "en" ? "en-GB" : "tr-TR",
    fold: value => String(value ?? "").toLocaleLowerCase("tr-TR").normalize("NFD").replace(/\p{Diacritic}/gu, "").replace(/ı/g, "i")
  });
  document.documentElement.lang = language;
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-i18n]").forEach(element => { element.textContent = text(element.textContent); });
    for (const attribute of ["aria-label", "placeholder", "title", "alt"]) {
      document.querySelectorAll(`[data-i18n-${attribute}]`).forEach(element => {
        element.setAttribute(attribute, text(element.getAttribute(`data-i18n-${attribute}`)));
      });
    }
    document.querySelectorAll("[data-language]").forEach(button => {
      button.setAttribute("aria-pressed", String(button.dataset.language === language));
      button.addEventListener("click", () => {
        const next = button.dataset.language;
        if (next === language || !["tr", "en"].includes(next)) return;
        try { localStorage.setItem(key, next); } catch {}
        const url = new URL(location.href); url.searchParams.set("lang", next);
        location.assign(url.href);
      });
    });
    if (language === "en" && (!document.documentElement.dataset.page || document.documentElement.dataset.page === "home")) document.title = "Şehir Arası — One city. A thousand stories. Your route.";
    const description = document.querySelector('meta[name="description"]');
    if (description && language === "en") description.content = "Explore Istanbul, Ankara and Izmir. Discover places on the map, plan your route and keep a travel journal.";
  });
  // Include the preference in internal navigation even when browser storage is disabled.
  document.addEventListener("click", event => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
    const anchor = event.target.closest("a[href]");
    if (!anchor || anchor.target || anchor.hasAttribute("download")) return;
    const href = anchor.getAttribute("href");
    if (!href || href.startsWith("#")) return;
    const url = new URL(href, location.href);
    if (url.origin !== location.origin) return;
    const pages = { "/hesabim": "/static/hesabim.html", "/rotalarim": "/static/rotalarim.html", "/gunlugum": "/static/gunlugum.html" };
    url.pathname = pages[url.pathname] || url.pathname;
    anchor.href = link(url.href);
  }, true);
})();
