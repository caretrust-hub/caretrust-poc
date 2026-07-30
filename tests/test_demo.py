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
        '<option value="corrected">Human-corrected expiration date</option>',
        'id="source-transition"',
        'aria-describedby="source-transition"',
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


def test_workflow_stages_are_noninteractive_progress_indicators() -> None:
    for step in ("evidence", "draft", "review", "source", "claim", "decision"):
        assert f'<li data-step="{step}"' in HTML
    assert '<button type="button" data-step=' not in HTML
    assert "stepButtons" not in JAVASCRIPT
    assert "stepIndicators" in JAVASCRIPT


def test_evidence_is_rebound_and_reset_for_each_scenario() -> None:
    for field in ("name", "id", "credential", "jurisdiction", "expiration"):
        assert f'data-evidence-field="{field}"' in HTML
    assert "button.dataset.evidence = evidence[field];" in JAVASCRIPT
    assert "Evidence: ${scenario.value}-${field}" in JAVASCRIPT
    assert (
        'evidencePopover.textContent = "Select an evidence link to reveal the '
        'supporting source text.";'
    ) in JAVASCRIPT


def test_revocation_requires_a_subsequent_request_and_permit_is_idempotent() -> None:
    assert 'if (claimStatus === "revoked")' in JAVASCRIPT
    assert 'showDecision("pending", "Claim revoked"' in JAVASCRIPT
    assert 'requestAction.textContent = "Request revoked claim";' in JAVASCRIPT
    assert '"Application request denied"' in JAVASCRIPT
    assert 'if (claimStatus !== "active" || permitRecorded) return;' in JAVASCRIPT
    assert "permitRecorded = true;" in JAVASCRIPT


def test_demo_covers_tested_safety_states_and_links_to_evidence() -> None:
    for value in (
        "REVIEW_DEFERRED",
        "SOURCE_MISMATCH",
        "POLICY_REQUIREMENTS_SATISFIED",
        "TOKEN_REVOKED",
        "Injection ignored; draft contract held",
    ):
        assert value in JAVASCRIPT
    for url in (
        "https://github.com/caretrust-hub/caretrust-poc",
        "artifacts/evaluation/20260730T085655.959974Z/REPORT.md",
        "#project-controls-and-limitations",
    ):
        assert url in HTML
