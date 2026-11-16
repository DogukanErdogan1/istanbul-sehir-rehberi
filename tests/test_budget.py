"""Trip budget persistence, exact totals and ownership boundaries."""
import atexit
import os
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

_boot = tempfile.TemporaryDirectory()
atexit.register(_boot.cleanup)
os.environ["GUIDE_DB_PATH"] = str(Path(_boot.name) / "bootstrap.db")
import main


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous_db = main.DB_PATH
        main.DB_PATH = Path(self.temp.name) / "guide.db"
        main.initialize_database()
        self.owner = TestClient(main.app)
        self.other = TestClient(main.app)
        self.guest = TestClient(main.app)
        for client, email in ((self.owner, "owner@example.com"), (self.other, "other@example.com")):
            self.assertEqual(client.post("/api/auth/register", json={"name": "Gezgin", "email": email, "password": "budget-password-123"}).status_code, 201)
        result = self.owner.post("/api/routes", json={"title": "Gezi planı", "notes": "", "place_slugs": ["pera-muzesi", "galata-kulesi"]})
        self.route_id = result.json()["id"]
        self.url = f"/api/routes/{self.route_id}/budget"
        self.payload = {"title": "Müze bileti", "category": "tickets", "planned_amount": "120.10", "spent_amount": "135.20", "spent_on": "2026-11-16", "notes": "Özel bütçe notum"}

    def tearDown(self):
        for client in (self.owner, self.other, self.guest):
            client.close()
        main.DB_PATH = self.previous_db
        self.temp.cleanup()

    def create(self, **overrides):
        result = self.owner.post(self.url, json={**self.payload, **overrides})
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def test_crud_exact_totals_and_overspend(self):
        data = self.create()
        item_id = data["items"][0]["id"]
        self.assertEqual(data["summary"]["planned_kurus"], 12010)
        self.assertEqual(data["summary"]["spent_kurus"], 13520)
        self.assertEqual(data["summary"]["remaining_kurus"], -1510)
        self.create(category="food", planned_amount="0.10", spent_amount="0.20")
        data = self.create(category="food", planned_amount="0.20", spent_amount="0.10")
        food = next(row for row in data["summary"]["categories"] if row["category"] == "food")
        self.assertEqual((food["planned_kurus"], food["spent_kurus"]), (30, 30))
        result = self.owner.put(f"{self.url}/{item_id}", json={**self.payload, "title": "Güncel bilet", "spent_amount": "100.00", "spent_on": None})
        self.assertEqual(result.status_code, 200)
        item = next(row for row in result.json()["items"] if row["id"] == item_id)
        self.assertEqual(item["spent_kurus"], 10000)
        self.assertIsNone(item["spent_on"])
        self.assertEqual(self.owner.delete(f"{self.url}/{item_id}").status_code, 200)
        self.assertEqual(self.owner.delete(f"{self.url}/{item_id}").status_code, 404)
        self.assertEqual(self.owner.get(self.url).json()["summary"]["spent_kurus"], 30)

    def test_guest_and_other_user_cannot_access_or_change_budget(self):
        item_id = self.create()["items"][0]["id"]
        for client, expected in ((self.guest, 401), (self.other, 404)):
            for method, path, body in (("GET", self.url, None), ("POST", self.url, self.payload), ("PUT", f"{self.url}/{item_id}", self.payload), ("DELETE", f"{self.url}/{item_id}", None)):
                with self.subTest(method=method, expected=expected):
                    self.assertEqual(client.request(method, path, **({"json": body} if body else {})).status_code, expected)
        self.assertEqual(self.owner.get(self.url).json()["summary"]["spent_kurus"], 13520)

    def test_item_cannot_be_moved_between_routes(self):
        item_id = self.create()["items"][0]["id"]
        second = self.owner.post("/api/routes", json={"title": "İkinci gezi", "place_slugs": ["galata-kulesi", "pera-muzesi"]}).json()["id"]
        url = f"/api/routes/{second}/budget/{item_id}"
        self.assertEqual(self.owner.put(url, json=self.payload).status_code, 404)
        self.assertEqual(self.owner.delete(url).status_code, 404)

    def test_validation_rejects_bad_amounts_categories_and_dates(self):
        invalid = [{"planned_amount": "-1"}, {"spent_amount": "0.001"}, {"planned_amount": "10000000"}, {"planned_amount": "NaN"}, {"planned_amount": "Infinity"}, {"category": "unknown"}, {"title": "  "}, {"notes": "x" * 301}, {"spent_on": "2026-02-30"}, {"planned_amount": "0", "spent_amount": "0"}]
        for override in invalid:
            with self.subTest(override=override):
                self.assertEqual(self.owner.post(self.url, json={**self.payload, **override}).status_code, 422)
        self.assertEqual(self.owner.get(self.url).json()["items"], [])
        self.create(planned_amount="0", spent_amount="0.01")

    def test_budget_survives_repeat_migration_and_route_delete_cascades(self):
        self.create()
        main.initialize_database()
        main.initialize_database()
        self.assertEqual(self.owner.get(self.url).json()["summary"]["planned_kurus"], 12010)
        self.assertEqual(self.owner.delete(f"/api/routes/{self.route_id}").status_code, 204)
        with main.db_session() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM route_budget_items").fetchone()[0], 0)

    def test_shared_route_does_not_expose_budget(self):
        self.create()
        path = self.owner.post(f"/api/routes/{self.route_id}/share").json()["path"]
        result = self.guest.get("/api/shared-routes/" + path.rsplit("/", 1)[1])
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("Özel bütçe notum", result.text)
        self.assertNotIn("planned_kurus", result.text)
        self.assertNotIn("13520", result.text)

    def test_large_amounts_and_item_limit(self):
        data = self.create(planned_amount="9999999.99", spent_amount="9999999.99")
        self.assertEqual(data["summary"]["planned_kurus"], 999999999)
        with main.db_session() as db:
            db.executemany("INSERT INTO route_budget_items(route_id,title,category,planned_kurus,spent_kurus,created_at,updated_at) VALUES(?, 'Kalem', 'other', 100, 0, 'now', 'now')", [(self.route_id,)] * 199)
        self.assertEqual(self.owner.post(self.url, json=self.payload).status_code, 422)
        self.assertEqual(len(self.owner.get(self.url).json()["items"]), 200)

    def test_foreign_origin_cannot_write(self):
        item_id = self.create()["items"][0]["id"]
        headers = {"Origin": "https://untrusted.example"}
        for method, path, body in (("POST", self.url, self.payload), ("PUT", f"{self.url}/{item_id}", self.payload), ("DELETE", f"{self.url}/{item_id}", None)):
            self.assertEqual(self.owner.request(method, path, headers=headers, **({"json": body} if body else {})).status_code, 403)


if __name__ == "__main__":
    unittest.main()
