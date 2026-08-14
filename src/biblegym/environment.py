from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .compat import Capability
from .generated_catalog import BIBLEGYM_CAPABILITIES

_BCP47 = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
_PRIVATE_FIELDS = {
    "details",
    "confession",
    "graphic_detail",
    "story",
    "narrative",
    "raw_text",
    "prayer_text",
    "coordinates",
    "latitude",
    "longitude",
    "biometric",
    "payment_token",
    "card_number",
}


def _digest(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(data).hexdigest()


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"payload.{key} must be a non-empty string")
    return value.strip()


def _refuse_private(payload: dict[str, Any], code: str) -> None:
    if _PRIVATE_FIELDS & payload.keys():
        raise PermissionError(code)


@dataclass(frozen=True)
class ChurchConfig:
    church_id: str
    name: str
    locale: str
    timezone: str
    currency: str
    bible_translation: str
    campuses: tuple[str, ...]
    required_volunteers_per_service: int

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "ChurchConfig":
        church_id = _required_str(config, "church_id")
        name = _required_str(config, "name")
        locale = str(config.get("locale", "en-US"))
        if not _BCP47.match(locale):
            raise ValueError("config.locale must be a BCP47-like language tag")
        timezone = str(config.get("timezone", "UTC"))
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("config.timezone must be an IANA timezone") from exc
        currency = str(config.get("currency", "USD")).upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("config.currency must be a 3-letter currency code")
        bible_translation = str(config.get("bible_translation", "local-preferred"))
        campuses_raw = config.get("campuses", ["main"])
        if (
            not isinstance(campuses_raw, list)
            or not campuses_raw
            or not all(isinstance(x, str) and x for x in campuses_raw)
        ):
            raise ValueError("config.campuses must be a non-empty list of strings")
        required = config.get("required_volunteers_per_service", 3)
        if not isinstance(required, int) or isinstance(required, bool) or required < 0:
            raise ValueError("config.required_volunteers_per_service must be a non-negative integer")
        return cls(
            church_id,
            name,
            locale,
            timezone,
            currency,
            bible_translation,
            tuple(campuses_raw),
            required,
        )


