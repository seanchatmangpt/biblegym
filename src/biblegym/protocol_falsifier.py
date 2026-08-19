"""Formation-domain falsifier for portable protocol invariants.

Interpretive, pedagogical, or formation output can inform SELECT/CONSTRUCT but
cannot self-award standing or authority for consequential action.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class FormationProtocolObservation:
    expected_refusal: str | None
    actual_code: str
    state_before: Any
    state_after: Any
    consequential: bool
    authority_present: bool
    receipt_present: bool
    self_awarded_standing: bool = False


def falsify(o: FormationProtocolObservation) -> tuple[bool, str]:
    if o.self_awarded_standing:
        return False, "FALSIFIED:SELF_AWARDED_STANDING"
    if o.expected_refusal is not None:
        if o.actual_code != o.expected_refusal:
            return False, "FALSIFIED:WRONG_REFUSAL"
        if o.state_before != o.state_after:
            return False, "FALSIFIED:REFUSED_PATH_CHANGED_WORLD"
        return True, "CONFORMS:REFUSAL"
    if o.consequential and not o.authority_present:
        return False, "FALSIFIED:AMBIENT_AUTHORITY"
    if o.consequential and not o.receipt_present:
        return False, "FALSIFIED:UNRECEIPTED_CONSEQUENCE"
    return True, "CONFORMS:CONSEQUENCE"
