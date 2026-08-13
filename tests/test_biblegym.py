from __future__ import annotations

import asyncio
import hashlib
import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "src"))

from biblegym import BibleGymProvider, CAPABILITY_BY_BINDING

CFG = {
    "church_id": "global-demo",
    "name": "Global Demo Church",
    "locale": "es-MX",
    "timezone": "America/Mexico_City",
    "currency": "MXN",
    "bible_translation": "RVR1960",
    "campuses": ["centro", "norte"],
    "required_volunteers_per_service": 3,
}


def run(coro):
    return asyncio.run(coro)


class BibleGymTests(unittest.TestCase):
    def env(self):
        return run(BibleGymProvider().materialize(scenario="formation", config=CFG))

    def act(self, env, binding, **payload):
        return run(env.actuate(CAPABILITY_BY_BINDING[binding], payload))["result"]

    def register(self, env, person_id, **extra):
        return self.act(env, "register_person", person_id=person_id, **extra)

    def onboard(self, env, person_id, ministry="welcome"):
        self.act(env, "recruit_volunteer", person_id=person_id, ministry=ministry)
        return self.act(
            env,
            "onboard_volunteer",
            person_id=person_id,
            orientation_complete=True,
            role_acknowledged=True,
        )

    def test_gymact_lifecycle_and_global_identity(self):
        env = self.env()
        self.assertTrue(env.requires_authority)
        observed = run(env.observe())
        self.assertEqual((observed["locale"], observed["currency"]), ("es-MX", "MXN"))
        cp = run(env.checkpoint())
        self.register(env, "p1", leaderboard_opt_in=True)
        self.assertEqual(run(env.observe())["people"], 1)
        run(env.restore(cp))
        self.assertEqual(run(env.observe())["people"], 0)
        passed, _ = run(env.verify({"church_id": "global-demo", "people": 0}))
        self.assertTrue(passed)
        run(env.teardown())
        with self.assertRaises(RuntimeError):
            run(env.observe())

    def test_sermon_to_daily_practice_accountability_and_gamification(self):
        env = self.env()
        self.register(env, "p1", leaderboard_opt_in=True)
        self.register(env, "p2", leaderboard_opt_in=True)
        self.act(
            env,
            "publish_sermon",
            sermon_id="s1",
            title="Serve your neighbor",
            scripture_refs=["Luke 10:33-35"],
            points=["mercy becomes action"],
        )
        self.act(
            env,
            "create_quest_from_sermon",
            quest_id="q1",
            sermon_id="s1",
            scripture_ref="Luke 10:33-35",
            practice="Help one neighbor",
            minutes=2,
        )
        self.act(
            env,
            "set_habit_stack",
            person_id="p1",
            after="after breakfast",
            practice="pray and choose one neighbor to serve",
            minutes=2,
            scripture_ref="Luke 10:33-35",
        )
        self.act(
            env,
            "link_accountability",
            person_id="p1",
            partner_id="p2",
            person_consents=True,
            partner_consents=True,
        )
        out = self.act(env, "complete_quest", person_id="p1", quest_id="q1")
        self.assertIn("first-steps", out["badges"])
        board = self.act(env, "leaderboard")
        self.assertEqual(board[0]["person_id"], "p1")
        packet = self.act(env, "devotion_prompt_packet", person_id="p1")
        self.assertEqual(packet["authority"], "CONSTRUCT_ONLY_NO_DO")

    def test_one_tap_community_event_volunteer_and_content_features(self):
        env = self.env()
        self.register(env, "v1", roles=["volunteer"], location_consent=True)
        self.onboard(env, "v1")
        self.act(env, "create_group", group_id="g1", name="Welcome Team")
        self.act(env, "join_group", person_id="v1", group_id="g1")
        self.act(env, "create_event", event_id="sun", name="Sunday Service", campus_id="centro")
        self.act(env, "rsvp_event", person_id="v1", event_id="sun")
        self.act(
            env,
            "assign_volunteer",
            assignment_id="a1",
            person_id="v1",
            event_id="sun",
            role="doorkeeper",
            route="welcome",
        )
        self.act(env, "location_check_in", person_id="v1", event_id="sun", inside_geofence=True)
        self.act(
            env,
            "publish_content",
            content_id="c1",
            title="Sunday notes",
            kind="sermon-notes",
            offline=True,
            scripture_refs=["Romans 12:13"],
        )
        self.act(env, "schedule_reminder", person_id="v1", subject_ref="event:sun", local_time="08:30")
        self.act(env, "share_invite", actor_id="v1", subject_ref="group:g1", channel="link")
        self.assertEqual(len(self.act(env, "offline_content")), 1)
        self.act(env, "set_next_step", person_id="v1", step_ref="serve:welcome", status="ACTIVE")
        self.act(env, "qr_check_in", person_id="v1", event_id="sun", qr_subject_ref="event:sun")
        note_digest = hashlib.sha256(b"encrypted-note").hexdigest()
        self.act(env, "record_content_note", person_id="v1", content_id="c1", note_digest=note_digest, encrypted_ref="device:vault:note-1")
        manifest = self.act(env, "content_sync_manifest")
        self.assertEqual(manifest[0]["note_refs"], 1)
        message = self.act(env, "message_intent", actor_id="v1", recipient_ref="group:g1", subject_ref="event:sun", template_ref="welcome-reminder")
        self.assertEqual(message["delivery"], "INTENT_ONLY")
        contact = self.act(env, "contact_intent", actor_id="v1", contact_ref="leader:welcome", action="text")
        self.assertEqual(contact["delivery"], "INTENT_ONLY")
        assertion = self.act(env, "record_biometric_assertion", person_id="v1", verified=True)
        self.assertTrue(assertion["verified"])
        with self.assertRaises(PermissionError):
            self.act(env, "record_biometric_assertion", person_id="v1", verified=True, biometric="face-template")
        with self.assertRaises(PermissionError):
            self.act(env, "message_intent", actor_id="v1", recipient_ref="group:g1", subject_ref="event:sun", template_ref="x", body="freeform")
        self.assertEqual(run(env.observe())["checkins"], 2)
        staffing = self.act(env, "staffing_health", event_id="sun")[0]
        self.assertEqual((staffing["required"], staffing["assigned"], staffing["vacancies"]), (3, 1, 2))

    def test_zero_roster_welcome_lifecycle_service_route_and_autonomous_hosting(self):
        env = self.env()
        self.act(env, "create_event", event_id="s0900", name="9 AM Service", campus_id="centro")
        self.assertEqual(self.act(env, "staffing_health", event_id="s0900")[0]["assigned"], 0)
        for pid in ("v1", "v2", "v3"):
            self.register(env, pid, roles=["attendee"])
            self.onboard(env, pid)
            self.act(
                env,
                "assign_volunteer",
                assignment_id=f"a-{pid}",
                person_id=pid,
                event_id="s0900",
                role="doorkeeper",
                route="welcome",
            )
        self.act(env, "assign_cochair", person_id="v1")
        staffed = self.act(env, "staffing_health", event_id="s0900")[0]
        self.assertEqual((staffed["assigned"], staffed["vacancies"]), (3, 0))

        gap = self.act(env, "record_no_show", assignment_id="a-v2", gap_id="gap-1")
        self.assertEqual(gap["status"], "OPEN")
        escalated = self.act(env, "escalate_staffing_gap", gap_id="gap-1", governance_route="welcome-captain")
        self.assertEqual(escalated["status"], "ESCALATED")
        opt_out = self.act(env, "opt_out_volunteer", person_id="v3")
        self.assertFalse(opt_out["notifications"])

        route = self.act(
            env,
            "create_service_route",
            route_id="route-1",
            need_category="belonging",
            route="get-connected",
            door="welcome-table",
            role="doorkeeper",
            assignment_ref="a-v1",
            evidence_ref="checkin:s0900",
            receipt_ref="gymact:receipt:pending",
        )
        self.assertEqual(route["follow_up_status"], "PENDING")
        follow = self.act(
            env,
            "record_follow_up",
            route_id="route-1",
            person_id="v1",
            outcome_code="CONNECTED_TO_GROUP",
            evidence_ref="group:g1",
        )
        self.assertEqual(follow["outcome_code"], "CONNECTED_TO_GROUP")
        self.assertEqual(self.act(env, "service_route", route_id="route-1")["follow_up_status"], "COMPLETED")

        hosted = self.act(
            env,
            "host_autonomous_group",
            agreement_id="aa-thu",
            group_name="Thursday Recovery Fellowship",
            space="Room A",
            cadence="Thursday 19:00",
        )
        self.assertTrue(hosted["group_governance"] == "AUTONOMOUS" and not hosted["church_controls_program"])

    def test_private_prayer_bible_need_formation_and_care_fences(self):
        env = self.env()
        self.register(env, "p", location_consent=False)
        self.act(env, "create_event", event_id="e", name="Service")
        with self.assertRaises(PermissionError):
            self.act(env, "location_check_in", person_id="p", event_id="e", inside_geofence=True)
        with self.assertRaises(PermissionError):
            self.act(
                env,
                "location_check_in",
                person_id="p",
                event_id="e",
                inside_geofence=True,
                latitude=34.1,
            )
        with self.assertRaises(PermissionError):
            self.act(
                env,
                "record_formation_step",
                person_id="p",
                stage="admit",
                scripture_ref="Matthew 26:41",
                next_faithful_action="call a safe person",
                details="raw story",
            )
        formation = self.act(
            env,
            "record_formation_step",
            person_id="p",
            stage="admit",
            scripture_ref="Matthew 26:41",
            setup_category="isolation",
            next_faithful_action="call a safe person",
            risk="none",
        )
        self.assertNotIn("details", formation)
        with self.assertRaises(PermissionError):
            self.act(env, "record_prayer_request", person_id="p", category="family", consent=True, prayer_text="private")
        prayer = self.act(env, "record_prayer_request", person_id="p", category="family", consent=True)
        self.assertEqual(prayer["status"], "REQUESTED")
        with self.assertRaises(PermissionError):
            self.act(
                env,
                "route_bible_need",
                person_id="p",
                topic="forgiveness",
                scripture_ref="Luke 6:37",
                target="mentor",
                narrative="private details",
            )
        routed = self.act(
            env,
            "route_bible_need",
            person_id="p",
            topic="forgiveness",
            scripture_ref="Luke 6:37",
            target="mentor",
        )
        self.assertEqual(routed["status"], "ROUTED")
        with self.assertRaises(PermissionError):
            self.act(env, "record_care_handoff", person_id="p", category="pastoral", reason_code="REQUESTED", details="private")
        self.assertEqual(
            self.act(env, "record_care_handoff", person_id="p", category="pastoral", reason_code="REQUESTED")["status"],
            "ROUTED",
        )

    def test_child_checkin_hashes_pickup_secret_and_giving_does_not_charge(self):
        env = self.env()
        self.register(env, "g")
        self.act(env, "create_event", event_id="kids", name="Kids Service")
        token = "secret-pickup"
        rec = self.act(env, "child_check_in", guardian_id="g", child_ref="child:opaque", event_id="kids", pickup_token=token)
        self.assertEqual(rec["pickup_token_digest"], hashlib.sha256(token.encode()).hexdigest())
        self.assertNotIn(token, str(rec))
        giving = self.act(env, "record_giving_intent", person_id="g", amount_minor=2500, currency="MXN", purpose="benevolence")
        self.assertEqual(giving["payment_status"], "NOT_ACTUATED")
        with self.assertRaises(PermissionError):
            self.act(env, "record_giving_intent", person_id="g", amount_minor=2500, payment_token="secret")

    def test_ggen_ontology_and_generated_catalog_are_in_lockstep(self):
        root = pathlib.Path(__file__).parents[1]
        ttl = (root / "ggen/biblegym-pack/ontology.ttl").read_text()
        ontology = set(re.findall(r'bg:capabilityBinding "([^"]+)"', ttl))
        generated = set(CAPABILITY_BY_BINDING)
        self.assertEqual(ontology, generated)
        self.assertGreaterEqual(len(generated), 47)
        self.assertIn("org:Organization", ttl)
        self.assertIn("AUTONOMOUS", pathlib.Path(root / "src/biblegym/environment.py").read_text())


if __name__ == "__main__":
    unittest.main()
