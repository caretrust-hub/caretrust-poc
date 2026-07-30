"""Static accessibility and safety contracts for the dependency-free demo."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "demo" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "demo" / "styles.css").read_text(encoding="utf-8")
JAVASCRIPT = (ROOT / "demo" / "app.js").read_text(encoding="utf-8")


def test_demo_has_accessible_structure_and_status_text() -> None:
    required = (
        '<html lang="en">',
        'class="skip-link"',
        "<main",
        "<nav",
        'aria-label="CareTrust workflow"',
        '<label id="scenario-label" for="scenario">',
        'role="status"',
        'aria-live="polite"',
        "Draft · not verified",
        "Synthetic data only",
    )
    for value in required:
        assert value in HTML
    assert HTML.count("<h1") == 1


def test_demo_declares_visible_focus_and_responsive_layout() -> None:
    assert ":focus-visible" in CSS
    assert "@media (max-width: 700px)" in CSS
    assert "prefers-reduced-motion" in CSS


def test_demo_covers_tested_safety_states_without_external_dependencies() -> None:
    for value in (
        "REVIEW_DEFERRED",
        "SOURCE_MISMATCH",
        "POLICY_REQUIREMENTS_SATISFIED",
        "TOKEN_REVOKED",
        "Injection ignored; draft contract held",
    ):
        assert value in JAVASCRIPT
    assert "https://" not in HTML
