"""Static truthfulness, accessibility, and workflow contracts for v0.3 console."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "demo" / "network.html").read_text(encoding="utf-8")
CSS = (ROOT / "demo" / "network.css").read_text(encoding="utf-8")
JAVASCRIPT = (ROOT / "demo" / "network.js").read_text(encoding="utf-8")


def test_console_is_accessible_and_explicitly_synthetic() -> None:
    for value in (
        '<html lang="en">',
        'class="skip-link"',
        '<main id="case-workspace"',
        'aria-label="Patient case views"',
        'role="status"',
        'aria-live="polite"',
        "Synthetic data · no PHI",
        "Service coordination record",
        ":focus-visible",
        "@media (max-width: 700px)",
        "prefers-reduced-motion",
    ):
        assert value in HTML or value in CSS


def test_provider_case_has_linked_activation_workforce_apps_and_history() -> None:
    for value in (
        'data-view="journey"',
        'data-view="team"',
        'data-view="permissions"',
        'data-view="applications"',
        'data-view="history"',
        "Activation queue",
        "Care workforce",
        "Access decisions",
        "Application trust",
        "Case history",
        "trace:synthetic-delegation-001",
        "not a complete medical record or clinical timeline",
    ):
        assert value in HTML
    assert 'eventItem.innerHTML = "<time>10:05:00' in JAVASCRIPT
    assert "document.querySelectorAll(\"#case-history li\").length" in JAVASCRIPT
    assert "Patient-provided discharge packet uploaded" in HTML
    assert "Two purpose-minimized items routed" in JAVASCRIPT


def test_relationship_permission_and_authority_remain_separate() -> None:
    for value in (
        "Relationship, workforce eligibility, assignment, and delegation remain distinct",
        "Care-team membership is descriptive",
        "Legal authority",
        "Never inferred",
        "Patient relationship + bounded delegation",
        "relationship_assertion_only",
        'legal_authority_status: "not_established"',
        "application_decision_required",
    ):
        assert value.lower() in (HTML + JAVASCRIPT).lower()


def test_ai_is_draft_only_and_evidence_boundaries_are_visible() -> None:
    for value in (
        "AI-assisted case compilation · never an authority decision",
        "Unverified draft · cannot activate or authorize",
        'activation_permitted: false',
        'authorization_permitted: false',
        "No AI output approves, activates, widens, or grants access",
        "Acceptance, patient choice, credential review, and organization assignment stay separate",
    ):
        assert value.lower() in (HTML + JAVASCRIPT).lower()


def test_independent_apps_show_permits_and_fail_closed_denial() -> None:
    for value in (
        "One reviewed package, different worker and application decisions",
        "Kākou Scheduling",
        "Direct Care Tasks",
        "Respite Connect",
        "POLICY_REQUIREMENTS_SATISFIED",
        "ACTION_NOT_IN_VOCABULARY",
        "ACTION_NOT_DELEGATED",
        "raw_evidence_shared: false",
    ):
        assert value in HTML or value in JAVASCRIPT


def test_track2_provider_workflow_and_outcome_boundary_are_primary() -> None:
    for value in (
        "Track 2 provider workflow",
        "Provider workforce activation",
        "From a fragmented referral to an access-ready care team",
        "Care contexts",
        "Field outcomes",
        "Not yet",
        "Phase 2 measurement",
        "Provider operations",
    ):
        assert value.lower() in (HTML + JAVASCRIPT).lower()
    for value in (
        "providerProof.care_context_count",
        "providerProof.application_count",
        "providerProof.decision_count",
        "providerProof.permit_count",
        "providerProof.deny_count",
        "providerProof.field_outcome_label",
    ):
        assert value in JAVASCRIPT


def test_application_onboarding_auth_and_federation_are_inspectable() -> None:
    for value in (
        "OpenAPI requirements",
        "Human review and registration",
        "OIDC + PKCE",
        "OAuth RAR",
        "FHIR/SMART projection",
        'data-message="app-compilation"',
        'data-message="auth-flow"',
        'data-message="fhir-scheduling"',
        'data-message="federation-lab"',
        "operational federation",
    ):
        assert value in HTML or value in JAVASCRIPT


def test_patient_provided_packet_is_reviewed_and_minimum_disclosure() -> None:
    for value in (
        "Turn a discharge scan into reviewed coordination items",
        "uploaded by Leilani K.",
        "Unverified · patient-provided copy",
        "Four candidates · none clinically verified",
        "Page 1 · lines 14–16",
        "CLINICAL_SOURCE_CLARIFICATION_REQUIRED",
        "Approve 2 administrative items",
        "Share approved items, not the whole packet",
        "Direct Care Tasks",
        "Medication change remains blocked",
        'raw_document_shared: false',
        'forbidden_outputs: ["MedicationRequest", "MedicationStatement", "active CarePlan"]',
        "Planned · no live HHIE connection",
    ):
        assert value.lower() in (HTML + JAVASCRIPT).lower()
    assert "document authorship, legal authority, clinical accuracy, or currentness" in HTML


def test_revocation_retains_history_and_stops_before_patient_matching() -> None:
    for value in (
        "Revocation changes fresh decisions but never erases prior events",
        "a fresh scheduling request is denied with GRANT_REVOKED",
        "DELEGATION_REVOKED · no new items disclosed",
        "Historical receipts remain",
        "existing-session termination is claimed",
    ):
        assert value in HTML or value in JAVASCRIPT
    assert "revoked = true" in JAVASCRIPT
    assert '"post-revocation-denial": {' in JAVASCRIPT
    assert 'reason_codes: ["GRANT_REVOKED"]' in JAVASCRIPT
    assert "supporting_grant_ids: []" in JAVASCRIPT
    assert 'const grantSummary = document.querySelector("#grant-summary");' in JAVASCRIPT
    assert 'if (grantSummary) grantSummary.textContent = "Revoked · history retained";' in JAVASCRIPT


def test_every_drilldown_uses_local_retained_objects_only() -> None:
    for key in (
        "intent",
        "draft",
        "clarification",
        "invite",
        "acceptance",
        "approval",
        "relationship",
        "grant",
        "schedule-decision",
        "portal-decision",
        "care-document",
        "document-extraction",
        "document-review",
        "document-share",
        "document-denial",
        "clinical-permit",
        "revocation",
        "post-revocation-denial",
    ):
        assert f"{key}: {{" in JAVASCRIPT or f'"{key}": {{' in JAVASCRIPT
    assert "fetch(" not in JAVASCRIPT
    assert "XMLHttpRequest" not in JAVASCRIPT
