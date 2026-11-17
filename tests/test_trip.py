"""Persistent trip state, privacy, edits and stale-client protection."""
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


class TripTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = main.DB_PATH
        main.DB_PATH = Path(self.temp.name) / "guide.db"
        main.initialize_database()
        self.owner, self.other, self.guest = (TestClient(main.app) for _ in range(3))
        self.owner.post("/api/auth/register", json={"name":"Gezgin", "email":"trip@example.com", "password":"trip-password-123"})
        self.slugs = ["galata-kulesi", "pera-muzesi", "istanbul-modern"]
        self.route = self.owner.post("/api/routes", json={"title":"Güzel bir gün", "place_slugs":self.slugs}).json()
        self.url = f"/api/routes/{self.route['id']}/trip"

    def tearDown(self):
        for client in (self.owner, self.other, self.guest):
            client.close()
        main.DB_PATH = self.previous
        self.temp.cleanup()

    def get(self):
        result = self.owner.get(self.url)
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def act(self, action, slug=None, revision=None):
        body = {"action":action,"expected_revision":self.get()["revision"] if revision is None else revision}
        if slug is not None:
            body["place_slug"] = slug
        result = self.owner.post(self.url, json=body)
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def finish(self):
        self.act("start")
        for slug in self.slugs:
            result = self.act("complete_stop", slug)
        return result

    def test_get_is_read_only_and_trip_survives_migration(self):
        data = self.get()
        self.assertEqual((data["status"],data["revision"]), ("not_started",0))
        self.assertEqual(data["next_stop"]["slug"], self.slugs[0])
        self.assertEqual(data["summary"]["completed_count"], 0)
        with main.db_session() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM route_trips").fetchone()[0],0)
        self.act("start")
        data = self.act("complete_stop", self.slugs[0])
        main.initialize_database()
        main.initialize_database()
        self.assertEqual(self.get(), data)

    def test_start_pause_resume_finish_and_estimates(self):
        initial = self.get()
        active = self.act("start")
        self.assertEqual(active["status"],"active")
        self.assertIsNotNone(active["started_at"])
        first = self.act("complete_stop",self.slugs[0])
        self.assertEqual(first["next_stop"]["slug"], self.slugs[1])
        self.assertLess(first["summary"]["remaining_estimated_minutes"],initial["summary"]["remaining_estimated_minutes"])
        paused = self.act("pause")
        self.assertEqual(paused["status"],"paused")
        self.assertIsNotNone(paused["paused_at"])
        denied = self.owner.post(self.url,json={"action":"complete_stop","place_slug":self.slugs[1],"expected_revision":paused["revision"]})
        self.assertEqual(denied.status_code,409)
        resumed = self.act("resume")
        self.assertEqual(resumed["started_at"], active["started_at"])
        self.assertIsNone(resumed["paused_at"])
        self.act("complete_stop",self.slugs[1])
        final = self.act("complete_stop",self.slugs[2])
        self.assertEqual(final["status"],"completed")
        self.assertIsNone(final["next_stop"])
        self.assertIsNotNone(final["finished_at"])
        self.assertEqual(final["summary"]["completed_percent"],100)
        self.assertEqual(final["summary"]["remaining_estimated_minutes"],0)
        with main.db_session() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM journal").fetchone()[0],0)

    def test_stale_revision_and_wrong_next_stop_do_not_advance_twice(self):
        data = self.act("start")
        self.act("complete_stop",self.slugs[0])
        for slug,revision in ((self.slugs[0],data["revision"]),(self.slugs[0],self.get()["revision"]),(self.slugs[2],self.get()["revision"])):
            result = self.owner.post(self.url,json={"action":"complete_stop","place_slug":slug,"expected_revision":revision})
            self.assertEqual(result.status_code,409)
        self.assertEqual(self.get()["summary"]["completed_count"],1)
        self.assertEqual(self.get()["next_stop"]["slug"],self.slugs[1])

    def test_undo_finished_trip_requires_resume_and_restart_preserves_budget(self):
        final = self.finish()
        undone = self.act("undo_stop",self.slugs[1])
        self.assertEqual(undone["status"],"paused")
        self.assertIsNone(undone["finished_at"])
        self.assertEqual(undone["next_stop"]["slug"],self.slugs[1])
        self.act("resume")
        self.act("complete_stop",self.slugs[1])
        budget_url=f"/api/routes/{self.route['id']}/budget"
        self.assertEqual(self.owner.post(budget_url,json={"title":"Bilet","category":"tickets","planned_amount":"100","spent_amount":"50"}).status_code,201)
        reset = self.act("restart")
        self.assertEqual(reset["status"],"active")
        self.assertEqual(reset["summary"]["completed_count"],0)
        self.assertEqual(reset["next_stop"]["slug"],self.slugs[0])
        self.assertGreater(reset["revision"],final["revision"])
        self.assertEqual(self.owner.get(budget_url).json()["summary"]["spent_kurus"],5000)

    def test_owner_only_and_shared_links_do_not_reveal_progress(self):
        self.act("start")
        self.act("complete_stop",self.slugs[0])
        self.other.post("/api/auth/register",json={"name":"Başka gezgin","email":"other-trip@example.com","password":"trip-password-123"})
        for client,code in ((self.other,404),(self.guest,401)):
            self.assertEqual(client.get(self.url).status_code,code)
            for action in ("start","pause","resume","restart"):
                self.assertEqual(client.post(self.url,json={"action":action,"expected_revision":0}).status_code,code)
        path=self.owner.post(f"/api/routes/{self.route['id']}/share").json()["path"]
        public=self.guest.get("/api/shared-routes/"+path.rsplit("/",1)[1])
        self.assertEqual(public.status_code,200)
        for key in ("completed_at","started_at","revision","next_stop"):
            self.assertNotIn(key,public.json())
            self.assertNotIn('"'+key+'"',public.text)
        self.assertEqual(self.get()["summary"]["completed_count"],1)

    def test_route_edit_preserves_matching_marks_and_invalidates_old_revision(self):
        self.act("start")
        self.act("complete_stop",self.slugs[0])
        old=self.act("complete_stop",self.slugs[1])
        new_slugs=[self.slugs[2],self.slugs[0],"yerebatan-sarnici"]
        result=self.owner.put(f"/api/routes/{self.route['id']}",json={"title":"Yeni sıra","place_slugs":new_slugs})
        self.assertEqual(result.status_code,200,result.text)
        updated=self.get()
        self.assertEqual(updated["title"],"Yeni sıra")
        self.assertEqual(updated["summary"]["completed_count"],1)
        self.assertEqual([p["slug"] for p in updated["stops"] if p["completed"]],[self.slugs[0]])
        self.assertEqual(updated["next_stop"]["slug"],self.slugs[2])
        self.assertGreater(updated["revision"],old["revision"])
        stale=self.owner.post(self.url,json={"action":"complete_stop","place_slug":self.slugs[2],"expected_revision":old["revision"]})
        self.assertEqual(stale.status_code,409)
        with main.db_session() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM route_trip_stops").fetchone()[0],1)

    def test_added_stop_reopens_completed_trip_as_paused(self):
        self.finish()
        result=self.owner.put(f"/api/routes/{self.route['id']}",json={"title":"Bir durak daha","place_slugs":[*self.slugs,"yerebatan-sarnici"]})
        self.assertEqual(result.status_code,200)
        data=self.get()
        self.assertEqual(data["status"],"paused")
        self.assertIsNone(data["finished_at"])
        self.assertEqual(data["summary"]["completed_count"],3)
        self.assertEqual(data["next_stop"]["slug"],"yerebatan-sarnici")
        self.act("resume")
        self.assertEqual(self.act("complete_stop","yerebatan-sarnici")["status"],"completed")

    def test_invalid_commands_and_foreign_origin_do_not_write(self):
        invalid=[{}, {"action":"skip","expected_revision":0}, {"action":"start","expected_revision":-1}, {"action":"start","expected_revision":True}, {"action":"start","expected_revision":"0"}, {"action":"complete_stop","expected_revision":0}, {"action":"start","expected_revision":0,"place_slug":self.slugs[0]}, {"action":"start","expected_revision":0,"extra":1}]
        for payload in invalid:
            self.assertEqual(self.owner.post(self.url,json=payload).status_code,422)
        self.assertEqual(self.owner.post(self.url,json={"action":"start","expected_revision":0},headers={"Origin":"https://untrusted.example"}).status_code,403)
        for action in ("pause","resume"):
            self.assertEqual(self.owner.post(self.url,json={"action":action,"expected_revision":0}).status_code,409)
        self.assertEqual(self.get()["revision"],0)

    def test_missing_locations_empty_route_and_delete_cascades(self):
        self.act("start")
        self.act("complete_stop",self.slugs[0])
        with main.db_session() as db:
            db.execute("UPDATE places SET latitude=NULL WHERE slug=?",(self.slugs[1],))
        data=self.get()
        self.assertIsNone(data["summary"]["remaining_estimated_minutes"])
        self.assertGreater(data["summary"]["remaining_visit_minutes"],0)
        with main.db_session() as db:
            db.execute("DELETE FROM route_places WHERE route_id=?",(self.route["id"],))
        empty=self.get()
        self.assertEqual(empty["summary"]["total_count"],0)
        self.assertEqual(empty["status"],"paused")
        self.assertIsNone(empty["next_stop"])
        self.assertEqual(self.owner.post(self.url,json={"action":"restart","expected_revision":empty["revision"]}).status_code,422)
        self.assertEqual(self.owner.delete(f"/api/routes/{self.route['id']}").status_code,204)
        with main.db_session() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM route_trips").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM route_trip_stops").fetchone()[0],0)

    def test_start_and_pause_are_idempotent_at_current_revision(self):
        active=self.act("start")
        self.assertEqual(self.act("start"),active)
        paused=self.act("pause")
        self.assertEqual(self.act("pause"),paused)
        self.act("resume")
        self.assertEqual(self.act("resume")["status"],"active")


if __name__ == "__main__":
    unittest.main()
