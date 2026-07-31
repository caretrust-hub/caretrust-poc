"""Contract tests for the draft-only application onboarding compiler."""

from __future__ import annotations

from datetime import UTC, datetime

from caretrust.app_onboarding import ApplicationOnboardingCompiler, make_application_description


NOW = datetime(2026, 7, 30, 10, 0, tzinfo=UTC)


def test_proposes_rar_profile_and_minimum_data_plan() -> None:
    source = make_application_description(
        application_id="app:synthetic-calendar",
        source_id="source:calendar",
        description="Synthetic scheduling application at https://calendar.synthetic.example reads appointments for care coordination.",
    )
    compiler = ApplicationOnboardingCompiler()
    result = compiler.compile_application(source, now=NOW)

    assert result.draft.status == "draft"
    assert result.draft.registration_permitted is False
    assert result.draft.proposed_profile == (
        "https://caretrust-hub.github.io/caretrust-spec/profiles/appointment_management/v1"
    )
    assert result.draft.proposed_rar[0].type == (
        "https://caretrust-hub.github.io/caretrust-spec/rar/care-data/v1"
    )
    assert result.draft.proposed_rar[0].datatypes == (
        "appointment.id", "appointment.start", "appointment.location", "appointment.status"
    )
    assert result.draft.proposed_rar[0].actions == ("view_appointments",)
    assert compiler.replay(source, result).draft == result.draft


def test_flags_excessive_data_and_clinical_authority() -> None:
    source = make_application_description(
        application_id="app:unsafe",
        source_id="source:unsafe",
        description="This synthetic app wants all records and will change medication under a treatment plan.",
    )
    result = ApplicationOnboardingCompiler().compile_application(source, now=NOW)
    assert {item.code for item in result.draft.flags} == {
        "EXCESSIVE_DATA_REQUEST", "CLINICAL_AUTHORITY_REQUEST"
    }
    assert all(item.blocking for item in result.draft.flags)


class _CandidateResponse:
    model_id = "fake-bedrock"
    raw_text = "candidate"
    started_at = NOW
    completed_at = NOW
    latency_ms = 4
    estimated_cost_usd = 0.00001
    parsed_json = {
        "capability": {"value": "appointment_management", "citation": {"citation_id": "source:calendar:full-text", "quote": "scheduling application"}},
        "action": {"value": "view_appointments", "citation": {"citation_id": "source:calendar:full-text", "quote": "reads appointments"}},
        "data_fields": [
            {"value": "appointment.id", "citation": {"citation_id": "source:calendar:full-text", "quote": "appointments"}},
            {"value": "appointment.start", "citation": {"citation_id": "source:calendar:full-text", "quote": "appointments"}},
        ],
        "location": {"value": "https://calendar.synthetic.example", "citation": {"citation_id": "source:calendar:full-text", "quote": "https://calendar.synthetic.example"}},
    }


class _CandidateModel:
    def extract(self, **kwargs: object) -> _CandidateResponse:
        assert kwargs["request_metadata"] == {"caretrust_component": "application_onboarding_compiler"}
        return _CandidateResponse()


def test_model_candidate_materially_selects_bounded_data_plan() -> None:
    source = make_application_description(
        application_id="app:synthetic-calendar", source_id="source:calendar",
        description="Synthetic scheduling application at https://calendar.synthetic.example reads appointments for care coordination.",
    )
    result = ApplicationOnboardingCompiler(model=_CandidateModel()).compile_application_with_bedrock(source, now=NOW)
    assert result.compilation_mode == "model_candidate_validated"
    assert result.draft.proposed_rar[0].datatypes == ("appointment.id", "appointment.start")
    assert result.evidence_status == "contract_tested"
    assert result.model_candidate is not None


