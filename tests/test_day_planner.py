"""Day-plan time bounds, preferences, local computation and route saving."""
import atexit
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

_boot = tempfile.TemporaryDirectory()
atexit.register(_boot.cleanup)
os.environ["GUIDE_DB_PATH"] = str(Path(_boot.name) / "bootstrap.db")
import main
from guide_day_planner import DayPlanWrite, build_day_plan, clock_minutes, distance_km, MAX_LEG_KM


class DayPlannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous_db = main.DB_PATH
        main.DB_PATH = Path(self.temp.name) / "guide.db"
        main.initialize_database()
        self.client = TestClient(main.app)
        self.payload = {"city": "istanbul", "available_minutes": 360, "start_time": "09:00", "interests": ["museum", "history", "view", "nature", "culture"], "break_minutes": 30}

    def tearDown(self):
        self.client.close()
        main.DB_PATH = self.previous_db
        self.temp.cleanup()

    def plan(self, **overrides):
        response = self.client.post("/api/day-plans", json={**self.payload, **overrides})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def assert_consistent(self, data, minutes):
        self.assertEqual(data["status"], "ready", data)
        summary = data["summary"]
        places = data["route"]["places"]
        self.assertLessEqual(summary["total_minutes"], minutes)
        self.assertEqual(summary["total_minutes"] + summary["free_minutes"], minutes)
        self.assertEqual(summary["total_minutes"], sum(event["minutes"] for event in data["schedule"]))
        self.assertEqual(len(places), len({p["slug"] for p in places}))
        self.assertLessEqual(len(places), 6)
        self.assertEqual(summary["stop_count"], len(places))
        last = clock_minutes(summary["start_time"])
        for event in data["schedule"]:
            self.assertEqual(clock_minutes(event["start"]), last)
            self.assertEqual(clock_minutes(event["end"]) - last, event["minutes"])
            last = clock_minutes(event["end"])
        self.assertEqual(last, clock_minutes(summary["end_time"]))
        self.assertEqual(last - clock_minutes(summary["start_time"]), summary["total_minutes"])
        self.assertEqual(sum(e["minutes"] for e in data["schedule"] if e["kind"] == "break"), summary["break_minutes"])
        for a, b in zip(places, places[1:]):
            self.assertLessEqual(distance_km(a, b), MAX_LEG_KM)

    def test_public_plans_all_cities_fit_window_without_saving(self):
        with patch("guide_features.walking_estimate", side_effect=AssertionError("Planner must work offline")):
            for city in ("istanbul", "ankara", "izmir"):
                with self.subTest(city=city):
                    data = self.plan(city=city)
                    self.assert_consistent(data, 360)
                    self.assertTrue(all(p["city_slug"] == city for p in data["route"]["places"]))
                    self.assertEqual(data["route"]["metrics"]["distance_kind"], "straight_line")
                    self.assertIsNone(data["route"]["metrics"]["walking_minutes"])
        with main.db_session() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM routes").fetchone()[0], 0)

    def test_only_requested_interests_and_confirmed_filters_are_used(self):
        data = self.plan(interests=["museum"], indoor_only=True, family_friendly=True, accessible_only=True)
        self.assert_consistent(data, 360)
        for place in data["route"]["places"]:
            self.assertEqual(place["category_slug"], "museum")
            for field in ("indoor", "family_friendly", "wheelchair_accessible"):
                self.assertIs(place[field], True)
        self.assertEqual(self.plan(interests=["nature"], indoor_only=True)["status"], "empty")

    def sample_places(self):
        return [{"slug": f"place-{i}", "name": f"Durak {i}", "city_slug": "istanbul", "category_slug": category,
                 "latitude": 41 + i * .001, "longitude": 29 + i * .001, "visit_minutes": 60,
                 "featured": False, "average_rating": 0, "indoor": None, "family_friendly": None,
                 "wheelchair_accessible": None, "source_url": "https://example.org/venue"}
                for i, category in enumerate(("museum", "history", "view"))]

    def test_exact_time_boundary_breaks_and_relaxed_pace(self):
        places = self.sample_places()
        exact = DayPlanWrite(city="istanbul", interests=["museum"], available_minutes=90, break_minutes=30)
        data = build_day_plan(places, "İstanbul", exact, main.route_metrics)
        self.assert_consistent(data, 90)
        self.assertEqual(data["summary"]["total_minutes"], 90)
        self.assertEqual(build_day_plan(places, "İstanbul", exact.model_copy(update={"available_minutes":89}), main.route_metrics)["status"], "empty")
        balanced = build_day_plan(places, "İstanbul", DayPlanWrite(**{**self.payload, "available_minutes":600}), main.route_metrics)
        relaxed = build_day_plan(places, "İstanbul", DayPlanWrite(**{**self.payload, "available_minutes":600, "pace":"relaxed"}), main.route_metrics)
        self.assert_consistent(balanced, 600)
        self.assert_consistent(relaxed, 600)
        self.assertEqual(len(balanced["route"]["places"]), len(relaxed["route"]["places"]))
        self.assertGreater(relaxed["summary"]["visit_minutes"], balanced["summary"]["visit_minutes"])
        self.assertGreaterEqual(relaxed["summary"]["estimated_transfer_minutes"], balanced["summary"]["estimated_transfer_minutes"])
        no_break = self.plan(break_minutes=0)
        self.assertFalse(any(e["kind"] == "break" for e in no_break["schedule"]))

    def test_disconnected_and_unknown_locations_are_not_invented(self):
        places = self.sample_places()
        places[1]["latitude"] = 42.0
        places[2]["latitude"] = None
        data = build_day_plan(places, "İstanbul", DayPlanWrite(**self.payload), main.route_metrics)
        self.assert_consistent(data, 360)
        self.assertEqual(len(data["route"]["places"]), 1)
        self.assertTrue(any("Konumu eksik" in note for note in data["notes"]))
        self.assertTrue(any("tamamına" in note for note in data["notes"]))
        places[0]["longitude"] = float("nan")
        places[1]["longitude"] = None
        self.assertEqual(build_day_plan(places, "İstanbul", DayPlanWrite(**self.payload), main.route_metrics)["status"], "empty")

    def test_invalid_preferences_are_rejected(self):
        invalid = [{"city":"unknown"}, {"interests":[]}, {"interests":["shopping"]}, {"interests":["museum","museum"]},
                   {"available_minutes":59}, {"available_minutes":601}, {"available_minutes":True}, {"available_minutes":120.5},
                   {"start_time":"24:00"}, {"start_time":"09:60"}, {"start_time":"23:00"}, {"break_minutes":17},
                   {"available_minutes":60,"break_minutes":60}, {"pace":"fast"}, {"extra":"no"}]
        for override in invalid:
            with self.subTest(override=override):
                self.assertEqual(self.client.post("/api/day-plans", json={**self.payload, **override}).status_code, 422)

    def test_generated_plan_saves_as_private_route_and_supports_budget(self):
        data = self.plan()
        route = data["route"]
        payload = {"title":route["title"], "notes":route["notes"], "place_slugs":[p["slug"] for p in route["places"]]}
        self.assertLessEqual(len(payload["notes"]), 500)
        self.assertEqual(self.client.post("/api/routes", json=payload).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/register", json={"name":"Gezgin","email":"day@example.com","password":"planner-password-123"}).status_code, 201)
        saved = self.client.post("/api/routes", json=payload)
        self.assertEqual(saved.status_code, 201)
        self.assertEqual([p["slug"] for p in saved.json()["places"]], payload["place_slugs"])
        self.assertEqual(self.client.get(f"/api/routes/{saved.json()['id']}/budget").json()["items"], [])
        self.assertEqual(self.client.get("/api/routes").json()["items"][0]["notes"], route["notes"])

    def test_plans_are_deterministic_and_bounded_for_larger_catalog(self):
        places = []
        for index in range(120):
            place = self.sample_places()[index % 3].copy()
            place.update(slug=f"sample-{index:03}", name=f"Örnek {index}", visit_minutes=20, longitude=29 + index * .0001)
            places.append(place)
        payload = DayPlanWrite(**self.payload)
        first = build_day_plan(places,"İstanbul",payload,main.route_metrics)
        second = build_day_plan(places,"İstanbul",payload,main.route_metrics)
        self.assertEqual(first, second)
        self.assert_consistent(first, 360)
        self.assertEqual(first["summary"]["stop_count"], 6)


if __name__ == "__main__":
    unittest.main()
