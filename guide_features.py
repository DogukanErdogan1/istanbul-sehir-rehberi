"""City catalog migration, private journals, shared routes and walking estimates."""
from __future__ import annotations

import json
import math
import os
import secrets
import threading
import time
from datetime import date
from urllib.parse import urlencode, urlparse
from urllib.request import Request as UrlRequest, urlopen

from fastapi import HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, model_validator

from guide_catalog import CITIES, EVENTS, NEW_PLACES, PLACE_META, ROUTE_TEMPLATES


META_COLUMNS = {
    "city_slug": "TEXT NOT NULL DEFAULT 'istanbul'", "latitude": "REAL", "longitude": "REAL",
    "visit_minutes": "INTEGER NOT NULL DEFAULT 90", "indoor": "INTEGER", "family_friendly": "INTEGER",
    "wheelchair_accessible": "INTEGER", "accessibility_note": "TEXT NOT NULL DEFAULT ''",
    "source_url": "TEXT NOT NULL DEFAULT ''",
}


def upgrade_database(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS cities (slug TEXT PRIMARY KEY, name TEXT NOT NULL, latitude REAL NOT NULL,
            longitude REAL NOT NULL, zoom INTEGER NOT NULL DEFAULT 12);
        CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS journal (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            place_id INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
            visited_on TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL,
            PRIMARY KEY(user_id, place_id));
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
            city_slug TEXT NOT NULL REFERENCES cities(slug), place_id INTEGER REFERENCES places(id) ON DELETE SET NULL,
            start_date TEXT NOT NULL, end_date TEXT NOT NULL, description TEXT NOT NULL,
            source_url TEXT NOT NULL, source_name TEXT NOT NULL, verified_on TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_events_dates ON events(city_slug, start_date, end_date);
    """)
    for city in CITIES:
        db.execute("INSERT OR IGNORE INTO cities(slug,name,latitude,longitude,zoom) VALUES(:slug,:name,:latitude,:longitude,:zoom)", city)
    columns = {row["name"] for row in db.execute("PRAGMA table_info(places)")}
    for name, kind in META_COLUMNS.items():
        if name not in columns:
            db.execute(f"ALTER TABLE places ADD COLUMN {name} {kind}")
    if "share_token" not in {row["name"] for row in db.execute("PRAGMA table_info(routes)")}:
        db.execute("ALTER TABLE routes ADD COLUMN share_token TEXT")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_routes_share ON routes(share_token) WHERE share_token IS NOT NULL")
    db.execute("CREATE INDEX IF NOT EXISTS idx_places_city ON places(city_slug)")
    if db.execute("SELECT 1 FROM schema_migrations WHERE name='guide-v2-catalog'").fetchone():
        return
    categories = {row["slug"]: row["id"] for row in db.execute("SELECT id,slug FROM categories")}
    for place in NEW_PLACES:
        values = {**place, "category_id": categories[place.get("category", place.get("category_slug"))]}
        db.execute("""INSERT OR IGNORE INTO places(slug,name,category_id,district,address,summary,description,
            duration,best_for,art,featured) VALUES(:slug,:name,:category_id,:district,:address,:summary,
            :description,:duration,:best_for,:art,:featured)""", values)
    all_meta = {**PLACE_META}
    for place in NEW_PLACES:
        all_meta.setdefault(place["slug"], {key: place[key] for key in META_COLUMNS if key in place})
    for slug, meta in all_meta.items():
        fields = {key: meta[key] for key in META_COLUMNS if key in meta}
        if fields:
            db.execute("UPDATE places SET " + ",".join(key + "=?" for key in fields) + " WHERE slug=?", [*fields.values(), slug])
    for event in EVENTS:
        values = {**event, "place_slug": event.get("place_slug")}
        db.execute("""INSERT OR IGNORE INTO events(slug,title,city_slug,place_id,start_date,end_date,
            description,source_url,source_name,verified_on) VALUES(:slug,:title,:city_slug,
            (SELECT id FROM places WHERE slug=:place_slug),:start_date,:end_date,:description,
            :source_url,:source_name,:verified_on)""", values)
    db.execute("INSERT INTO schema_migrations(name) VALUES('guide-v2-catalog')")


def route_metrics(places):
    visit = sum(place.get("visit_minutes") or 90 for place in places)
    known = all(place.get("latitude") is not None and place.get("longitude") is not None for place in places)
    legs = []
    if known:
        for a, b in zip(places, places[1:]):
            lat1, lat2 = math.radians(a["latitude"]), math.radians(b["latitude"])
            dl = math.radians(b["latitude"] - a["latitude"])
            dn = math.radians(b["longitude"] - a["longitude"])
            h = math.sin(dl / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dn / 2) ** 2
            distance = 6371.0088 * 2 * math.asin(math.sqrt(min(1, max(0, h))))
            legs.append({"from": a["name"], "to": b["name"], "distance_km": round(distance, 3)})
    return {
        "distance_km": round(sum(leg["distance_km"] for leg in legs), 2) if known else None,
        "distance_kind": "straight_line", "walking_minutes": None, "visit_minutes": visit,
        "total_minutes": None, "legs": legs,
        "geometry": [[p["longitude"], p["latitude"]] for p in places] if known else [],
        "note": "Kuş uçuşu mesafe; yürünebilir yol değildir. Ziyaret süreleri öneridir." if known else "Bazı durakların konumu eksik; mesafe hesaplanamadı.",
    }


_route_cache = {}
_route_lock = threading.Lock()
_last_request = 0.0


def walking_estimate(places):
    global _last_request
    base = route_metrics(places)
    if len(places) < 2 or not base["geometry"]:
        return base
    coords = ";".join(f"{p['longitude']:.6f},{p['latitude']:.6f}" for p in places)
    endpoint = os.environ.get("GUIDE_ROUTING_URL", "https://routing.openstreetmap.de/routed-foot/route/v1/driving/")
    if not endpoint:
        return {**base, "note": "Yürüyüş hizmeti kapalı. Gösterilen mesafe kuş uçuşudur."}
    with _route_lock:
        cached = _route_cache.get(coords)
        if cached and cached[0] > time.monotonic():
            live = cached[1]
        else:
            if time.monotonic() - _last_request < 1:
                return {**base, "note": "Yürüyüş hesabı için bir saniye sonra yeniden dene. Şimdilik kuş uçuşu mesafe gösteriliyor."}
            _last_request = time.monotonic()
            try:
                url = endpoint.rstrip("/") + "/" + coords + "?" + urlencode({"overview": "full", "geometries": "geojson", "steps": "false"})
                with urlopen(UrlRequest(url, headers={"User-Agent": "SehirArasiLocalGuide/2.0 (educational city guide)"}), timeout=6) as response:
                    result = json.loads(response.read(2_000_000))
                if result.get("code") != "Ok" or not result.get("routes"):
                    raise ValueError("Route unavailable")
                route = result["routes"][0]
                live = {"distance_km": round(route["distance"] / 1000, 2), "walking_minutes": math.ceil(route["duration"] / 60),
                        "geometry": route["geometry"]["coordinates"], "distance_kind": "walking",
                        "legs": [{"from": a["name"], "to": b["name"], "distance_km": round(leg["distance"] / 1000, 2), "walking_minutes": math.ceil(leg["duration"] / 60)} for a, b, leg in zip(places, places[1:], route["legs"])]}
                if len(_route_cache) >= 256:
                    _route_cache.pop(next(iter(_route_cache)))
                _route_cache[coords] = (time.monotonic() + 86400, live)
            except (OSError, ValueError, KeyError, IndexError, TypeError):
                return {**base, "note": "Yürüyüş hizmetine ulaşılamadı veya yol bulunamadı. Gösterilen mesafe kuş uçuşudur."}
    return {**base, **live, "total_minutes": base["visit_minutes"] + live["walking_minutes"],
            "note": "OSRM / FOSSGIS yürüyüş yolu. Süreler tahminidir; mola ve ziyaret süreleri değişebilir."}


class EstimateWrite(BaseModel):
    place_slugs: list[str] = Field(min_length=1, max_length=12)
    walking: bool = False


class JournalWrite(BaseModel):
    visited_on: date
    notes: str = Field(default="", max_length=1500)

    @model_validator(mode="after")
    def valid_day(self):
        if self.visited_on > date.today():
            raise ValueError("Ziyaret tarihi gelecekte olamaz.")
        return self


class EventWrite(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=3, max_length=100)
    title: str = Field(min_length=3, max_length=150)
    city_slug: str = Field(max_length=40)
    place_slug: str | None = Field(default=None, max_length=80)
    start_date: date
    end_date: date
    description: str = Field(min_length=10, max_length=1500)
    source_url: str = Field(max_length=700)
    source_name: str = Field(min_length=2, max_length=100)
    verified_on: date

    @model_validator(mode="after")
    def valid_event(self):
        self.title = self.title.strip()
        self.description = self.description.strip()
        self.source_name = self.source_name.strip()
        self.source_url = self.source_url.strip()
        if len(self.title) < 3 or len(self.description) < 10 or len(self.source_name) < 2:
            raise ValueError("Etkinlik adı, açıklaması ve kaynak kurumu doldurulmalı.")
        if self.end_date < self.start_date:
            raise ValueError("Bitiş tarihi başlangıçtan önce olamaz.")
        if self.verified_on > date.today():
            raise ValueError("Doğrulama tarihi gelecekte olamaz.")
        if urlparse(self.source_url).scheme not in ("https", "http") or not urlparse(self.source_url).netloc:
            raise ValueError("Geçerli bir resmî kaynak bağlantısı gir.")
        return self


def install_features(app, core):
    def validate_city(db, slug):
        if not db.execute("SELECT 1 FROM cities WHERE slug=?", (slug,)).fetchone():
            raise HTTPException(422, "Geçerli bir şehir seç.")

    def load_places(db, slugs):
        core.route_place_ids(db, slugs)
        rows = db.execute(core._place_select() + " WHERE p.slug IN (" + ",".join("?" for _ in slugs) + ") GROUP BY p.id", slugs).fetchall()
        lookup = {row["slug"]: core._as_place(row) for row in rows}
        return [lookup[slug] for slug in slugs]

    @app.get("/r/{token}", include_in_schema=False)
    def shared_page(token: str):
        return core.home()

    @app.get("/api/cities")
    def cities():
        with core.db_session() as db:
            return [dict(row) for row in db.execute("SELECT c.*,COUNT(p.id) AS place_count FROM cities c LEFT JOIN places p ON p.city_slug=c.slug GROUP BY c.slug ORDER BY CASE c.slug WHEN 'istanbul' THEN 0 WHEN 'ankara' THEN 1 ELSE 2 END")]

    @app.get("/api/route-templates")
    def templates(city: str = "istanbul"):
        items = []
        with core.db_session() as db:
            validate_city(db, city)
            for template in ROUTE_TEMPLATES:
                if template["city_slug"] != city:
                    continue
                available = {row["slug"] for row in db.execute("SELECT slug FROM places WHERE city_slug=?", (city,))}
                slugs = [slug for slug in template["place_slugs"] if slug in available]
                if not slugs:
                    continue
                places = load_places(db, slugs)
                items.append({**template, "places": places, "metrics": route_metrics(places)})
        return {"items": items}

    @app.post("/api/route-estimate")
    def estimate(payload: EstimateWrite):
        with core.db_session() as db:
            places = load_places(db, payload.place_slugs)
        if len({place["city_slug"] for place in places}) > 1:
            raise HTTPException(422, "Yürüyüş rotası için aynı şehirdeki durakları seç.")
        return walking_estimate(places) if payload.walking else route_metrics(places)

    @app.post("/api/routes/{route_id}/share")
    def share_route(route_id: int, request: Request):
        core.check_origin(request)
        user = core.require_user(request)
        with core.db_session() as db:
            row = db.execute("SELECT share_token FROM routes WHERE id=? AND user_id=?", (route_id, user["id"])).fetchone()
            if row is None:
                raise HTTPException(404, "Rota bulunamadı.")
            token = row["share_token"] or secrets.token_urlsafe(24)
            db.execute("UPDATE routes SET share_token=? WHERE id=?", (token, route_id))
        return {"path": "/r/" + token, "note": "Bağlantıyı bilenler rota adını ve durakları görebilir. Özel notların paylaşılmaz."}

    @app.delete("/api/routes/{route_id}/share", status_code=204)
    def revoke_share(route_id: int, request: Request):
        core.check_origin(request)
        user = core.require_user(request)
        with core.db_session() as db:
            if not db.execute("UPDATE routes SET share_token=NULL WHERE id=? AND user_id=?", (route_id, user["id"])).rowcount:
                raise HTTPException(404, "Rota bulunamadı.")
        return Response(status_code=204)

    @app.get("/api/shared-routes/{token}")
    def get_shared(token: str):
        if len(token) > 64:
            raise HTTPException(404, "Paylaşılan rota bulunamadı.")
        with core.db_session() as db:
            row = db.execute("SELECT id,title FROM routes WHERE share_token=?", (token,)).fetchone()
            if row is None:
                raise HTTPException(404, "Bu bağlantı geçersiz veya paylaşımı kapatılmış.")
            places = [core._as_place(p) for p in db.execute(core._place_select() + " JOIN route_places rp ON rp.place_id=p.id WHERE rp.route_id=? GROUP BY p.id ORDER BY rp.position", (row["id"],))]
        return {"title": row["title"], "places": places, "metrics": route_metrics(places)}

    @app.get("/api/journal")
    def get_journal(request: Request, city: str = ""):
        user = core.require_user(request)
        with core.db_session() as db:
            rows = db.execute("""SELECT p.slug,p.name,p.city_slug,ci.name AS city_name,p.district,
                j.visited_on,j.notes,j.updated_at FROM journal j JOIN places p ON p.id=j.place_id
                JOIN cities ci ON ci.slug=p.city_slug WHERE j.user_id=? AND (?='' OR p.city_slug=?)
                ORDER BY j.visited_on DESC,p.name""", (user["id"], city, city)).fetchall()
        return {"items": [dict(row) for row in rows], "total": len(rows)}

    @app.put("/api/journal/{slug}")
    def save_journal(slug: str, payload: JournalWrite, request: Request):
        core.check_origin(request)
        user = core.require_user(request)
        with core.db_session() as db:
            place = db.execute("SELECT id FROM places WHERE slug=?", (slug,)).fetchone()
            if place is None:
                raise HTTPException(404, "Durak bulunamadı.")
            db.execute("""INSERT INTO journal(user_id,place_id,visited_on,notes,updated_at) VALUES(?,?,?,?,?)
                ON CONFLICT(user_id,place_id) DO UPDATE SET visited_on=excluded.visited_on,
                notes=excluded.notes,updated_at=excluded.updated_at""", (user["id"], place["id"], payload.visited_on.isoformat(), payload.notes.strip(), core.utc_now()))
        return {"saved": True}

    @app.delete("/api/journal/{slug}", status_code=204)
    def remove_journal(slug: str, request: Request):
        core.check_origin(request)
        user = core.require_user(request)
        with core.db_session() as db:
            db.execute("DELETE FROM journal WHERE user_id=? AND place_id=(SELECT id FROM places WHERE slug=?)", (user["id"], slug))
        return Response(status_code=204)

    @app.get("/api/events")
    def events(city: str = "istanbul", start: date | None = None, end: date | None = None, include_past: bool = False):
        if start and end and end < start:
            raise HTTPException(422, "Geçerli bir tarih aralığı seç.")
        where, params = ["e.city_slug=?"], [city]
        if start:
            where.append("e.end_date>=?")
            params.append(start.isoformat())
        if end:
            where.append("e.start_date<=?")
            params.append(end.isoformat())
        if not include_past:
            where.append("e.end_date>=?")
            params.append(date.today().isoformat())
        with core.db_session() as db:
            validate_city(db, city)
            rows = db.execute("SELECT e.*,p.slug AS place_slug,p.name AS place_name FROM events e LEFT JOIN places p ON p.id=e.place_id WHERE " + " AND ".join(where) + " ORDER BY e.start_date,e.id LIMIT 200", params).fetchall()
        return {"items": [dict(row) for row in rows], "today": date.today().isoformat()}

    def event_values(db, payload):
        validate_city(db, payload.city_slug)
        place_id = None
        if payload.place_slug:
            place = db.execute("SELECT id,city_slug FROM places WHERE slug=?", (payload.place_slug,)).fetchone()
            if place is None or place["city_slug"] != payload.city_slug:
                raise HTTPException(422, "Etkinlik durağı aynı şehirde olmalı.")
            place_id = place["id"]
        data = payload.model_dump(mode="json")
        return {**data, "title": payload.title.strip(), "description": payload.description.strip(), "place_id": place_id}

    @app.post("/api/admin/events", status_code=201)
    def add_event(payload: EventWrite, request: Request):
        core.check_origin(request)
        core.require_admin(request)
        with core.db_session() as db:
            values = event_values(db, payload)
            try:
                cursor = db.execute("""INSERT INTO events(slug,title,city_slug,place_id,start_date,end_date,description,
                    source_url,source_name,verified_on) VALUES(:slug,:title,:city_slug,:place_id,:start_date,:end_date,
                    :description,:source_url,:source_name,:verified_on)""", values)
            except core.sqlite3.IntegrityError as error:
                raise HTTPException(409, "Bu etkinlik kısa adı zaten kullanılıyor.") from error
        return {"id": cursor.lastrowid}

    @app.put("/api/admin/events/{event_id}")
    def update_event(event_id: int, payload: EventWrite, request: Request):
        core.check_origin(request)
        core.require_admin(request)
        with core.db_session() as db:
            values = {**event_values(db, payload), "id": event_id}
            try:
                changed = db.execute("""UPDATE events SET slug=:slug,title=:title,city_slug=:city_slug,place_id=:place_id,
                    start_date=:start_date,end_date=:end_date,description=:description,source_url=:source_url,
                    source_name=:source_name,verified_on=:verified_on WHERE id=:id""", values).rowcount
            except core.sqlite3.IntegrityError as error:
                raise HTTPException(409, "Bu etkinlik kısa adı zaten kullanılıyor.") from error
            if not changed:
                raise HTTPException(404, "Etkinlik bulunamadı.")
        return {"saved": True}

    @app.delete("/api/admin/events/{event_id}", status_code=204)
    def delete_event(event_id: int, request: Request):
        core.check_origin(request)
        core.require_admin(request)
        with core.db_session() as db:
            if not db.execute("DELETE FROM events WHERE id=?", (event_id,)).rowcount:
                raise HTTPException(404, "Etkinlik bulunamadı.")
        return Response(status_code=204)
