"""Bounded day itineraries from the local catalog; no external service required."""
from __future__ import annotations

import math
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

Interest = Literal["museum", "history", "view", "nature", "culture"]
CATEGORY_NAMES = {"museum": "Müzeler", "history": "Tarihî yerler", "view": "Manzara", "nature": "Doğa", "culture": "Kültür"}
MAX_LEG_KM = 2.5
BEAM_WIDTH = 72


class DayPlanWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    city: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9-]+$")
    available_minutes: int = Field(default=240, ge=60, le=600, strict=True)
    start_time: str = Field(default="09:00", pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    interests: list[Interest] = Field(min_length=1, max_length=5)
    pace: Literal["balanced", "relaxed"] = "balanced"
    break_minutes: Literal[0, 15, 30, 45, 60] = 30
    indoor_only: bool = False
    family_friendly: bool = False
    accessible_only: bool = False

    @model_validator(mode="after")
    def valid_window(self):
        if len(set(self.interests)) != len(self.interests):
            raise ValueError("İlgi alanlarını yalnızca bir kez seç.")
        if self.break_minutes >= self.available_minutes:
            raise ValueError("Mola süresi ayırdığın toplam süreden kısa olmalı.")
        if clock_minutes(self.start_time) + self.available_minutes >= 1440:
            raise ValueError("Plan aynı gün içinde bitmeli. Başlangıç saatini veya süreyi değiştir.")
        return self


def clock_minutes(value):
    hour, minute = map(int, value.split(":"))
    return hour * 60 + minute


def clock(value):
    return f"{value // 60:02d}:{value % 60:02d}"


def distance_km(a, b):
    lat1, lat2 = math.radians(a["latitude"]), math.radians(b["latitude"])
    delta_lat = lat2 - lat1
    delta_lon = math.radians(b["longitude"] - a["longitude"])
    term = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1, max(0, term))))


def known_location(place):
    lat, lon = place.get("latitude"), place.get("longitude")
    return lat is not None and lon is not None and math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180


