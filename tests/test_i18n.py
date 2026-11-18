"""Language negotiation, catalog overlays and preservation of personal data."""
import atexit
import os
from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient

_bootstrap = tempfile.TemporaryDirectory()
atexit.register(_bootstrap.cleanup)
os.environ["GUIDE_DB_PATH"] = str(Path(_bootstrap.name) / "bootstrap.db")
import main
from guide_i18n import CATALOG


class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = main.DB_PATH
        main.DB_PATH = Path(self.temp.name) / "guide.db"
        main.initialize_database()
        self.client = TestClient(main.app)
        self.en = {"Accept-Language": "en-GB,en;q=0.9,tr;q=0.5"}

    def tearDown(self):
        self.client.close()
        main.DB_PATH = self.previous
        self.temp.cleanup()

    def sign_in(self):
        result = self.client.post("/api/auth/register", headers=self.en, json={"name": "Giriş yap", "email": "language@example.com", "password": "language-pass-123"})
        self.assertEqual(result.status_code, 201, result.text)
        self.assertTrue(result.headers.get("set-cookie"))
        self.assertEqual(self.client.get("/api/auth/me", headers=self.en).json()["user"]["name"], "Giriş yap")

    def new_route(self):
        self.sign_in()
        result = self.client.post("/api/routes", headers=self.en, json={"title": "Giriş yap", "notes": "Rotalarım", "place_slugs": ["galata-kulesi", "pera-muzesi"]})
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def test_language_priority_and_default(self):
        for suffix, headers, expected in [
            ("", {}, "tr"), ("", self.en, "en"),
            ("?lang=tr", self.en, "tr"), ("?lang=en", {"Accept-Language": "tr"}, "en"),
            ("", {"Accept-Language": "en;q=0.3,tr;q=0.9"}, "tr"),
            ("?lang=invalid", {"Accept-Language": "fr,en;q=0.8"}, "en"),
            ("", {"Accept-Language": "en;q=0,tr;q=1"}, "tr"),
        ]:
            with self.subTest(suffix=suffix, headers=headers):
                response = self.client.get("/api/categories" + suffix, headers=headers)
                self.assertEqual(response.headers["content-language"], expected)
                self.assertIn("Accept-Language", response.headers["vary"])
                self.assertEqual(response.json()[0]["name"], "Museums" if expected == "en" else "Müzeler")

    def test_english_search_and_seeded_catalog(self):
        response = self.client.get("/api/places?q=Basilica&limit=1", headers=self.en)
        self.assertEqual([p["slug"] for p in response.json()["items"]], ["yerebatan-sarnici"])
        self.assertEqual(response.json()["items"][0]["name"], "Basilica Cistern")
        self.assertTrue(self.client.get("/api/places?q=Yerebatan", headers=self.en).json()["items"])
        self.assertTrue(self.client.get("/api/places?city=izmir&q=Izmir", headers=self.en).json()["items"])
        for city in ("istanbul", "ankara", "izmir"):
            rows = self.client.get(f"/api/places?city={city}&sort=az", headers=self.en).json()["items"]
            self.assertTrue(rows)
            for row in rows:
                self.assertEqual(row["summary"], CATALOG["places"][row["slug"]]["en"]["summary"])
                self.assertNotIn("translation_note", row)
        self.assertEqual(self.client.get("/api/places/yerebatan-sarnici").json()["place"]["name"], "Yerebatan Sarnıcı")

    def test_editor_changes_preserved_with_original_for_editor(self):
        with main.db_session() as db:
            db.execute("UPDATE places SET summary=? WHERE slug='galata-kulesi'", ("Giriş yap",))
        row = self.client.get("/api/places/galata-kulesi", headers=self.en).json()["place"]
        self.assertEqual(row["summary"], "Giriş yap")
        self.assertEqual(row["name"], "Galata Tower")
        self.assertEqual(row["original_content"]["name"], "Galata Kulesi")
        self.assertIn("original language", row["translation_note"])

    def test_personal_content_and_trip_survive_language_change(self):
        route = self.new_route()
        rid = route["id"]
        self.assertEqual((route["title"], route["notes"]), ("Giriş yap", "Rotalarım"))
        self.assertEqual(route["places"][0]["name"], "Galata Tower")
        saved = self.client.put("/api/journal/galata-kulesi", headers=self.en, json={"visited_on": "2026-10-19", "notes": "Giriş yap"})
        self.assertEqual(saved.status_code, 200, saved.text)
        journal = self.client.get("/api/journal", headers=self.en).json()["items"][0]
        self.assertEqual((journal["name"], journal["notes"]), ("Galata Tower", "Giriş yap"))
        trip = self.client.post(f"/api/routes/{rid}/trip", headers=self.en, json={"action": "start", "expected_revision": 0}).json()
        self.client.post(f"/api/routes/{rid}/trip", headers=self.en, json={"action": "complete_stop", "place_slug": "galata-kulesi", "expected_revision": trip["revision"]})
        tr = self.client.get(f"/api/routes/{rid}/trip?lang=tr").json()
        en = self.client.get(f"/api/routes/{rid}/trip", headers=self.en).json()
        self.assertEqual(tr["summary"], en["summary"])
        self.assertEqual(tr["revision"], en["revision"])
        self.assertEqual(en["title"], "Giriş yap")
        self.assertEqual(en["stops"][0]["name"], "Galata Tower")
        self.assertEqual(tr["stops"][0]["name"], "Galata Kulesi")
        shared = self.client.post(f"/api/routes/{rid}/share", headers=self.en).json()["path"].split("/")[-1]
        public = self.client.get("/api/shared-routes/" + shared, headers=self.en).json()
        self.assertEqual(public["title"], "Giriş yap")
        self.assertNotIn("notes", public)

    def test_budget_labels_without_converting_amounts_or_personal_text(self):
        rid = self.new_route()["id"]
        result = self.client.post(f"/api/routes/{rid}/budget", headers=self.en, json={"title": "Giriş yap", "notes": "Rotalarım", "category": "food", "planned_amount": "1250.50", "spent_amount": "100"})
        self.assertEqual(result.status_code, 201, result.text)
        budget = result.json()
        self.assertEqual(budget["currency"], "TRY")
        self.assertEqual(budget["summary"]["planned_kurus"], 125050)
        self.assertEqual(budget["items"][0]["title"], "Giriş yap")
        self.assertEqual(budget["items"][0]["notes"], "Rotalarım")
        self.assertEqual(budget["summary"]["categories"][1]["label"], "Food and drink")

    def test_day_plan_and_events_match_translated_places(self):
        result = self.client.post("/api/day-plans", headers=self.en, json={"city": "istanbul", "available_minutes": 360, "interests": ["museum", "history"]})
        self.assertEqual(result.status_code, 200, result.text)
        data = result.json()
        self.assertEqual(data["status"], "ready")
        self.assertIn("My day out", data["route"]["title"])
        names = {p["slug"]: p["name"] for p in data["route"]["places"]}
        for entry in data["schedule"]:
            if entry["kind"] == "visit": self.assertEqual(entry["title"], names[entry["place_slug"]])
        self.assertIn("Opening hours", data["notes"][1])
        en = self.client.get("/api/events?city=istanbul&include_past=true", headers=self.en).json()["items"]
        tr = self.client.get("/api/events?city=istanbul&include_past=true").json()["items"]
        self.assertEqual([e["start_date"] for e in en], [e["start_date"] for e in tr])
        self.assertEqual(en[0]["title"], CATALOG["events"][en[0]["slug"]]["en"]["title"])
        self.assertEqual(en[0]["original_content"]["title"], tr[0]["title"])
        template = self.client.get("/api/route-templates", headers=self.en).json()["items"][0]
        self.assertEqual(template["title"], CATALOG["templates"][template["slug"]]["en"]["title"])

    def test_errors_localized_without_rewriting_validation_input(self):
        en = self.client.get("/api/places/missing", headers=self.en)
        self.assertEqual(en.status_code, 404)
        self.assertEqual(en.json()["detail"], "Stop not found.")
        denied = self.client.get("/api/routes", headers=self.en)
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(denied.json()["detail"], "Please sign in to continue.")
        bad = self.client.post("/api/day-plans", headers=self.en, json={"city": "istanbul", "interests": ["museum", "museum"]})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(bad.json()["detail"][0]["msg"], "Select each interest only once.")
        self.assertEqual(bad.json()["detail"][0]["input"]["city"], "istanbul")

    def test_offline_pack_is_public_bilingual_and_has_all_template_stops(self):
        self.new_route()
        guest = TestClient(main.app)
        try:
            en = self.client.get("/api/offline-guide?lang=en")
            public = guest.get("/api/offline-guide?lang=en")
            tr = guest.get("/api/offline-guide?lang=tr")
            worker = guest.get("/offline-worker.js")
        finally:
            guest.close()
        self.assertEqual((en.status_code, public.status_code, tr.status_code), (200, 200, 200))
        self.assertEqual((en.headers["content-language"], tr.headers["content-language"]), ("en", "tr"))
        member, anonymous = en.json(), public.json()
        member.pop("downloaded_at")
        anonymous.pop("downloaded_at")
        self.assertEqual(member, anonymous)
        self.assertEqual(set(member), {"version", "cities", "categories", "places", "templates"})
        self.assertEqual({city["slug"] for city in member["cities"]}, {"istanbul", "ankara", "izmir"})
        en_names = {place["slug"]: place["name"] for place in member["places"]}
        self.assertEqual(len(en_names), len(CATALOG["places"]))
        self.assertEqual(en_names["yerebatan-sarnici"], "Basilica Cistern")
        self.assertTrue(any(p["name"] == "Yerebatan Sarnıcı" for p in tr.json()["places"]))
        for template in member["templates"]:
            self.assertEqual(template["places"], [next(p for p in member["places"] if p["slug"] == slug) for slug in template["place_slugs"]])
        self.assertEqual(worker.status_code, 200)
        self.assertIn("javascript", worker.headers["content-type"])
        self.assertEqual(worker.headers["cache-control"], "no-cache")


if __name__ == "__main__":
    unittest.main()
