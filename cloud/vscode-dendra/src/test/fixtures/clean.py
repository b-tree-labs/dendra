"""Fixture: clean classifier (AUTO_LIFTABLE)."""


def triage(text: str) -> str:
    if "bug" in text:
        return "bug"
    if "feature" in text:
        return "feature"
    return "other"
