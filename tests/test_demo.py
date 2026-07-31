"""Static accessibility, truthfulness, and workflow contracts for the demo."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "demo" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "demo" / "styles.css").read_text(encoding="utf-8")
JAVASCRIPT = (ROOT / "demo" / "app.js").read_text(encoding="utf-8")
README = (ROOT / "demo" / "README.md").read_text(encoding="utf-8")


def test_demo_has_accessible_structure_and_keyboard_treatment() -> None:
    required = (
        '<html lang="en">',
        'class="skip-link"',
        '<main id="workspace">',
        'aria-label="CareTrust workflow"',
        '<label id="scenario-label" for="scenario">',
        'role="status"',
        'aria-live="polite"',
        ':focus-visible',
        '@media (max-width: 700px)',
        'prefers-reduced-motion',
    )
    for value in required:
        assert value in HTML or value in CSS
    assert HTML.count("<h1") == 1
    assert '<button type="button" data-step=' not in HTML


def test_hero_is_truthful_and_platform_horizon_is_visible() -> None:
    for value in (
        "Activate a trusted care workforce",
        "across applications",
        "Phase 1 design prototype",
        "Synthetic data only",
        "Exact-message local trace",
        "No live HIE or EHR",
        "Now · executable local",
        "Secondary technical proof · retained AWS",
        "Network path · local federation laboratory",
        "Provider workforce activation",
        "Credential evidence compiler",
        "Independent organizations and applications",
        "operational federation and live HIE/EHR access remain planned",
        'href="network.html"',
    ):
        assert value in HTML
    overclaims = (
        "Live TRL 3",
        "Reuse trust everywhere",
        "live federation",
        "live status",
    )
    for value in overclaims:
        assert value.lower() not in HTML.lower()


def test_demo_shows_retained_ocr_and_model_boundary() -> None:
    for value in (
        "Synthetic legacy document",
        "Retained Amazon Textract result",
        "Amazon Textract DetectDocumentText",
        "OCR evidence, not authority",
        'class="ocr-highlight"',
        'class="ocr-lines"',
        "<meter",
        "Input SHA-256",
        "Response SHA-256",
        "Retained Bedrock/Qwen structured draft",
        "No live model call occurs in this browser",
        "Retained Textract line:",
    ):
        assert value in HTML or value in JAVASCRIPT
    assert "fetch(" not in JAVASCRIPT
    assert "XMLHttpRequest" not in JAVASCRIPT


def test_trust_actions_are_explicit_and_independent() -> None:
    for control in (
        'id="review-action"',
        'id="source-action"',
        'id="claim-action"',
    ):
        assert control in HTML
    for label in (
        "1 · Approve human review",
        "2 · Run synthetic source check",
        "3 · Create signed claim",
        "Each action changes one gate only",
    ):
        assert label in HTML
    assert 'reviewAction.addEventListener("click"' in JAVASCRIPT
    assert 'sourceAction.addEventListener("click"' in JAVASCRIPT
    assert 'claimAction.addEventListener("click"' in JAVASCRIPT
    assert "sourceAction.disabled = false;" in JAVASCRIPT
    assert "claimAction.disabled = false;" in JAVASCRIPT
    assert "This action did not run a source check" in JAVASCRIPT
    assert "This action did not create or sign a claim" in JAVASCRIPT


def test_safety_scenarios_remain_fail_closed_and_evidence_bound() -> None:
    for scenario_name in ("clean", "corrected", "ambiguous", "mismatch", "injection"):
        assert f"{scenario_name}:" in JAVASCRIPT
    for result in (
        "REVIEW_DEFERRED",
        "SOURCE_MISMATCH",
        "Injection ignored; schema held",
        "no source check started",
        "signing remains unavailable",
    ):
        assert result in JAVASCRIPT
    for field in ("name", "id", "credential", "jurisdiction", "expiration"):
        assert f'data-evidence-field="{field}"' in HTML


def test_two_apps_use_same_claim_with_distinct_local_policies() -> None:
    for value in (
        "The same claim, two independent application decisions",
        'id="stable-claim-id"',
        'id="app-a-action"',
        'id="app-b-action"',
        'id="app-a-receipt"',
        'id="app-b-receipt"',
        "urn:caretrust:app:onboarding",
        "workforce-onboarding",
        "HI-CNA-ACTIVE-v1",
        "urn:caretrust:app:scheduling",
        "shift-assignment",
        "SHIFT-CNA-ELIGIBLE-v2",
    ):
        assert value in HTML
    assert JAVASCRIPT.count("${claimIdFor(item)}") >= 3
    assert "Independent local policy receipt" in JAVASCRIPT


def test_revocation_requires_two_permits_then_fresh_app_b_request() -> None:
    for value in (
        "workflow.appAPermit && workflow.appBPermit",
        "Revoke after both permits",
        "Make fresh App B request",
        "DENY / TOKEN_REVOKED",
        "TOKEN_REVOKED",
        "Earlier permit receipts remain historical",
        "existing-session termination is claimed",
    ):
        assert value in HTML or value in JAVASCRIPT
    assert "workflow.revoked = true;" in JAVASCRIPT
    assert "workflow.freshBRequested = true;" in JAVASCRIPT
    assert "appBAction.disabled = false;" in JAVASCRIPT


def test_evidence_limits_metrics_are_frozen_and_test_count_is_not_hardcoded() -> None:
    for value in (
        "Evidence &amp; limits",
        "Frozen synthetic evaluation results",
        "20/20",
        "6/20",
        "0.286",
        "7/7",
        "material-risk cases carried a blocking marker",
        "not field outcomes",
        "cross-organization federation",
    ):
        assert value in HTML
    assert "114 tests" not in HTML
    assert "114 tests" not in JAVASCRIPT
    assert "114 tests" not in README


def test_standards_are_secondary_and_status_labeled() -> None:
    assert '<details class="technical-proof"' in HTML
    for value in (
        'data-evidence-status="executed_local"',
        'data-evidence-status="contract_tested"',
        'data-evidence-status="local_simulation"',
        "Executed local",
        "Contract tested",
        "Local simulation",
        "FHIR R4 projection",
        "OID4VC exchange",
        "Federation-shaped trust resolution",
        "no deployed federation or network call",
    ):
        assert value in HTML
    for url in (
        "https://github.com/caretrust-hub/caretrust-poc",
        "artifacts/evaluation/20260730T085655.959974Z/REPORT.md",
        "#project-controls-and-limitations",
    ):
        assert url in HTML
