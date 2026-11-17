"""Private route progress with ordered checkpoints and revision checks."""
from __future__ import annotations
import math
from typing import Literal
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from guide_day_planner import distance_km, known_location


def upgrade_trip_database(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS route_trips (
            route_id INTEGER PRIMARY KEY REFERENCES routes(id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK(status IN ('not_started','active','paused','completed')),
            revision INTEGER NOT NULL DEFAULT 0 CHECK(revision >= 0),
            started_at TEXT, paused_at TEXT, finished_at TEXT, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS route_trip_stops (
            route_id INTEGER NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
            place_id INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
            completed_at TEXT NOT NULL,
            PRIMARY KEY(route_id,place_id)
        );
    """)


class TripAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["start", "pause", "resume", "complete_stop", "undo_stop", "restart"]
    expected_revision: int = Field(ge=0, strict=True)
    place_slug: str | None = Field(default=None, min_length=3, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    @model_validator(mode="after")
    def checkpoint_required(self):
        if (self.action in ("complete_stop", "undo_stop")) != (self.place_slug is not None):
            raise ValueError("Durak işlemi için geçerli bir durak seç; diğer işlemlerde durak gönderme.")
        return self


def effective_status(stored, total, completed):
    if stored == "not_started":
        return stored
    if total and completed == total:
        return "completed"
    if not total or stored == "completed":
        return "paused"
    return stored


def sync_trip_progress(db, route_id, now):
    """Keep matching checkpoints on route edits; remove only deleted stops."""
    db.execute("DELETE FROM route_trip_stops WHERE route_id=? AND place_id NOT IN (SELECT place_id FROM route_places WHERE route_id=?)", (route_id, route_id))
    row = db.execute("SELECT * FROM route_trips WHERE route_id=?", (route_id,)).fetchone()
    if row is None:
        return
    total = db.execute("SELECT COUNT(*) FROM route_places WHERE route_id=?", (route_id,)).fetchone()[0]
    completed = db.execute("SELECT COUNT(*) FROM route_trip_stops WHERE route_id=?", (route_id,)).fetchone()[0]
    state = effective_status(row["status"], total, completed)
    db.execute("UPDATE route_trips SET status=?, revision=revision+1, paused_at=?, finished_at=?, updated_at=? WHERE route_id=?",
               (state, (row["paused_at"] or now) if state == "paused" else None,
                (row["finished_at"] or now) if state == "completed" else None, now, route_id))


def owned_route(db, route_id, user_id):
    row = db.execute("SELECT id,title FROM routes WHERE id=? AND user_id=?", (route_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(404, "Rota bulunamadı.")
    return row


def trip_data(db, route, core):
    stored = db.execute("SELECT * FROM route_trips WHERE route_id=?", (route["id"],)).fetchone()
    marks = {row["place_id"]: row["completed_at"] for row in db.execute("SELECT place_id,completed_at FROM route_trip_stops WHERE route_id=?", (route["id"],))}
    rows = db.execute(core._place_select() + " JOIN route_places rp ON rp.place_id=p.id WHERE rp.route_id=? GROUP BY p.id ORDER BY rp.position", (route["id"],)).fetchall()
    stops = [{**core._as_place(row), "number": index + 1, "completed": row["id"] in marks, "completed_at": marks.get(row["id"])} for index, row in enumerate(rows)]
    remaining = [stop for stop in stops if not stop["completed"]]
    done = len(stops) - len(remaining)
    state = effective_status(stored["status"] if stored else "not_started", len(stops), done)
    visit = sum(stop.get("visit_minutes") or 90 for stop in remaining)
    travel_path = remaining[:]
    if remaining and remaining[0]["number"] > 1:
        travel_path.insert(0, stops[remaining[0]["number"] - 2])
    legs = list(zip(travel_path, travel_path[1:]))
    transfer = sum(math.ceil(distance_km(a, b) * 1.5 / 4 * 60) + 5 for a, b in legs) if all(known_location(a) and known_location(b) for a, b in legs) else None
    return {"route_id": route["id"], "title": route["title"], "status": state,
            "revision": stored["revision"] if stored else 0,
            "started_at": stored["started_at"] if stored else None,
            "paused_at": stored["paused_at"] if stored else None,
            "finished_at": stored["finished_at"] if stored else None,
            "stops": stops, "next_stop": remaining[0] if remaining else None,
            "summary": {"completed_count": done, "total_count": len(stops), "remaining_count": len(remaining),
                        "completed_percent": round(done / len(stops) * 100) if stops else 0,
                        "remaining_visit_minutes": visit, "estimated_transfer_minutes": transfer,
                        "remaining_estimated_minutes": visit + transfer if transfer is not None else None},
            "estimate_note": "Ziyaret süreleri öneridir. Geçişler kuş uçuşu mesafeden türetilen tahminlerdir; gerçek yürüyüş yolu değildir. Mevcut konumundan ilk durağa ulaşım, molalar ve dönüş dahil değildir. Gezi ilerlemesi durakları elle tamamladığında güncellenir."}


def install_trip(app, core):
    @app.get("/api/routes/{route_id}/trip")
    def get_trip(route_id: int, request: Request):
        user = core.require_user(request)
        with core.db_session() as db:
            return trip_data(db, owned_route(db, route_id, user["id"]), core)

    @app.post("/api/routes/{route_id}/trip")
    def update_trip(route_id: int, payload: TripAction, request: Request):
        core.check_origin(request)
        user = core.require_user(request)
        with core.db_session() as db:
            db.execute("BEGIN IMMEDIATE")
            route = owned_route(db, route_id, user["id"])
            current = trip_data(db, route, core)
            if payload.expected_revision != current["revision"]:
                raise HTTPException(409, "Gezi ilerlemesi veya rota başka bir yerde güncellendi. Son durumu yükleyip tekrar dene.")
            if not current["stops"]:
                raise HTTPException(422, "Bu rotada durak kalmamış. Önce rotanı düzenle.")
            state = current["status"]
            action = payload.action
            now = core.utc_now()
            started, paused, finished = current["started_at"], current["paused_at"], current["finished_at"]
            if action == "start":
                if state == "active":
                    return current
                if state != "not_started":
                    raise HTTPException(409, "Başlamış bir geziye devam et veya onaylayarak baştan başlat.")
                state, started, paused, finished = "active", now, None, None
            elif action == "restart":
                db.execute("DELETE FROM route_trip_stops WHERE route_id=?", (route_id,))
                state, started, paused, finished = "active", now, None, None
            elif action == "pause":
                if state == "paused":
                    return current
                if state != "active":
                    raise HTTPException(409, "Yalnızca devam eden bir geziye mola verebilirsin.")
                state, paused = "paused", now
            elif action == "resume":
                if state == "active":
                    return current
                if state != "paused":
                    raise HTTPException(409, "Önce geziyi başlat veya tamamlanan geziyi baştan başlat.")
                state, paused, finished = "active", None, None
            elif action == "complete_stop":
                if state != "active":
                    raise HTTPException(409, "Durağı tamamlamak için geziyi başlat veya devam ettir.")
                if current["next_stop"]["slug"] != payload.place_slug:
                    raise HTTPException(409, "Sıradaki durak değişti. Güncel geziyi yükleyip tekrar dene.")
                stop = current["next_stop"]
                db.execute("INSERT INTO route_trip_stops(route_id,place_id,completed_at) VALUES(?,?,?)", (route_id, stop["id"], now))
                if current["summary"]["remaining_count"] == 1:
                    state, finished = "completed", now
            elif action == "undo_stop":
                stop = next((item for item in current["stops"] if item["slug"] == payload.place_slug and item["completed"]), None)
                if stop is None:
                    raise HTTPException(422, "Yalnızca bu rotada tamamlanan bir durağı geri alabilirsin.")
                db.execute("DELETE FROM route_trip_stops WHERE route_id=? AND place_id=?", (route_id, stop["id"]))
                if state == "completed":
                    state, paused, finished = "paused", now, None
            db.execute("""INSERT INTO route_trips(route_id,status,revision,started_at,paused_at,finished_at,updated_at)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(route_id) DO UPDATE SET status=excluded.status,
                revision=excluded.revision, started_at=excluded.started_at, paused_at=excluded.paused_at,
                finished_at=excluded.finished_at, updated_at=excluded.updated_at""",
                (route_id, state, current["revision"] + 1, started, paused, finished, now))
            return trip_data(db, route, core)
