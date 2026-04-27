"""Fixture: side_effect_evidence pattern (REFUSED).

Mirrors the inline source in tests/test_analyzer_hazards.py
(test_charge_then_branch_is_refused_with_specific_diagnostic).
"""


def maybe_charge(req):
    response = api.charge(req)
    if response.ok:
        return "charged"
    return "skipped"
