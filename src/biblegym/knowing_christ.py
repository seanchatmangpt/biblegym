from __future__ import annotations

from copy import deepcopy
from typing import Any

PROGRAM_ID = "knowing-christ-v1"
PROGRAM_GOAL = "know_christ"

# Scripture references are identifiers, not embedded translation text. The active
# church configuration owns translation preference and an external READ surface may
# resolve the text. BibleGym does not manufacture revelation or doctrine.
_STEPS: tuple[dict[str, Any], ...] = (
    {
        "id": "empty-hands",
        "order": 1,
        "title": "Empty Hands",
        "scripture_refs": ["Job 1:21", "Job 42:10-17"],
        "theme": "Receive life as gift rather than treating restoration as an earned result.",
        "practice": "Name what you are trying to control and release the result to God.",
    },
    {
        "id": "ask-daily",
        "order": 2,
        "title": "Ask Daily",
        "scripture_refs": ["Matthew 6:9-13"],
        "theme": "Prayer is a daily relationship and dependence, not a project milestone.",
        "practice": "Pray the Lord's Prayer slowly and ask for today's bread, forgiveness, and guidance.",
    },
    {
        "id": "sow-freely",
        "order": 3,
        "title": "Sow Freely",
        "scripture_refs": ["Proverbs 11:24-25"],
        "theme": "Practice generosity without turning generosity into a transaction for gain.",
        "practice": "Refresh someone today without requiring recognition or repayment.",
    },
    {
        "id": "discern-seed",
        "order": 4,
        "title": "Discern the Seed",
        "scripture_refs": ["Matthew 13:24-30"],
        "theme": "Wheat and weeds can coexist before the harvest; visible results are not final judgment.",
        "practice": "Separate what you observed from the judgment you are tempted to make about it.",
    },
    {
        "id": "leave-the-harvest",
        "order": 5,
        "title": "Leave the Harvest to God",
        "scripture_refs": ["Matthew 13:28-30"],
        "theme": "Do not destroy good growth while trying to force an early judgment.",
        "practice": "Choose one situation where patience is more faithful than forced resolution.",
    },
    {
        "id": "thorns-and-pruning",
        "order": 6,
        "title": "Thorns and Pruning",
        "scripture_refs": ["Mark 4:18-19", "John 15:1-5"],
        "theme": "Distinguish what chokes growth from the pruning that makes room for fruit.",
        "practice": "Identify one distraction, fear, or attachment that is crowding out attention to Christ.",
    },
    {
        "id": "daily-dying",
        "order": 7,
        "title": "Daily Dying",
        "scripture_refs": ["Luke 9:23-24"],
        "theme": "Following Jesus is a repeated surrender, not a completed spiritual project.",
        "practice": "Choose one concrete act of self-denial that makes room to love God or neighbor.",
    },
    {
        "id": "pray-honestly",
        "order": 8,
        "title": "Pray Honestly",
        "scripture_refs": ["Psalm 13", "Psalm 51", "Psalm 139:23-24"],
        "theme": "David's prayers model honest speech before God: lament, repentance, praise, and examination.",
        "practice": "Tell God the truth about what you fear, want, regret, and hope for.",
    },
    {
        "id": "trust-providence",
        "order": 9,
        "title": "Trust Providence",
        "scripture_refs": ["Genesis 39:2-3", "Genesis 50:19-21"],
        "theme": "Joseph's story emphasizes God's presence and providence through suffering without promising an easy outcome.",
        "practice": "Name one painful circumstance without pretending to know its final meaning.",
    },
    {
        "id": "practice-the-word",
        "order": 10,
        "title": "Practice the Word",
        "scripture_refs": ["Matthew 7:24-27"],
        "theme": "Hearing becomes formation through practice; information alone is not the foundation.",
        "practice": "Turn one teaching of Jesus you already understand into a specific action today.",
    },
    {
        "id": "relationship-over-recognition",
        "order": 11,
        "title": "Relationship Over Recognition",
        "scripture_refs": ["Matthew 7:21-23"],
        "theme": "Recognition and impressive results are not the goal; knowing Christ and doing the Father's will cannot be replaced by performance.",
        "practice": "Do one faithful thing that nobody needs to notice.",
    },
    {
        "id": "press-on-to-know-christ",
        "order": 12,
        "title": "Press On to Know Christ",
        "scripture_refs": ["Philippians 3:7-17"],
        "theme": "The process has a direction but not a recognition score: know Christ and keep pressing on.",
        "practice": "Pray: God, I want to know you. Then take the next faithful action already made clear to you.",
    },
)


def step_ids() -> tuple[str, ...]:
    return tuple(step["id"] for step in _STEPS)


def knowing_christ_packet(*, bible_translation: str, locale: str) -> dict[str, Any]:
    """Return the deterministic SELECT/CONSTRUCT formation packet.

    This packet can ground an external planner or LLM. It cannot claim revelation,
    infer a person's standing with God, score conversion, or exercise pastoral DO.
    """

    return {
        "program_id": PROGRAM_ID,
        "goal": PROGRAM_GOAL,
        "title": "Knowing Christ: A Daily 12-Step Formation Process",
        "locale": locale,
        "bible_translation": bible_translation,
        "cadence": "daily_process_not_project",
        "steps": deepcopy(_STEPS),
        "cross_cutting": {
            "solitude": "Deliberate time alone with God that remains connected to love and community.",
            "isolation": "Withdrawal from truthful relationship or help; it is not treated as a spiritual achievement.",
            "results": "Observed outcomes are evidence about events, never a score of spiritual worth or proof that God approves a person.",
        },
        "fences": [
            "NO_CONVERSION_SCORE",
            "NO_SPIRITUAL_LEADERBOARD",
            "NO_RECOGNITION_AS_GOAL",
            "NO_PROSPERITY_FORMULA",
            "NO_AI_REVELATION_CLAIMS",
            "NO_PASTORAL_AUTHORITY",
            "NO_PRIVATE_CONFESSION_STORAGE",
        ],
        "authority": "CONSTRUCT_ONLY_NO_DO",
    }
