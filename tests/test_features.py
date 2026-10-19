"""Persistent city guide flows and privacy boundaries."""
from datetime import date, timedelta
from io import BytesIO
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import main
import guide_features


class ExpandedGuideTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        main.DB_PATH = Path(self.temp.name) / "guide.db"
        main.initialize_database()
        self.client = TestClient(main.app)
        self.other = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        self.other.close()
        self.temp.cleanup()

    def register(self, client=None, email="gezgin@example.com"):
        client = client or self.client
        response = client.post("/api/auth/register", json={"name": "Gezgin Deniz", "email": email, "password": "guclu-bir-parola"})
        self.assertEqual(response.status_code, 201, response.text)

    def create_route(self):
        self.register()
        response = self.client.post("/api/routes", json={"title": "Özel gezim", "notes": "Kimseyle paylaşılmayan notum", "place_slugs": ["pera-muzesi", "galata-kulesi"]})
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_cities_filters_templates_and_upgrade(self):
        cities = self.client.get("/api/cities").json()
        self.assertEqual({item["slug"]: item["place_count"] for item in cities}, {"istanbul": 15, "ankara": 5, "izmir": 5})
        for city, count in (("istanbul", 15), ("ankara", 5), ("izmir", 5)):
            places = self.client.get("/api/places", params={"city": city}).json()["items"]
            self.assertEqual(len(places), count)
            self.assertTrue(all(place["city_slug"] == city for place in places))
            self.assertGreaterEqual(len(self.client.get("/api/route-templates", params={"city": city}).json()["items"]), 2)
        accessible = self.client.get("/api/places?city=&wheelchair_accessible=true").json()["items"]
        self.assertEqual({place["slug"] for place in accessible}, {"pera-muzesi", "ankara-vakif-eserleri-muzesi"})
        indoors = self.client.get("/api/places?city=izmir&indoor=true&family_friendly=true").json()["items"]
        self.assertTrue(indoors)
        self.assertTrue(all(place["indoor"] is True and place["family_friendly"] is True for place in indoors))
        self.assertEqual(self.client.get("/api/places?city=").json()["total"], 25)
        with main.db_session() as db:
            db.execute("DELETE FROM places WHERE slug='anitkabir'")
        main.initialize_database()
        self.assertEqual(self.client.get("/api/places/anitkabir").status_code, 404)

    def test_estimates_route_order_and_network_fallback(self):
        slugs = ["pera-muzesi", "galata-kulesi"]
        basic = self.client.post("/api/route-estimate", json={"place_slugs": slugs}).json()
        self.assertGreater(basic["distance_km"], 0)
        self.assertIsNone(basic["walking_minutes"])
        self.assertEqual(basic["distance_kind"], "straight_line")
        self.assertEqual(basic["legs"][0]["from"], "Pera Müzesi")
        self.assertEqual(self.client.post("/api/route-estimate", json={"place_slugs": ["pera-muzesi", "anitkabir"]}).status_code, 422)
        self.assertEqual(self.client.post("/api/route-estimate", json={"place_slugs": ["pera-muzesi", "pera-muzesi"]}).status_code, 422)
        live = {"code": "Ok", "routes": [{"distance": 1250, "duration": 1200, "geometry": {"coordinates": [[28.975, 41.03], [28.974, 41.025]]}, "legs": [{"distance": 1250, "duration": 1200}]}]}
        guide_features._route_cache.clear()
        guide_features._last_request = 0
        with patch("guide_features.urlopen", return_value=BytesIO(json.dumps(live).encode())):
            estimate = self.client.post("/api/route-estimate", json={"place_slugs": slugs, "walking": True}).json()
        self.assertEqual(estimate["distance_kind"], "walking")
        self.assertEqual(estimate["distance_km"], 1.25)
        self.assertEqual(estimate["walking_minutes"], 20)
        self.assertEqual(estimate["total_minutes"], estimate["visit_minutes"] + 20)
        guide_features._route_cache.clear()
        guide_features._last_request = 0
        with patch("guide_features.urlopen", side_effect=OSError("offline")):
            fallback = self.client.post("/api/route-estimate", json={"place_slugs": slugs, "walking": True}).json()
        self.assertEqual(fallback["distance_kind"], "straight_line")
        self.assertIsNone(fallback["walking_minutes"])
        self.assertIn("kuş uçuşu", fallback["note"])

    def test_shared_routes_do_not_expose_notes_and_can_be_revoked(self):
        route = self.create_route()
        self.register(self.other, "baska@example.com")
        self.assertEqual(self.other.post(f"/api/routes/{route['id']}/share").status_code, 404)
        link = self.client.post(f"/api/routes/{route['id']}/share").json()["path"]
        token = link.rsplit("/", 1)[-1]
        shared = self.other.get("/api/shared-routes/" + token)
        self.assertEqual(shared.status_code, 200)
        self.assertEqual(shared.json()["title"], route["title"])
        self.assertNotIn("notes", shared.json())
        self.assertNotIn("user_id", shared.json())
        self.assertNotIn("Kimseyle", shared.text)
        self.assertEqual(self.other.get(link).status_code, 200)
        self.assertEqual(self.client.put(f"/api/routes/{route['id']}", json={"title": "Yeni gezi adı", "notes": "Hâlâ özel", "place_slugs": ["galata-kulesi"]}).status_code, 200)
        self.assertEqual(self.other.get("/api/shared-routes/" + token).json()["title"], "Yeni gezi adı")
        self.assertEqual(self.other.delete(f"/api/routes/{route['id']}/share").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/routes/{route['id']}/share").status_code, 204)
        self.assertEqual(self.other.get("/api/shared-routes/" + token).status_code, 404)

    def test_private_journal_is_scoped_to_user_and_city(self):
        day = date.today().isoformat()
        payload = {"visited_on": day, "notes": "Sadece benim özel günlüğüm."}
        self.assertEqual(self.client.put("/api/journal/galata-kulesi", json=payload).status_code, 401)
        self.register()
        self.assertEqual(self.client.put("/api/journal/galata-kulesi", json=payload).status_code, 200)
        self.assertEqual(self.client.put("/api/journal/galata-kulesi", json={**payload, "notes": "Güncellenen not"}).status_code, 200)
        self.assertEqual(self.client.get("/api/journal").json()["total"], 1)
        self.assertEqual(self.client.get("/api/journal?city=ankara").json()["total"], 0)
        self.register(self.other, "diger@example.com")
        self.assertEqual(self.other.get("/api/journal").json()["total"], 0)
        self.assertEqual(self.other.delete("/api/journal/galata-kulesi").status_code, 204)
        self.assertEqual(self.client.get("/api/journal").json()["items"][0]["notes"], "Güncellenen not")
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        self.assertEqual(self.client.put("/api/journal/galata-kulesi", json={**payload, "visited_on": tomorrow}).status_code, 422)
        self.assertEqual(self.client.delete("/api/journal/galata-kulesi").status_code, 204)
        self.assertEqual(self.client.get("/api/journal").json()["total"], 0)

    def test_event_calendar_overlap_admin_and_validation(self):
        day = date.today()
        payload = {"slug": "resmi-sergi", "title": "Resmî sergi", "city_slug": "izmir", "place_slug": "izmir-ataturk-muzesi", "start_date": day.isoformat(), "end_date": (day + timedelta(days=4)).isoformat(), "description": "Kaynağı doğrulanmış örnek bir takvim etkinliği.", "source_name": "Resmî Müze", "source_url": "https://www.ktb.gov.tr/", "verified_on": day.isoformat()}
        self.register()
        self.assertEqual(self.client.post("/api/admin/events", json=payload).status_code, 403)
        with main.db_session() as db:
            db.execute("UPDATE users SET role='admin' WHERE email='gezgin@example.com'")
        created = self.client.post("/api/admin/events", json=payload)
        self.assertEqual(created.status_code, 201, created.text)
        event_id = created.json()["id"]
        event_day = (day + timedelta(days=2)).isoformat()
        results = self.client.get(f"/api/events?city=izmir&start={event_day}&end={event_day}").json()["items"]
        self.assertTrue(any(event["id"] == event_id for event in results))
        self.assertEqual(self.client.post("/api/admin/events", json=payload).status_code, 409)
        self.assertEqual(self.client.put(f"/api/admin/events/{event_id}", json={**payload, "title": "   "}).status_code, 422)
        self.assertEqual(self.client.put(f"/api/admin/events/{event_id}", json={**payload, "source_url": "javascript:alert(1)"}).status_code, 422)
        self.assertEqual(self.client.put(f"/api/admin/events/{event_id}", json={**payload, "place_slug": "galata-kulesi"}).status_code, 422)
        self.assertEqual(self.client.put(f"/api/admin/events/{event_id}", json={**payload, "end_date": (day - timedelta(days=1)).isoformat()}).status_code, 422)
        self.assertEqual(self.client.put(f"/api/admin/events/{event_id}", json={**payload, "title": "Güncel sergi"}).status_code, 200)
        self.assertEqual(self.client.delete(f"/api/admin/events/{event_id}").status_code, 204)
        self.assertEqual(self.client.get("/api/events?city=izmir").json()["items"], [])


if __name__ == "__main__":
    unittest.main()
