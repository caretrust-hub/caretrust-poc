"""Static product, truthfulness, and accessibility contracts for v0.5."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "demo" / "network.html").read_text(encoding="utf-8")
CSS = (ROOT / "demo" / "network.css").read_text(encoding="utf-8")
JAVASCRIPT = (ROOT / "demo" / "network.js").read_text(encoding="utf-8")
REFERENCE_HTML = (ROOT / "demo" / "reference-client.html").read_text(
    encoding="utf-8"
)
REFERENCE_CSS = (ROOT / "demo" / "reference-client.css").read_text(
    encoding="utf-8"
)
REFERENCE_JAVASCRIPT = (ROOT / "demo" / "reference-client.js").read_text(
    encoding="utf-8"
)
BRIEF = (
    ROOT / "prompts" / "claude-code-caretrust-org-console-brief.md"
).read_text(encoding="utf-8")


def test_console_is_accessible_and_explicitly_synthetic() -> None:
    for value in (
        '<html lang="en">',
        'class="skip-link"',
        '<main id="case-workspace"',
        'aria-label="Patient case views"',
        'role="status"',
        'aria-live="polite"',
        "Synthetic data · no PHI",
        ":focus-visible",
        "@media (max-width: 700px)",
        "prefers-reduced-motion",
    ):
        assert value in HTML or value in CSS
    assert HTML.count("<h1") == 1


def test_primary_story_is_provider_workforce_activation() -> None:
    for value in (
        "Turn a fragmented referral into a consented, qualified-worker assignment",
        "Organization work queue",
        "Compile the referral",
        "Coordinator review",
        "Patient scope",
        "Qualified worker",
        "Independent apps",
        "Care team and authority",
        "Case history",
    ):
        assert value.lower() in (HTML + JAVASCRIPT).lower()


def test_workload_reduction_is_explicit_and_bounded() -> None:
    for value in (
        "Workload avoided in this prototype run",
        "Fields prefilled",
        "Exceptions to review",
        "Follow-ups open",
        "App entries generated",
        "Human approvals left",
        "measured prototype interactions",
        "not validated staff time savings or field outcomes",
        "duplicate_app_entries_avoided",
    ):
        assert value.lower() in (HTML + JAVASCRIPT + BRIEF).lower()


def test_console_uses_stateful_api_with_public_reference_fallback() -> None:
    for value in (
        'const API_ROOT = "./api/v1"',
        'fetch(`${API_ROOT}/health`',
        "class ApiBackend",
        "class BrowserReferenceBackend",
        "expected_version: session.version",
        "Python API · local",
        "Browser reference adapter",
        "caretrust.provider-session.v1",
    ):
        assert value in JAVASCRIPT or value in HTML


def test_ai_proposes_cited_drafts_but_cannot_create_authority() -> None:
    for value in (
        "AI-assisted intake",
        "Every result remains a draft",
        "No consent, credential, clinical, or access decision",
        "exact_quote",
        "authority_effect: \"none\"",
        "AI explanation did not control eligibility or assignment",
        "model output",
        "non-authoritative",
    ):
        assert value.lower() in (HTML + JAVASCRIPT + BRIEF).lower()


def test_patient_approval_and_worker_assignment_are_separate() -> None:
    for value in (
        "Separate patient-facing gate",
        "Approve this scope",
        "patient_approval",
        "assign_worker",
        "failed deterministic eligibility checks",
        "two ineligible workers cannot be assigned",
    ):
        assert value.lower() in (HTML + JAVASCRIPT + BRIEF).lower()


def test_apps_receive_disjoint_projections_and_revocation_denies() -> None:
    for value in (
        "OpenShift Scheduler",
        "Care Tasks Mobile",
        "first_visit_task",
        "start_date",
        "source document",
        "request_app_access",
        "revoke_assignment",
        "Fresh request denied: the assignment is revoked",
        "disclose zero case fields",
    ):
        assert value.lower() in (JAVASCRIPT + BRIEF).lower()


def test_standards_are_secondary_but_inspectable() -> None:
    for value in (
        "Standards &amp; decision evidence",
        "OAuth 2.0 + RAR",
        "FHIR R4 projections",
        "OIDC, VC &amp; federation",
        "CareTrust Core 0.1",
        "OpenID Federation 1.0",
        "experimental profile",
    ):
        assert value.lower() in (HTML + BRIEF).lower()


def test_reference_client_is_a_minimum_data_consumer() -> None:
    for value in (
        "TEST / DEMO ONLY",
        "independent reference consumer",
        "CareTrust is the trust layer—not the caregiver app",
        "authorization_details",
        "caretrust_case_access",
        "first_visit_task",
        "No task disclosed",
        "disclosed_fields=0",
    ):
        assert value.lower() in (
            REFERENCE_HTML + REFERENCE_JAVASCRIPT
        ).lower()
    assert ":focus-visible" in REFERENCE_CSS
    assert "prefers-reduced-motion" in REFERENCE_CSS


def test_design_handoff_contains_executable_acceptance_criteria() -> None:
    for value in (
        "Primary outcome",
        "Why an organization adopts this",
        "Workflow interaction specification",
        "Executable synthetic case",
        "Technical architecture",
        "Open standards workflow",
        "AI prominence and safety",
        "Acceptance criteria",
        "12 generated app entries",
    ):
        assert value in BRIEF