def build_day_plan(places, city_name, payload, route_metrics):
    eligible = [p for p in places if p["city_slug"] == payload.city and p["category_slug"] in payload.interests
                and (not payload.indoor_only or p.get("indoor") is True)
                and (not payload.family_friendly or p.get("family_friendly") is True)
                and (not payload.accessible_only or p.get("wheelchair_accessible") is True)]
    located = [p for p in eligible if known_location(p)]
    # Keep a bounded, category-balanced pool as the catalog grows.
    candidates = []
    for category in payload.interests:
        group = sorted((p for p in located if p["category_slug"] == category), key=lambda p: (-bool(p.get("featured")), -float(p.get("average_rating") or 0), p.get("visit_minutes") or 90, p["slug"]))
        candidates.extend(group[:6])
    visits = [math.ceil((p.get("visit_minutes") or 90) * (1.25 if payload.pace == "relaxed" else 1)) for p in candidates]
    limit = 4 if payload.pace == "relaxed" else 6
    transfers = {}
    for i, a in enumerate(candidates):
        for j in range(i + 1, len(candidates)):
            km = distance_km(a, candidates[j])
            if km <= MAX_LEG_KM:
                minutes = math.ceil(km * 1.5 / (3.5 if payload.pace == "relaxed" else 4) * 60) + 5
                transfers[i, j] = transfers[j, i] = (minutes, km)

    def score(path, travel):
        coverage = len({candidates[i]["category_slug"] for i in path})
        quality = sum(4 * bool(candidates[i].get("featured")) + 2 * float(candidates[i].get("average_rating") or 0) for i in path)
        return coverage * 140 + len(path) * 40 + quality + sum(visits[i] for i in path) * .06 - travel * .35

    # A state is (indices, elapsed including the reserved break, transfer minutes).
    beam = [((i,), visit + payload.break_minutes, 0) for i, visit in enumerate(visits) if visit + payload.break_minutes <= payload.available_minutes]
    best = None
    for _ in range(limit):
        if not beam:
            break
        beam = sorted(beam, key=lambda state: (-score(state[0], state[2]), state[1], tuple(candidates[i]["slug"] for i in state[0])))[:BEAM_WIDTH]
        candidate_best = beam[0]
        if best is None or score(candidate_best[0], candidate_best[2]) > score(best[0], best[2]):
            best = candidate_best
        next_states = []
        for path, elapsed, travel in beam:
            if len(path) == limit:
                continue
            for index, visit in enumerate(visits):
                leg = transfers.get((path[-1], index))
                if index in path or leg is None or elapsed + leg[0] + visit > payload.available_minutes:
                    continue
                next_states.append(((*path, index), elapsed + leg[0] + visit, travel + leg[0]))
        beam = next_states

    notes = ["Saatler önerilen ziyaret süreleri ve kuş uçuşu mesafeden türetilen geçiş tahminleridir; gerçek yürüyüş yolu değildir.",
             "Açılış saatleri, kapalı günler ve bilet bilgileri kontrol edilmedi. Gitmeden önce durakların resmî kaynaklarını kontrol et.",
             "Plan ilk durakta başlar; ilk durağa ulaşım ve eve dönüş süresi dahil değildir."]
    if payload.accessible_only:
        notes.append("Erişim filtresi durak bilgilerine dayanır; duraklar arasındaki güzergâhın erişilebilirliği doğrulanmadı.")
    if len(located) < len(eligible):
        notes.append("Konumu eksik duraklar geçiş süresi hesaplanamadığı için plana alınmadı.")
    if not best:
        message = "Bu tercihlere uyan, konumu bilinen bir durak bulamadık. İlgi alanlarını veya ek tercihlerini değiştir." if not located else "Bu süreye sığan bir plan bulamadık. Süreyi artırabilir veya mola payını azaltabilirsin."
        return {"status": "empty", "message": message, "route": None, "schedule": [], "summary": None, "notes": notes}

    path, elapsed, travel = best
    selected = [candidates[i] for i in path]
    schedule = []
    current = clock_minutes(payload.start_time)
    break_after = (len(path) - 1) // 2
    for order, index in enumerate(path):
        if order:
            minutes, _ = transfers[path[order - 1], index]
            schedule.append({"kind": "transfer", "start": clock(current), "end": clock(current + minutes), "minutes": minutes,
                             "title": "Tahmini geçiş", "description": selected[order - 1]["name"] + " → " + candidates[index]["name"]})
            current += minutes
        schedule.append({"kind": "visit", "start": clock(current), "end": clock(current + visits[index]), "minutes": visits[index],
                         "title": candidates[index]["name"], "description": CATEGORY_NAMES[candidates[index]["category_slug"]], "place_slug": candidates[index]["slug"],
                         "source_url": candidates[index].get("source_url") or ""})
        current += visits[index]
        if order == break_after and payload.break_minutes:
            schedule.append({"kind": "break", "start": clock(current), "end": clock(current + payload.break_minutes), "minutes": payload.break_minutes,
                             "title": "Sana ait bir mola", "description": "Yemek, kahve ya da sadece biraz soluklanmak için ayırdığın zaman."})
            current += payload.break_minutes
    covered = {place["category_slug"] for place in selected}
    if set(payload.interests) - covered:
        notes.append("Süre ve yakınlık sınırları nedeniyle seçtiğin ilgi alanlarının tamamına durak eklenemedi.")
    description = f"{city_name} için {payload.start_time}–{clock(current)} arası bir gezi önerisi. Ziyaret ve geçiş süreleri tahminidir."
    route_notes = description + "\n" + " · ".join(f"{entry['start']} {entry['title']}" for entry in schedule if entry["kind"] != "transfer")
    return {"status": "ready", "message": "Günün için bir başlangıç planı hazır.",
            "route": {"title": f"{city_name} · Benim bir günüm", "description": description, "notes": route_notes[:500], "places": selected, "metrics": route_metrics(selected)},
            "schedule": schedule, "summary": {"start_time": payload.start_time, "end_time": clock(current), "total_minutes": elapsed,
                "available_minutes": payload.available_minutes, "free_minutes": payload.available_minutes - elapsed,
                "visit_minutes": sum(visits[i] for i in path), "estimated_transfer_minutes": travel, "break_minutes": payload.break_minutes,
                "stop_count": len(path), "covered_interests": sorted(covered)}, "notes": notes}


def install_day_planner(app, core):
    @app.post("/api/day-plans")
    def day_plan(payload: DayPlanWrite):
        with core.db_session() as db:
            city = db.execute("SELECT name FROM cities WHERE slug=?", (payload.city,)).fetchone()
            if city is None:
                raise HTTPException(422, "Geçerli bir şehir seç.")
            rows = db.execute(core._place_select() + " WHERE p.city_slug=? GROUP BY p.id", (payload.city,)).fetchall()
            places = [core._as_place(row) for row in rows]
        return build_day_plan(places, city["name"], payload, core.route_metrics)
