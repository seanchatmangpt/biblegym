from __future__ import annotations

import asyncio
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "src"))

from biblegym import BibleGymProvider, CAPABILITY_BY_BINDING
from biblegym.knowing_christ import PROGRAM_GOAL, knowing_christ_packet, step_ids

CFG = {
    "church_id": "knowing-christ-test",
    "name": "Knowing Christ Test Church",
    "locale": "en-US",
    "timezone": "America/Los_Angeles",
    "currency": "USD",
    "bible_translation": "NIV",
    "campuses": ["main"],
    "required_volunteers_per_service": 0,
}


def run(coro):
    return asyncio.run(coro)


class KnowingChristFormationTests(unittest.TestCase):
    def env(self):
        return run(BibleGymProvider().materialize(scenario="formation", config=CFG))

    def act(self, env, binding, **payload):
        return run(env.actuate(CAPABILITY_BY_BINDING[binding], payload))["result"]

    def test_program_is_exactly_twelve_ordered_source_grounded_steps(self):
        packet = knowing_christ_packet(bible_translation="NIV", locale="en-US")
        self.assertEqual(packet["goal"], PROGRAM_GOAL)
        self.assertEqual(packet["authority"], "CONSTRUCT_ONLY_NO_DO")
        self.assertEqual(len(packet["steps"]), 12)
        self.assertEqual([step["order"] for step in packet["steps"]], list(range(1, 13)))
        self.assertEqual(len(set(step_ids())), 12)

        refs = {ref for step in packet["steps"] for ref in step["scripture_refs"]}
        for expected in {
            "Proverbs 11:24-25",
            "Matthew 13:24-30",
            "Matthew 6:9-13",
            "Matthew 7:21-23",
            "Matthew 7:24-27",
            "Philippians 3:7-17",
        }:
            self.assertIn(expected, refs)

    def test_program_explicitly_refuses_recognition_scoring_and_ai_authority(self):
        packet = knowing_christ_packet(bible_translation="NIV", locale="en-US")
        self.assertIn("NO_CONVERSION_SCORE", packet["fences"])
        self.assertIn("NO_SPIRITUAL_LEADERBOARD", packet["fences"])
        self.assertIn("NO_RECOGNITION_AS_GOAL", packet["fences"])
        self.assertIn("NO_PROSPERITY_FORMULA", packet["fences"])
        self.assertIn("NO_AI_REVELATION_CLAIMS", packet["fences"])
        self.assertIn("NO_PASTORAL_AUTHORITY", packet["fences"])

    def test_devotion_packet_exposes_program_without_widening_do_authority(self):
        env = self.env()
        self.act(env, "register_person", person_id="p")
        packet = self.act(env, "devotion_prompt_packet", person_id="p")
        self.assertEqual(packet["authority"], "CONSTRUCT_ONLY_NO_DO")
        self.assertEqual(packet["formation_program"]["authority"], "CONSTRUCT_ONLY_NO_DO")
        self.assertEqual(packet["formation_program"]["goal"], "know_christ")
        self.assertEqual(len(packet["formation_program"]["steps"]), 12)

    def test_formation_is_process_not_gamified_result(self):
        env = self.env()
        self.act(env, "register_person", person_id="p", leaderboard_opt_in=True)
        before = self.act(env, "dashboard", actor_id="p")
        self.assertEqual(before["points"], 0)
        self.assertEqual(before["milestones"], [])

        result = self.act(
            env,
            "record_formation_step",
            person_id="p",
            stage="practice",
            scripture_ref="Philippians 3:7-17",
            process_step="press-on-to-know-christ",
            setup_category="daily-process",
            next_faithful_action="pray: God, I want to know you",
        )
        self.assertEqual(result["goal"], "know_christ")
        self.assertEqual(result["process_step"], "press-on-to-know-christ")

        after = self.act(env, "dashboard", actor_id="p")
        self.assertEqual(after["points"], 0)
        self.assertEqual(after["milestones"], [])
        self.assertFalse(any(item["points"] > 0 for item in self.act(env, "leaderboard")))

    def test_unknown_step_and_private_confession_fail_closed(self):
        env = self.env()
        self.act(env, "register_person", person_id="p")
        with self.assertRaises(ValueError):
            self.act(
                env,
                "record_formation_step",
                person_id="p",
                stage="practice",
                scripture_ref="Matthew 7:24-27",
                process_step="recognition-score",
                next_faithful_action="practice the word",
            )
        with self.assertRaises(PermissionError):
            self.act(
                env,
                "record_formation_step",
                person_id="p",
                stage="surrender",
                scripture_ref="Luke 9:23-24",
                process_step="daily-dying",
                next_faithful_action="surrender",
                confession="private text must not be stored",
            )


if __name__ == "__main__":
    unittest.main()
