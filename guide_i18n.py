"""Request-scoped English overlays. Stored content and personal writing stay untouched."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from guide_catalog import NEW_PLACES, PLACE_META

LOCALES = Path(__file__).resolve().parent / "static" / "locales"
CATALOG = json.loads((LOCALES / "catalog.en.json").read_text(encoding="utf-8"))
MESSAGES = json.loads((LOCALES / "ui.en.json").read_text(encoding="utf-8")) | json.loads((LOCALES / "messages.en.json").read_text(encoding="utf-8"))
CATEGORIES = {"museum": "Museums", "history": "Historic places", "view": "Views", "nature": "Nature", "culture": "Culture"}
CITIES = {"istanbul": "Istanbul", "ankara": "Ankara", "izmir": "Izmir"}
META = PLACE_META | {p["slug"]: p for p in NEW_PLACES}


def language(request):
    explicit = request.query_params.get("lang")
    if explicit in ("en", "tr"):
        return explicit
    # Respect language priorities, including clients with en-GB/tr-TR preferences.
    choices = []
    for index, entry in enumerate(request.headers.get("accept-language", "tr").split(",")):
        code, *parameters = entry.strip().lower().split(";")
        try:
            weight = next((float(p.strip()[2:]) for p in parameters if p.strip().startswith("q=")), 1.0)
        except ValueError:
            continue
        if code.split("-")[0] in ("tr", "en") and 0 < weight <= 1:
            choices.append((weight, -index, code.split("-")[0]))
    return max(choices)[2] if choices else "tr"


def fold(value):
    return "".join(c for c in unicodedata.normalize("NFD", str(value).lower().replace("ı", "i")) if not unicodedata.combining(c))


def message(value):
    if not isinstance(value, str):
        return value
    prefix = "Value error, " if value.startswith("Value error, ") else ""
    return MESSAGES.get(value.removeprefix(prefix), value)


def overlay(item, kind):
    entry = CATALOG[kind].get(item.get("slug"))
    originals = dict(item.get("original_content", {}))
    if entry:
        for field, translated in entry["en"].items():
            if item.get(field) == entry["source"].get(field):
                originals[field] = item[field]
                item[field] = translated
    if originals:
        item["original_content"] = originals
    return item


def place(item):
    if not item:
        return item
    overlay(item, "places")
    if "city_name" in item:
        item["city_name"] = CITIES.get(item.get("city_slug"), item["city_name"])
    if "category_name" in item:
        item["category_name"] = CATEGORIES.get(item.get("category_slug"), item["category_name"])
    original = META.get(item.get("slug"), {}).get("accessibility_note")
    if original and item.get("accessibility_note") == original:
        item.setdefault("original_content", {})["accessibility_note"] = original
        item["accessibility_note"] = message(original)
    # Names and descriptions added/changed by editors have no automatic translation.
    if any(key in item and key not in item.get("original_content", {}) for key in ("name", "summary", "description")):
        item["translation_note"] = "Some content is shown in its original language."
    return item


def metrics(data, places=()):
    if not data:
        return
    data["note"] = message(data.get("note", ""))
    names = {p.get("original_content", {}).get("name", p["name"]): p["name"] for p in places}
    for leg in data.get("legs", []):
        for field in ("from", "to"):
            leg[field] = names.get(leg[field], leg[field])


def route(data):
    for item in data.get("places", []):
        place(item)
    metrics(data.get("metrics"), data.get("places", []))


def day_plan(data):
    data["message"] = message(data.get("message", ""))
    data["notes"] = [message(note) for note in data.get("notes", [])]
    if not data.get("route"):
        return
    proposal = data["route"]
    route(proposal)
    lookup = {p["slug"]: p for p in proposal["places"]}
    previous = None
    for index, entry in enumerate(data["schedule"]):
        if entry["kind"] == "visit":
            stop = lookup[entry["place_slug"]]
            entry["title"], entry["description"] = stop["name"], CATEGORIES[stop["category_slug"]]
            previous = stop["name"]
        elif entry["kind"] == "transfer":
            following = next(s for s in data["schedule"][index + 1:] if s["kind"] == "visit")
            entry["title"] = message(entry["title"])
            entry["description"] = previous + " → " + lookup[following["place_slug"]]["name"]
        else:
            entry["title"], entry["description"] = message(entry["title"]), message(entry["description"])
    city = CITIES.get(proposal["places"][0]["city_slug"], "City")
    summary = data["summary"]
    proposal["title"] = city + " · My day out"
    proposal["description"] = f"A day out in {city}, {summary['start_time']}–{summary['end_time']}. Visit and transfer times are estimates."
    proposal["notes"] = (proposal["description"] + "\n" + " · ".join(f"{e['start']} {e['title']}" for e in data["schedule"] if e["kind"] != "transfer"))[:500]


def localize(path, data, status=200):
    """Known response schemas only; never recursively translate arbitrary strings."""
    if status >= 400 and isinstance(data, dict):
        if isinstance(data.get("detail"), str):
            data["detail"] = message(data["detail"])
        elif isinstance(data.get("detail"), list):
            for error in data["detail"]:
                if isinstance(error, dict) and "msg" in error:
                    error["msg"] = message(error["msg"])
        return data
    if path == "/api/categories":
        for item in data:
            item["name"] = CATEGORIES.get(item["slug"], item["name"])
    elif path == "/api/cities":
        for item in data:
            item["name"] = CITIES.get(item["slug"], item["name"])
    elif path == "/api/places":
        for item in data.get("items", []):
            place(item)
    elif re.fullmatch(r"/api/places/[^/]+", path):
        place(data.get("place"))
    elif path == "/api/route-templates":
        for item in data["items"]:
            overlay(item, "templates")
            route(item)
    elif path == "/api/offline-guide":
        localize("/api/cities", data["cities"])
        localize("/api/categories", data["categories"])
        localize("/api/places", {"items": data["places"]})
        localize("/api/route-templates", {"items": data["templates"]})
    elif path == "/api/events":
        for item in data["items"]:
            overlay(item, "events")
            source = CATALOG["places"].get(item.get("place_slug"))
            if source and item.get("place_name") == source["source"]["name"]:
                item["place_name"] = source["en"]["name"]
    elif path == "/api/journal":
        for item in data.get("items", []):
            place(item)
    elif path == "/api/day-plans":
        day_plan(data)
    elif path == "/api/route-estimate":
        metrics(data)
    elif re.fullmatch(r"/api/routes/\d+/budget(?:/\d+)?", path):
        for category in data.get("summary", {}).get("categories", []):
            category["label"] = message(category["label"])
    elif re.fullmatch(r"/api/routes/\d+/trip", path):
        for item in data.get("stops", []):
            place(item)
        place(data.get("next_stop"))
        data["estimate_note"] = message(data.get("estimate_note", ""))
    elif path == "/api/routes":
        for item in data.get("items", [data]):
            route(item)
    elif re.fullmatch(r"/api/routes/\d+", path) or path.startswith("/api/shared-routes/"):
        route(data)
    elif re.fullmatch(r"/api/routes/\d+/share", path) and "note" in data:
        data["note"] = message(data["note"])
    return data


class LanguageMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            return await self.app(scope, receive, send)
        from starlette.requests import Request
        selected = language(Request(scope))
        start, chunks = None, []

        async def localized_send(event):
            nonlocal start
            if event["type"] == "http.response.start":
                start = event.copy()
                return
            if event["type"] != "http.response.body":
                return await send(event)
            chunks.append(event.get("body", b""))
            if event.get("more_body"):
                return
            body = b"".join(chunks)
            headers = list(start["headers"])
            if selected == "en" and body and any(k.lower() == b"content-type" and b"application/json" in v for k, v in headers):
                data = localize(scope["path"], json.loads(body), start["status"])
                body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            vary = next((v.decode("latin-1") for k, v in headers if k.lower() == b"vary"), "")
            if "accept-language" not in vary.lower():
                vary = ", ".join(filter(None, (vary, "Accept-Language")))
            headers = [(k, v) for k, v in headers if k.lower() not in (b"content-length", b"content-language", b"vary")]
            headers += [(b"content-length", str(len(body)).encode()), (b"content-language", selected.encode()), (b"vary", vary.encode("latin-1"))]
            start["headers"] = headers
            await send(start)
            await send({"type": "http.response.body", "body": body})

        await self.app(scope, receive, localized_send)
