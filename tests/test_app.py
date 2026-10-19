"""Core API flows, run with: python -m unittest discover -s tests -v"""

import atexit
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


_BOOT_DIR = tempfile.TemporaryDirectory()
atexit.register(_BOOT_DIR.cleanup)
os.environ["GUIDE_DB_PATH"] = str(Path(_BOOT_DIR.name) / "bootstrap.db")

import main  # noqa: E402  (the temporary database path must be set first)


class GuideApiTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        main.DB_PATH = Path(self._temp_dir.name) / "guide.db"
        main.initialize_database()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        self._temp_dir.cleanup()

    def register(self, email="deniz@example.com"):
        return self.client.post(
            "/api/auth/register",
            json={"name": "Deniz Gezgin", "email": email, "password": "guclu-parola-123"},
        )

    def test_public_exploration(self):
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/").status_code, 200)
        places = self.client.get("/api/places").json()
        self.assertEqual(places["total"], 15)
        self.assertEqual(self.client.get("/api/places?category=museum").status_code, 200)
        self.assertTrue(all(item["category_slug"] == "museum" for item in self.client.get("/api/places?category=museum").json()["items"]))
        self.assertEqual(self.client.get("/api/places?q=Galata").json()["items"][0]["slug"], "galata-kulesi")
        self.assertEqual(self.client.get("/api/places/ayasofya").status_code, 200)
        self.assertEqual(self.client.get("/api/places/bilinmeyen").status_code, 404)

    def test_account_favorites_reviews_and_routes(self):
        self.assertEqual(self.client.post("/api/places/ayasofya/reviews", json={"rating": 5, "body": "Çok güzeldi!"}).status_code, 401)
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.client.get("/api/auth/me").json()["user"]["email"], "deniz@example.com")
        self.assertEqual(self.client.post("/api/favorites/ayasofya").status_code, 200)
        self.assertIn("ayasofya", self.client.get("/api/favorites").json()["slugs"])

        review = {"rating": 5, "body": "Mimari detayları çok etkileyiciydi."}
        self.assertEqual(self.client.post("/api/places/ayasofya/reviews", json=review).status_code, 201)
        self.assertTrue(self.client.get("/api/places/ayasofya").json()["user_has_reviewed"])
        self.assertEqual(self.client.post("/api/places/ayasofya/reviews", json=review).status_code, 409)

        route = {"title": "Tarih rotası", "notes": "Sabah erken başla", "place_slugs": ["galata-kulesi", "ayasofya"]}
        created = self.client.post("/api/routes", json=route)
        self.assertEqual(created.status_code, 201)
        route_id = created.json()["id"]
        self.assertEqual([place["slug"] for place in created.json()["places"]], route["place_slugs"])
        updated = self.client.put(f"/api/routes/{route_id}", json={**route, "place_slugs": ["ayasofya", "galata-kulesi"]})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["places"][0]["slug"], "ayasofya")

        other = TestClient(main.app)
        try:
            self.assertEqual(other.post("/api/auth/register", json={"name": "Başka Kullanıcı", "email": "baska@example.com", "password": "guclu-parola-123"}).status_code, 201)
            self.assertEqual(other.put(f"/api/routes/{route_id}", json=route).status_code, 404)
            self.assertEqual(other.get("/api/routes").json()["items"], [])
        finally:
            other.close()

        self.assertEqual(self.client.delete(f"/api/routes/{route_id}").status_code, 204)
        self.assertEqual(self.client.get("/api/routes").json()["items"], [])
        self.assertEqual(self.client.delete("/api/favorites/ayasofya").status_code, 200)
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
        self.assertIsNone(self.client.get("/api/auth/me").json()["user"])

    def test_admin_place_management(self):
        self.register()
        payload = {
            "slug": "ornek-durak", "name": "Örnek Durak", "category_slug": "culture",
            "district": "Karaköy", "address": "Karaköy, İstanbul",
            "summary": "Yeni bir kültür durağını ziyaret et.",
            "description": "Bu durak yönetici paneli ve API işlemlerini doğrulamak için eklendi.",
            "duration": "1 saat", "best_for": "Kültür gezisi", "art": "gallery", "featured": False,
        }
        self.assertEqual(self.client.post("/api/admin/places", json=payload).status_code, 403)
        with main.db_session() as db:
            db.execute("UPDATE users SET role = 'admin' WHERE email = ?", ("deniz@example.com",))
        self.client.post("/api/auth/logout")
        login = self.client.post("/api/auth/login", json={"email": "deniz@example.com", "password": "guclu-parola-123"})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["user"]["role"], "admin")
        self.assertEqual(self.client.post("/api/admin/places", json=payload).status_code, 201)
        self.assertEqual(self.client.post("/api/admin/places", json=payload).status_code, 409)
        updated = self.client.put("/api/admin/places/ornek-durak", json={**payload, "name": "Güncel Durak"})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(self.client.get("/api/places/ornek-durak").json()["place"]["name"], "Güncel Durak")
        self.assertEqual(self.client.delete("/api/admin/places/ornek-durak").status_code, 204)
        self.assertEqual(self.client.get("/api/places/ornek-durak").status_code, 404)

    def test_existing_review_table_is_upgraded(self):
        old_path = Path(self._temp_dir.name) / "old.db"
        db = sqlite3.connect(old_path)
        try:
            db.execute(
                """CREATE TABLE reviews (id INTEGER PRIMARY KEY, place_id INTEGER NOT NULL,
                   author TEXT NOT NULL, rating INTEGER NOT NULL, body TEXT NOT NULL,
                   created_at TEXT NOT NULL)"""
            )
            db.commit()
        finally:
            db.close()
        current_path = main.DB_PATH
        try:
            main.DB_PATH = old_path
            main.initialize_database()
            with main.db_session() as db:
                columns = {row["name"] for row in db.execute("PRAGMA table_info(reviews)")}
            self.assertIn("user_id", columns)
        finally:
            main.DB_PATH = current_path


if __name__ == "__main__":
    unittest.main()
