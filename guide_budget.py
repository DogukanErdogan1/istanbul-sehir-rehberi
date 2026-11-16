"""Private, route-owned trip budgets. Amounts are stored as integer kurus."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

CATEGORIES = {
    "transport": "Ulaşım",
    "food": "Yeme içme",
    "tickets": "Giriş ve bilet",
    "accommodation": "Konaklama",
    "other": "Diğer",
}
MAX_ITEMS = 200


def upgrade_budget_database(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS route_budget_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_id INTEGER NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            category TEXT NOT NULL CHECK(category IN ('transport','food','tickets','accommodation','other')),
            planned_kurus INTEGER NOT NULL CHECK(planned_kurus BETWEEN 0 AND 999999999),
            spent_kurus INTEGER NOT NULL CHECK(spent_kurus BETWEEN 0 AND 999999999),
            spent_on TEXT,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_budget_route ON route_budget_items(route_id);
    """)


class BudgetItemWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=2, max_length=80)
    category: Literal["transport", "food", "tickets", "accommodation", "other"]
    planned_amount: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("9999999.99"), max_digits=9, decimal_places=2, allow_inf_nan=False)
    spent_amount: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("9999999.99"), max_digits=9, decimal_places=2, allow_inf_nan=False)
    spent_on: date | None = None
    notes: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def require_amount(self):
        if self.planned_amount == 0 and self.spent_amount == 0:
            raise ValueError("Planlanan veya harcanan tutardan biri sıfırdan büyük olmalı.")
        return self


def owned_route(db, route_id, user_id):
    row = db.execute("SELECT id, title FROM routes WHERE id=? AND user_id=?", (route_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(404, "Rota bulunamadı.")
    return row


def budget_data(db, route):
    items = [dict(row) for row in db.execute(
        "SELECT id,title,category,planned_kurus,spent_kurus,spent_on,notes,created_at,updated_at "
        "FROM route_budget_items WHERE route_id=? ORDER BY id DESC", (route["id"],)
    ).fetchall()]
    categories = []
    for key, label in CATEGORIES.items():
        matching = [item for item in items if item["category"] == key]
        planned = sum(item["planned_kurus"] for item in matching)
        spent = sum(item["spent_kurus"] for item in matching)
        categories.append({"category": key, "label": label, "planned_kurus": planned,
                           "spent_kurus": spent, "remaining_kurus": planned - spent, "item_count": len(matching)})
    planned = sum(item["planned_kurus"] for item in items)
    spent = sum(item["spent_kurus"] for item in items)
    return {"route_id": route["id"], "route_title": route["title"], "currency": "TRY", "items": items,
            "summary": {"planned_kurus": planned, "spent_kurus": spent, "remaining_kurus": planned - spent,
                        "categories": categories}}


def install_budget(app, core):
    @app.get("/api/routes/{route_id}/budget")
    def get_budget(route_id: int, request: Request):
        user = core.require_user(request)
        with core.db_session() as db:
            return budget_data(db, owned_route(db, route_id, user["id"]))

    @app.post("/api/routes/{route_id}/budget", status_code=201)
    def create_item(route_id: int, payload: BudgetItemWrite, request: Request):
        core.check_origin(request)
        user = core.require_user(request)
        with core.db_session() as db:
            route = owned_route(db, route_id, user["id"])
            if db.execute("SELECT COUNT(*) FROM route_budget_items WHERE route_id=?", (route_id,)).fetchone()[0] >= MAX_ITEMS:
                raise HTTPException(422, "Bir rotaya en fazla 200 bütçe kalemi ekleyebilirsin.")
            now = core.utc_now()
            db.execute("""INSERT INTO route_budget_items
                (route_id,title,category,planned_kurus,spent_kurus,spent_on,notes,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)""", (route_id, payload.title, payload.category,
                int(payload.planned_amount * 100), int(payload.spent_amount * 100),
                payload.spent_on.isoformat() if payload.spent_on else None, payload.notes, now, now))
            return budget_data(db, route)

    @app.put("/api/routes/{route_id}/budget/{item_id}")
    def update_item(route_id: int, item_id: int, payload: BudgetItemWrite, request: Request):
        core.check_origin(request)
        user = core.require_user(request)
        with core.db_session() as db:
            route = owned_route(db, route_id, user["id"])
            changed = db.execute("""UPDATE route_budget_items SET title=?,category=?,planned_kurus=?,spent_kurus=?,
                spent_on=?,notes=?,updated_at=? WHERE id=? AND route_id=?""", (payload.title, payload.category,
                int(payload.planned_amount * 100), int(payload.spent_amount * 100),
                payload.spent_on.isoformat() if payload.spent_on else None, payload.notes, core.utc_now(), item_id, route_id)).rowcount
            if not changed:
                raise HTTPException(404, "Bütçe kalemi bulunamadı.")
            return budget_data(db, route)

    @app.delete("/api/routes/{route_id}/budget/{item_id}")
    def delete_item(route_id: int, item_id: int, request: Request):
        core.check_origin(request)
        user = core.require_user(request)
        with core.db_session() as db:
            route = owned_route(db, route_id, user["id"])
            if not db.execute("DELETE FROM route_budget_items WHERE id=? AND route_id=?", (item_id, route_id)).rowcount:
                raise HTTPException(404, "Bütçe kalemi bulunamadı.")
            return budget_data(db, route)
