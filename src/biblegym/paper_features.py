from __future__ import annotations

import copy
import re
from typing import Any

from .compat import Capability
from .environment import BibleGymEnvironment, ChurchConfig, _required_str


class PaperFeatureEnvironment(BibleGymEnvironment):
    """Paper-specific UX capabilities layered over the core church world."""

    def __init__(self, config: ChurchConfig, *, requires_authority: bool = True) -> None:
        super().__init__(config, requires_authority=requires_authority)
        self._state.update(
            {
                "next_steps": {},
                "content_notes": [],
                "message_intents": [],
                "contact_intents": [],
                "auth_assertions": [],
            }
        )

    @staticmethod
    def _refuse_freeform(payload: dict[str, Any], code: str) -> None:
        forbidden = {
            "body",
            "details",
            "raw_text",
            "note_text",
            "prayer_text",
            "narrative",
            "biometric",
            "coordinates",
            "latitude",
            "longitude",
        }
        if forbidden & payload.keys():
            raise PermissionError(code)

    def _mutate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        binding = capability.binding
        state = self._state

        if binding == "set_next_step":
            person_id = _required_str(payload, "person_id")
            self._person(person_id)
            status = str(payload.get("status", "ACTIVE")).upper()
            if status not in {"ACTIVE", "COMPLETED"}:
                raise ValueError("status must be ACTIVE|COMPLETED")
            result = {
                "person_id": person_id,
                "step_ref": _required_str(payload, "step_ref"),
                "status": status,
            }
            state["next_steps"][person_id] = result
            return result

        if binding == "qr_check_in":
            person_id = _required_str(payload, "person_id")
            event_id = _required_str(payload, "event_id")
            self._person(person_id)
            if event_id not in state["events"]:
                raise ValueError("unknown event")
            if _required_str(payload, "qr_subject_ref") != f"event:{event_id}":
                raise PermissionError("QR_SUBJECT_MISMATCH_REFUSED")
            result = {"person_id": person_id, "event_id": event_id, "mode": "qr"}
            state["checkins"].append(result)
            return result

        if binding == "record_content_note":
            self._refuse_freeform(payload, "RAW_NOTE_STORAGE_REFUSED")
            person_id = _required_str(payload, "person_id")
            content_id = _required_str(payload, "content_id")
            self._person(person_id)
            if content_id not in state["content"]:
                raise ValueError("unknown content")
            digest = _required_str(payload, "note_digest")
            if not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
                raise ValueError("note_digest must be a 64-hex digest")
            result = {
                "person_id": person_id,
                "content_id": content_id,
                "note_digest": digest.lower(),
                "encrypted_ref": _required_str(payload, "encrypted_ref"),
            }
            state["content_notes"].append(result)
            return result

        if binding == "message_intent":
            self._refuse_freeform(payload, "FREEFORM_MESSAGE_STORAGE_REFUSED")
            result = {
                "actor_id": _required_str(payload, "actor_id"),
                "recipient_ref": _required_str(payload, "recipient_ref"),
                "subject_ref": _required_str(payload, "subject_ref"),
                "template_ref": _required_str(payload, "template_ref"),
                "delivery": "INTENT_ONLY",
            }
            state["message_intents"].append(result)
            return result

        if binding == "contact_intent":
            action = _required_str(payload, "action").lower()
            if action not in {"call", "text", "email"}:
                raise ValueError("action must be call|text|email")
            result = {
                "actor_id": _required_str(payload, "actor_id"),
                "contact_ref": _required_str(payload, "contact_ref"),
                "action": action,
                "delivery": "INTENT_ONLY",
            }
            state["contact_intents"].append(result)
            return result

        if binding == "record_biometric_assertion":
            self._refuse_freeform(payload, "BIOMETRIC_MATERIAL_STORAGE_REFUSED")
            person_id = _required_str(payload, "person_id")
            person = self._person(person_id)
            verified = payload.get("verified") is True
            result = {
                "person_id": person_id,
                "verified": verified,
                "source": "PLATFORM_ASSERTION",
            }
            state["auth_assertions"].append(result)
            if verified:
                person["auth_assurance"] = "platform-biometric-asserted"
            return result

        return super()._mutate(capability, payload)

    def _read(self, binding: str, payload: dict[str, Any]) -> Any:
        if binding == "content_sync_manifest":
            notes_by_content: dict[str, int] = {}
            for note in self._state["content_notes"]:
                content_id = note["content_id"]
                notes_by_content[content_id] = notes_by_content.get(content_id, 0) + 1
            return [
                {**copy.deepcopy(item), "note_refs": notes_by_content.get(item["content_id"], 0)}
                for item in self._state["content"].values()
                if item.get("offline")
            ]
        return super()._read(binding, payload)


class BibleGymProvider:
    name = "biblegym"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> PaperFeatureEnvironment:
        del scenario
        church = ChurchConfig.from_config(config)
        required = config.get("requires_authority", True)
        if not isinstance(required, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return PaperFeatureEnvironment(church, requires_authority=required)
