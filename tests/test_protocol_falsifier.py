from biblegym.protocol_falsifier import FormationProtocolObservation, falsify


def test_formation_output_cannot_self_award_standing():
    observation = FormationProtocolObservation(
        None, "ALLOWED", {}, {}, False, False, False, self_awarded_standing=True
    )
    assert falsify(observation) == (False, "FALSIFIED:SELF_AWARDED_STANDING")


def test_refusal_is_inert():
    before = {"formation": ["read"]}
    observation = FormationProtocolObservation(
        "REFUSED:AUTHORITY_REQUIRED",
        "REFUSED:AUTHORITY_REQUIRED",
        before,
        dict(before),
        True,
        False,
        False,
    )
    assert falsify(observation) == (True, "CONFORMS:REFUSAL")


def test_consequential_transition_requires_receipt():
    observation = FormationProtocolObservation(
        None,
        "ALLOWED",
        {"actions": []},
        {"actions": ["external-action"]},
        True,
        True,
        False,
    )
    assert falsify(observation) == (False, "FALSIFIED:UNRECEIPTED_CONSEQUENCE")