class BibleGymEnvironment:
    """One isolated church world implementing GymAct's Environment protocol."""

    def __init__(self, config: ChurchConfig, *, requires_authority: bool = True) -> None:
        self.environment_id = f"urn:biblegym:environment:{config.church_id}:{uuid4().hex}"
        self.requires_authority = requires_authority
        self.config = config
        self._closed = False
        self._state: dict[str, Any] = {
            "people": {},
            "groups": {},
            "host_agreements": {},
            "events": {},
            "checkins": [],
            "child_checkins": [],
            "content": {},
            "sermons": {},
            "quests": {},
            "habit_stacks": {},
            "accountability": [],
            "quiz_results": [],
            "volunteers": {},
            "volunteer_assignments": [],
            "staffing_gaps": {},
            "service_routes": {},
            "bible_need_routes": [],
            "followups": [],
            "prayer_requests": [],
            "giving_intents": [],
            "reminders": [],
            "shares": [],
            "formation_steps": [],
            "feedback_consent": [],
            "care_handoffs": [],
            "points": {},
            "badges": {},
            "milestones": {},
            "effect_receipts": [],
        }

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return BIBLEGYM_CAPABILITIES

    def _summary(self) -> dict[str, Any]:
        s = self._state
        return {
            "church_id": self.config.church_id,
            "locale": self.config.locale,
            "timezone": self.config.timezone,
            "currency": self.config.currency,
            "people": len(s["people"]),
            "groups": len(s["groups"]),
            "events": len(s["events"]),
            "checkins": len(s["checkins"]),
            "sermons": len(s["sermons"]),
            "quests": len(s["quests"]),
            "quest_completions": sum(len(q.get("completed_by", [])) for q in s["quests"].values()),
            "volunteers": len(s["volunteers"]),
            "open_staffing_gaps": sum(g["status"] == "OPEN" for g in s["staffing_gaps"].values()),
            "service_routes": len(s["service_routes"]),
            "formation_steps": len(s["formation_steps"]),
            "care_handoffs": len(s["care_handoffs"]),
            "effect_receipts": len(s["effect_receipts"]),
        }

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return copy.deepcopy(self._summary())

    def _person(self, person_id: str) -> dict[str, Any]:
        try:
            return self._state["people"][person_id]
        except KeyError as exc:
            raise ValueError(f"unknown person: {person_id}") from exc

    def _volunteer(self, person_id: str) -> dict[str, Any]:
        try:
            return self._state["volunteers"][person_id]
        except KeyError as exc:
            raise ValueError(f"unknown volunteer candidate: {person_id}") from exc

    def _award(self, person_id: str, points: int, milestone: str | None = None) -> None:
        s = self._state
        s["points"][person_id] = s["points"].get(person_id, 0) + points
        total = s["points"][person_id]
        badges = s["badges"].setdefault(person_id, [])
        for threshold, badge in ((10, "first-steps"), (50, "steady-practice"), (100, "faithful-rhythm")):
            if total >= threshold and badge not in badges:
                badges.append(badge)
        if milestone:
            s["milestones"].setdefault(person_id, []).append(milestone)

    def _staffing_health(self, event_id: str | None = None) -> list[dict[str, Any]]:
        s = self._state
        events = [s["events"][event_id]] if event_id else list(s["events"].values())
        result: list[dict[str, Any]] = []
        for event in events:
            eid = event["event_id"]
            active = [
                a
                for a in s["volunteer_assignments"]
                if a["event_id"] == eid and a["status"] == "ASSIGNED"
            ]
            required = event["required_volunteers"]
            gaps = [g for g in s["staffing_gaps"].values() if g["event_id"] == eid]
            result.append(
                {
                    "event_id": eid,
                    "required": required,
                    "assigned": len(active),
                    "vacancies": max(required - len(active), 0),
                    "open_gap_ids": [g["gap_id"] for g in gaps if g["status"] == "OPEN"],
                    "escalated_gap_ids": [g["gap_id"] for g in gaps if g["status"] == "ESCALATED"],
                }
            )
        return result

    def _mutate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        b = capability.binding
        s = self._state

        if b == "register_person":
            pid = _required_str(payload, "person_id")
            s["people"][pid] = {
                "person_id": pid,
                "display_name": str(payload.get("display_name", pid)),
                "locale": str(payload.get("locale", self.config.locale)),
                "roles": sorted(set(payload.get("roles", ["attendee"]))),
                "leaderboard_opt_in": bool(payload.get("leaderboard_opt_in", False)),
                "auth_assurance": str(payload.get("auth_assurance", "session")),
                "location_consent": bool(payload.get("location_consent", False)),
            }
            return {"person_id": pid}

        if b == "create_group":
            gid = _required_str(payload, "group_id")
            s["groups"][gid] = {
                "group_id": gid,
                "name": _required_str(payload, "name"),
                "members": [],
                "owner_ref": str(payload.get("owner_ref", f"church:{self.config.church_id}")),
            }
            return {"group_id": gid}

        if b == "join_group":
            pid = _required_str(payload, "person_id")
            gid = _required_str(payload, "group_id")
            self._person(pid)
            if gid not in s["groups"]:
                raise ValueError(f"unknown group: {gid}")
            if pid not in s["groups"][gid]["members"]:
                s["groups"][gid]["members"].append(pid)
            return {"joined": True}

        if b == "host_autonomous_group":
            aid = _required_str(payload, "agreement_id")
            rec = {
                "agreement_id": aid,
                "group_name": _required_str(payload, "group_name"),
                "space": _required_str(payload, "space"),
                "cadence": _required_str(payload, "cadence"),
                "group_governance": "AUTONOMOUS",
                "church_role": "FACILITY_HOST_NOT_OWNER",
                "church_controls_program": False,
            }
            s["host_agreements"][aid] = rec
            return rec

        if b == "create_event":
            eid = _required_str(payload, "event_id")
            campus = str(payload.get("campus_id", self.config.campuses[0]))
            if campus not in self.config.campuses:
                raise ValueError("unknown campus")
            required = payload.get("required_volunteers", self.config.required_volunteers_per_service)
            if not isinstance(required, int) or isinstance(required, bool) or required < 0:
                raise ValueError("required_volunteers must be a non-negative integer")
            s["events"][eid] = {
                "event_id": eid,
                "name": _required_str(payload, "name"),
                "campus_id": campus,
                "required_volunteers": required,
                "rsvps": [],
            }
            return {"event_id": eid, "required_volunteers": required}

        if b == "rsvp_event":
            pid = _required_str(payload, "person_id")
            eid = _required_str(payload, "event_id")
            self._person(pid)
            if eid not in s["events"]:
                raise ValueError("unknown event")
            if pid not in s["events"][eid]["rsvps"]:
                s["events"][eid]["rsvps"].append(pid)
            return {"rsvp": True}

        if b in {"check_in", "location_check_in"}:
            pid = _required_str(payload, "person_id")
            eid = _required_str(payload, "event_id")
            person = self._person(pid)
            if eid not in s["events"]:
                raise ValueError("unknown event")
            if b == "location_check_in":
                _refuse_private(payload, "PRECISE_LOCATION_STORAGE_REFUSED")
                if not (person["location_consent"] and payload.get("inside_geofence") is True):
                    raise PermissionError("LOCATION_CONSENT_OR_GEOFENCE_REFUSED")
            rec = {
                "person_id": pid,
                "event_id": eid,
                "mode": "location" if b == "location_check_in" else "manual",
            }
            s["checkins"].append(rec)
            return rec

        if b == "child_check_in":
            guardian = _required_str(payload, "guardian_id")
            self._person(guardian)
            child_ref = _required_str(payload, "child_ref")
            token = _required_str(payload, "pickup_token")
            rec = {
                "guardian_id": guardian,
                "child_ref": child_ref,
                "event_id": _required_str(payload, "event_id"),
                "pickup_token_digest": hashlib.sha256(token.encode()).hexdigest(),
            }
            s["child_checkins"].append(rec)
            return rec

        if b == "publish_content":
            cid = _required_str(payload, "content_id")
            s["content"][cid] = {
                "content_id": cid,
                "title": _required_str(payload, "title"),
                "kind": str(payload.get("kind", "note")),
                "offline": bool(payload.get("offline", True)),
                "scripture_refs": list(payload.get("scripture_refs", [])),
            }
            return {"content_id": cid}

        if b == "schedule_reminder":
            rec = {
                "person_id": _required_str(payload, "person_id"),
                "subject_ref": _required_str(payload, "subject_ref"),
                "local_time": _required_str(payload, "local_time"),
                "delivery": "INTENT_ONLY",
            }
            s["reminders"].append(rec)
            return rec

        if b == "share_invite":
            rec = {
                "actor_id": _required_str(payload, "actor_id"),
                "subject_ref": _required_str(payload, "subject_ref"),
                "channel": str(payload.get("channel", "link")),
                "delivery": "INTENT_ONLY",
            }
            s["shares"].append(rec)
            return rec

        if b == "record_giving_intent":
            _refuse_private(payload, "PAYMENT_CREDENTIAL_STORAGE_REFUSED")
            amount = payload.get("amount_minor")
            if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
                raise ValueError("payload.amount_minor must be a non-negative integer")
            rec = {
                "person_id": _required_str(payload, "person_id"),
                "amount_minor": amount,
                "currency": str(payload.get("currency", self.config.currency)).upper(),
                "purpose": str(payload.get("purpose", "general")),
                "payment_status": "NOT_ACTUATED",
            }
            s["giving_intents"].append(rec)
            return rec

        if b == "publish_sermon":
            sid = _required_str(payload, "sermon_id")
            refs = payload.get("scripture_refs")
            if not isinstance(refs, list) or not refs:
                raise ValueError("scripture_refs must be non-empty")
            s["sermons"][sid] = {
                "sermon_id": sid,
                "title": _required_str(payload, "title"),
                "scripture_refs": refs,
                "points": list(payload.get("points", [])),
            }
            return {"sermon_id": sid}

        if b == "create_quest_from_sermon":
            qid = _required_str(payload, "quest_id")
            sid = _required_str(payload, "sermon_id")
            if sid not in s["sermons"]:
                raise ValueError("unknown sermon")
            minutes = int(payload.get("minutes", 2))
            if minutes < 1 or minutes > 15:
                raise ValueError("quest minutes must be 1..15")
            scripture_ref = _required_str(payload, "scripture_ref")
            if scripture_ref not in s["sermons"][sid]["scripture_refs"]:
                raise ValueError("quest scripture_ref must be grounded in the sermon")
            s["quests"][qid] = {
                "quest_id": qid,
                "sermon_id": sid,
                "scripture_ref": scripture_ref,
                "practice": _required_str(payload, "practice"),
                "minutes": minutes,
                "completed_by": [],
            }
            return {"quest_id": qid}

        if b == "complete_quest":
            pid = _required_str(payload, "person_id")
            qid = _required_str(payload, "quest_id")
            self._person(pid)
            quest = s["quests"].get(qid)
            if quest is None:
                raise ValueError("unknown quest")
            if pid not in quest["completed_by"]:
                quest["completed_by"].append(pid)
                self._award(pid, 10, f"quest:{qid}")
            return {"points": s["points"].get(pid, 0), "badges": list(s["badges"].get(pid, []))}

        if b == "set_habit_stack":
            pid = _required_str(payload, "person_id")
            self._person(pid)
            minutes = int(payload.get("minutes", 2))
            if minutes < 1 or minutes > 15:
                raise ValueError("practice minutes must be 1..15")
            rec = {
                "cue": _required_str(payload, "after"),
                "practice": _required_str(payload, "practice"),
                "minutes": minutes,
                "scripture_ref": _required_str(payload, "scripture_ref"),
            }
            s["habit_stacks"][pid] = rec
            return rec

        if b == "link_accountability":
            person_id = _required_str(payload, "person_id")
            partner_id = _required_str(payload, "partner_id")
            self._person(person_id)
            self._person(partner_id)
            if payload.get("person_consents") is not True or payload.get("partner_consents") is not True:
                raise PermissionError("BILATERAL_CONSENT_REQUIRED")
            edge = sorted([person_id, partner_id])
            if edge not in s["accountability"]:
                s["accountability"].append(edge)
            return {"linked": True}

        if b == "submit_scripture_quiz":
            pid = _required_str(payload, "person_id")
            self._person(pid)
            score = payload.get("score")
            if not isinstance(score, int) or not 0 <= score <= 100:
                raise ValueError("score must be 0..100")
            rec = {
                "person_id": pid,
                "scripture_ref": _required_str(payload, "scripture_ref"),
                "score": score,
            }
            s["quiz_results"].append(rec)
            self._award(pid, score // 10)
            return rec

        if b == "recruit_volunteer":
            pid = _required_str(payload, "person_id")
            self._person(pid)
            existing = s["volunteers"].get(pid)
            if existing and existing["status"] not in {"OPTED_OUT", "CANDIDATE"}:
                raise ValueError("volunteer already beyond candidate state")
            rec = {
                "person_id": pid,
                "ministry": str(payload.get("ministry", "welcome")),
                "gifts": sorted(set(payload.get("gifts", []))),
                "status": "CANDIDATE",
                "notifications": True,
                "cochair": False,
            }
            s["volunteers"][pid] = rec
            return copy.deepcopy(rec)

        if b == "onboard_volunteer":
            pid = _required_str(payload, "person_id")
            volunteer = self._volunteer(pid)
            if volunteer["status"] != "CANDIDATE":
                raise ValueError("volunteer must be CANDIDATE before onboarding")
            if payload.get("orientation_complete") is not True or payload.get("role_acknowledged") is not True:
                raise PermissionError("VOLUNTEER_READINESS_REFUSED")
            volunteer["status"] = "ONBOARDED"
            return copy.deepcopy(volunteer)

        if b == "assign_volunteer":
            pid = _required_str(payload, "person_id")
            eid = _required_str(payload, "event_id")
            volunteer = self._volunteer(pid)
            if volunteer["status"] != "ONBOARDED":
                raise PermissionError("VOLUNTEER_NOT_ONBOARDED")
            if eid not in s["events"]:
                raise ValueError("unknown event")
            rec = {
                "assignment_id": str(payload.get("assignment_id", f"assignment:{uuid4().hex}")),
                "person_id": pid,
                "event_id": eid,
                "role": _required_str(payload, "role"),
                "route": str(payload.get("route", "service")),
                "status": "ASSIGNED",
            }
            s["volunteer_assignments"].append(rec)
            return copy.deepcopy(rec)

        if b == "assign_cochair":
            pid = _required_str(payload, "person_id")
            volunteer = self._volunteer(pid)
            if volunteer["status"] != "ONBOARDED":
                raise PermissionError("VOLUNTEER_NOT_ONBOARDED")
            volunteer["cochair"] = True
            if "cochair" not in s["people"][pid]["roles"]:
                s["people"][pid]["roles"].append("cochair")
                s["people"][pid]["roles"].sort()
            return {"person_id": pid, "cochair": True}

        if b == "opt_out_volunteer":
            pid = _required_str(payload, "person_id")
            volunteer = self._volunteer(pid)
            volunteer["status"] = "OPTED_OUT"
            volunteer["notifications"] = False
            released = 0
            for assignment in s["volunteer_assignments"]:
                if assignment["person_id"] == pid and assignment["status"] == "ASSIGNED":
                    assignment["status"] = "RELEASED_OPT_OUT"
                    released += 1
            return {"person_id": pid, "status": "OPTED_OUT", "notifications": False, "released": released}

        if b == "record_no_show":
            assignment_id = _required_str(payload, "assignment_id")
            assignment = next((a for a in s["volunteer_assignments"] if a["assignment_id"] == assignment_id), None)
            if assignment is None:
                raise ValueError("unknown assignment")
            assignment["status"] = "NO_SHOW"
            gap_id = str(payload.get("gap_id", f"gap:{uuid4().hex}"))
            gap = {
                "gap_id": gap_id,
                "event_id": assignment["event_id"],
                "role": assignment["role"],
                "source_assignment": assignment_id,
                "status": "OPEN",
                "governance_route": None,
            }
            s["staffing_gaps"][gap_id] = gap
            return copy.deepcopy(gap)

        if b == "escalate_staffing_gap":
            gap_id = _required_str(payload, "gap_id")
            gap = s["staffing_gaps"].get(gap_id)
            if gap is None:
                raise ValueError("unknown staffing gap")
            gap["status"] = "ESCALATED"
            gap["governance_route"] = _required_str(payload, "governance_route")
            return copy.deepcopy(gap)

        if b == "create_service_route":
            route_id = _required_str(payload, "route_id")
            rec = {
                "route_id": route_id,
                "need_category": _required_str(payload, "need_category"),
                "route": _required_str(payload, "route"),
                "door": _required_str(payload, "door"),
                "role": _required_str(payload, "role"),
                "assignment_ref": payload.get("assignment_ref"),
                "evidence_ref": payload.get("evidence_ref"),
                "receipt_ref": payload.get("receipt_ref"),
                "follow_up_status": "PENDING",
            }
            s["service_routes"][route_id] = rec
            return copy.deepcopy(rec)

        if b == "route_bible_need":
            _refuse_private(payload, "BIBLE_NEED_NARRATIVE_STORAGE_REFUSED")
            target = _required_str(payload, "target")
            allowed = {"content", "group", "mentor", "pastoral"}
            if target not in allowed:
                raise ValueError(f"target must be one of {sorted(allowed)}")
            rec = {
                "person_id": _required_str(payload, "person_id"),
                "topic": _required_str(payload, "topic"),
                "scripture_ref": _required_str(payload, "scripture_ref"),
                "target": target,
                "status": "ROUTED",
            }
            s["bible_need_routes"].append(rec)
            return rec

        if b == "record_follow_up":
            route_id = _required_str(payload, "route_id")
            route = s["service_routes"].get(route_id)
            if route is None:
                raise ValueError("unknown service route")
            rec = {
                "route_id": route_id,
                "person_id": _required_str(payload, "person_id"),
                "outcome_code": _required_str(payload, "outcome_code"),
                "evidence_ref": payload.get("evidence_ref"),
            }
            s["followups"].append(rec)
            route["follow_up_status"] = "COMPLETED"
            return rec

        if b == "record_prayer_request":
            _refuse_private(payload, "RAW_PRAYER_TEXT_STORAGE_REFUSED")
            if payload.get("consent") is not True:
                raise PermissionError("PRAYER_REQUEST_CONSENT_REQUIRED")
            rec = {
                "person_id": _required_str(payload, "person_id"),
                "category": _required_str(payload, "category"),
                "visibility": str(payload.get("visibility", "private-leaders")),
                "status": "REQUESTED",
            }
            s["prayer_requests"].append(rec)
            return rec

        if b == "record_formation_step":
            _refuse_private(payload, "RAW_CONFESSION_STORAGE_REFUSED")
            pid = _required_str(payload, "person_id")
            self._person(pid)
            stage = _required_str(payload, "stage").lower()
            if stage not in {"admit", "believe", "surrender", "practice"}:
                raise ValueError("stage must be Admit|Believe|Surrender|Practice")
            rec = {
                "person_id": pid,
                "stage": stage,
                "scripture_ref": _required_str(payload, "scripture_ref"),
                "setup_category": str(payload.get("setup_category", "unspecified")),
                "next_faithful_action": _required_str(payload, "next_faithful_action"),
                "risk": str(payload.get("risk", "none")),
            }
            s["formation_steps"].append(rec)
            self._award(pid, 5, f"formation:{stage}")
            return rec

        if b == "grant_feedback_consent":
            rec = {
                "person_id": _required_str(payload, "person_id"),
                "from_ref": _required_str(payload, "from_ref"),
                "granted": bool(payload.get("granted", True)),
            }
            s["feedback_consent"].append(rec)
            return rec

        if b == "record_care_handoff":
            _refuse_private(payload, "CARE_HANDOFF_DETAILS_REFUSED")
            category = _required_str(payload, "category")
            if category not in {"pastoral", "counseling", "sponsor", "mentor", "safety", "professional"}:
                raise ValueError("unsupported care category")
            rec = {
                "person_id": _required_str(payload, "person_id"),
                "category": category,
                "reason_code": _required_str(payload, "reason_code"),
                "status": "ROUTED",
            }
            s["care_handoffs"].append(rec)
            return rec

        raise ValueError(f"unsupported BibleGym binding: {b}")

    def _read(self, binding: str, payload: dict[str, Any]) -> Any:
        s = self._state
        if binding == "dashboard":
            pid = _required_str(payload, "actor_id")
            self._person(pid)
            return {
                "person": copy.deepcopy(s["people"][pid]),
                "groups": [g["group_id"] for g in s["groups"].values() if pid in g["members"]],
                "milestones": list(s["milestones"].get(pid, [])),
                "points": s["points"].get(pid, 0),
            }
        if binding == "leaderboard":
            return sorted(
                (
                    {"person_id": pid, "points": points}
                    for pid, points in s["points"].items()
                    if s["people"].get(pid, {}).get("leaderboard_opt_in")
                ),
                key=lambda item: (-item["points"], item["person_id"]),
            )
        if binding == "milestones":
            return list(s["milestones"].get(_required_str(payload, "person_id"), []))
        if binding == "offline_content":
            return [copy.deepcopy(item) for item in s["content"].values() if item.get("offline")]
        if binding == "devotion_prompt_packet":
            pid = _required_str(payload, "person_id")
            self._person(pid)
            sermons = list(s["sermons"].values())
            latest = sermons[-1] if sermons else None
            return {
                "person_id": pid,
                "locale": self.config.locale,
                "bible_translation": self.config.bible_translation,
                "sermon": copy.deepcopy(latest),
                "habit_stack": copy.deepcopy(s["habit_stacks"].get(pid)),
                "authority": "CONSTRUCT_ONLY_NO_DO",
            }
        if binding == "staffing_health":
            event_id = payload.get("event_id")
            if event_id is not None and event_id not in s["events"]:
                raise ValueError("unknown event")
            return self._staffing_health(event_id)
        if binding == "service_route":
            route_id = _required_str(payload, "route_id")
            if route_id not in s["service_routes"]:
                raise ValueError("unknown service route")
            return copy.deepcopy(s["service_routes"][route_id])
        raise ValueError(f"unsupported read binding: {binding}")

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        before = self._summary()
        before_digest = _digest(self._state)
        consequence = getattr(capability.consequence, "value", str(capability.consequence))
        result = self._read(capability.binding, payload) if consequence == "READ" else self._mutate(capability, payload)
        after_digest = _digest(self._state)
        if before_digest != after_digest:
            receipt = {
                "sequence": len(self._state["effect_receipts"]) + 1,
                "capability": capability.iri,
                "before_sha256": before_digest,
                "after_sha256": after_digest,
            }
            self._state["effect_receipts"].append(receipt)
        return {
            "before": before,
            "after": self._summary(),
            "capability": capability.iri,
            "result": copy.deepcopy(result),
        }

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = self._summary()
        return all(observed.get(key) == value for key, value in expected.items()), observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return {"church_id": self.config.church_id, "state": copy.deepcopy(self._state)}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        if checkpoint.get("church_id") != self.config.church_id:
            raise ValueError("checkpoint belongs to a different church")
        self._state = copy.deepcopy(checkpoint["state"])

    async def teardown(self) -> None:
        self._closed = True


class BibleGymProvider:
    name = "biblegym"
    materialization_requires_authority = False

    async def materialize(self, *, scenario: str | None, config: dict[str, Any]) -> BibleGymEnvironment:
        del scenario
        cfg = ChurchConfig.from_config(config)
        required = config.get("requires_authority", True)
        if not isinstance(required, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return BibleGymEnvironment(cfg, requires_authority=required)