class _OpenApiCandidateResponse(_CandidateResponse):
    parsed_json = {
        **_CandidateResponse.parsed_json,
        "capability": {
            "value": "appointment_management",
            "citation": {
                "citation_id": "source:openapi:full-text",
                "quote": "scheduling application",
            },
        },
        "data_fields": [
            {
                "value": "appointment.id",
                "citation": {
                    "citation_id": "source:openapi:openapi",
                    "quote": "/appointments",
                },
            },
            {
                "value": "appointment.start",
                "citation": {
                    "citation_id": "source:openapi:openapi",
                    "quote": "/appointments",
                },
            },
        ],
        "action": {
            "value": "view_appointments",
            "citation": {
                "citation_id": "source:openapi:openapi",
                "quote": "\"get\"",
            },
        },
        "location": {
            "value": "https://api.synthetic.example",
            "citation": {
                "citation_id": "source:openapi:openapi",
                "quote": "https://api.synthetic.example",
            },
        },
    }


class _OpenApiCandidateModel:
    def extract(self, **kwargs: object) -> _OpenApiCandidateResponse:
        assert "/appointments" in str(kwargs["user_text"])
        return _OpenApiCandidateResponse()


def test_model_candidate_can_ground_location_and_fields_in_openapi() -> None:
    source = make_application_description(
        application_id="app:synthetic-openapi",
        source_id="source:openapi",
        description="Synthetic scheduling application for caregiver appointment coordination.",
        openapi={
            "openapi": "3.1.0",
            "servers": [{"url": "https://api.synthetic.example"}],
            "paths": {"/appointments": {"get": {"operationId": "listAppointments"}}},
        },
    )
    result = ApplicationOnboardingCompiler(
        model=_OpenApiCandidateModel()
    ).compile_application_with_bedrock(source, now=NOW)

    assert result.compilation_mode == "model_candidate_validated"
    assert result.draft.proposed_rar[0].locations == ("https://api.synthetic.example",)
    assert result.draft.proposed_rar[0].actions == ("view_appointments",)
    assert result.draft.minimum_data_plan[0].evidence_refs == ("source:openapi:openapi",)


def test_mutating_openapi_proposes_schedule_without_delete_scope() -> None:
    source = make_application_description(
        application_id="app:synthetic-scheduler",
        source_id="source:scheduler",
        description="Synthetic appointment application.",
        openapi={
            "openapi": "3.1.0",
            "servers": [{"url": "https://scheduler.synthetic.example"}],
            "paths": {
                "/appointments": {
                    "get": {"operationId": "listAppointments"},
                    "post": {"operationId": "createAppointment"},
                },
                "/appointments/{id}": {
                    "patch": {"operationId": "rescheduleAppointment"}
                },
            },
        },
    )

    draft = ApplicationOnboardingCompiler().compile_application(source, now=NOW).draft
    assert draft.proposed_rar[0].actions == ("schedule_appointments",)
    assert "delete" not in draft.proposed_rar[0].actions


def test_model_candidate_cannot_clear_broad_or_clinical_source_flags() -> None:
    source = make_application_description(
        application_id="app:synthetic-calendar", source_id="source:calendar",
        description="Synthetic scheduling application at https://calendar.synthetic.example reads appointments, wants all records, and will change medication.",
    )
    result = ApplicationOnboardingCompiler(model=_CandidateModel()).compile_application_with_bedrock(source, now=NOW)
    assert result.compilation_mode == "model_candidate_validated"
    assert {flag.code for flag in result.draft.flags} == {"EXCESSIVE_DATA_REQUEST", "CLINICAL_AUTHORITY_REQUEST"}


class _InvalidAppCandidateModel:
    def extract(self, **kwargs: object) -> _CandidateResponse:
        response = _CandidateResponse()
        response.parsed_json = {
            **_CandidateResponse.parsed_json,
            "data_fields": [{"value": "raw_document", "citation": {"citation_id": "source:calendar:full-text", "quote": "appointments"}}],
        }
        return response


def test_hallucinated_app_data_candidate_is_rejected_to_labeled_fallback() -> None:
    source = make_application_description(
        application_id="app:synthetic-calendar", source_id="source:calendar",
        description="Synthetic scheduling application at https://calendar.synthetic.example reads appointments for care coordination.",
    )
    result = ApplicationOnboardingCompiler(model=_InvalidAppCandidateModel()).compile_application_with_bedrock(source, now=NOW)
    assert result.compilation_mode == "deterministic_fallback_after_model_rejection"
    assert result.safety_flags == ("MODEL_CANDIDATE_REJECTED",)
