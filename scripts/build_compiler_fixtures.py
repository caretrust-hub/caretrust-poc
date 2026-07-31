"""Build deterministic, synthetic fixtures for the CareTrust compiler plane."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from caretrust.app_onboarding import ApplicationOnboardingCompiler, make_application_description
from caretrust.compiler import CompilerService, make_intent_statement
from caretrust.trace import canonical_json


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures" / "compiler"
NOW = datetime(2026, 7, 30, 10, 0, tzinfo=UTC)


class RecordedCandidateResponse:
    """Deterministic structured-output fixture; this does not call AWS."""

    provider = "recorded_contract_fixture"
    model_id = "recorded-structured-output-v1"
    started_at = NOW
    completed_at = NOW
    latency_ms = 0
    estimated_cost_usd = 0.0

    def __init__(self, parsed_json: dict[str, object]) -> None:
        self.parsed_json = parsed_json
        self.raw_text = canonical_json(parsed_json)


class RecordedCandidateModel:
    def __init__(self, component: str, candidate: dict[str, object]) -> None:
        self.component = component
        self.candidate = candidate

    def extract(self, **kwargs: object) -> RecordedCandidateResponse:
        if kwargs.get("request_metadata") != {"caretrust_component": self.component}:
            raise ValueError("recorded fixture invoked for the wrong compiler component")
        return RecordedCandidateResponse(self.candidate)


def write(name: str, value: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    (OUT / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    intent_id = "intent:compiler-fixture-001"
    intent = make_intent_statement(
        intent_id=intent_id,
        patient_ref="patient:synthetic-compiler-001",
        utterance=(
            "Let my daughter Leilani look at upcoming appointments through 2026-12-31 "
            "in the scheduling app for appointment management, but not billing."
        ),
        created_at=NOW,
    )
    intent_span = f"{intent_id}:full-text"
    intent_candidate = {
        "delegate_ref": {
            "value": "person:synthetic-leilani-caregiver",
            "citation": {"span_id": intent_span, "quote": "daughter Leilani"},
        },
        "relationship_code": {
            "value": "child",
            "citation": {"span_id": intent_span, "quote": "daughter"},
        },
        "actions": [{
            "value": "view_appointments",
            "citation": {"span_id": intent_span, "quote": "look at upcoming appointments"},
        }],
        "resources": [{
            "value": "appointments",
            "citation": {"span_id": intent_span, "quote": "look at upcoming appointments"},
        }],
        "excluded_resources": [{
            "value": "billing",
            "citation": {"span_id": intent_span, "quote": "billing"},
        }],
        "audience": {
            "value": "app:synthetic-scheduling",
            "citation": {"span_id": intent_span, "quote": "scheduling app"},
        },
        "purpose": {
            "value": "appointment_management",
            "citation": {"span_id": intent_span, "quote": "appointment management"},
        },
        "valid_until": {
            "value": "2026-12-31",
            "citation": {"span_id": intent_span, "quote": "2026-12-31"},
        },
    }
    intent_result = CompilerService(
        model=RecordedCandidateModel("intent_compiler", intent_candidate)
    ).compile_intent_with_bedrock(intent, now=NOW)
    write("intent-input.json", intent)
    write("intent-compilation.json", intent_result)

    app_source_id = "app-source:synthetic-scheduling-001"
    application = make_application_description(
        application_id="app:synthetic-scheduling",
        source_id=app_source_id,
        description=(
            "Synthetic scheduling application that creates and reschedules caregiver appointments."
        ),
        openapi={
            "openapi": "3.1.0",
            "info": {"title": "Synthetic Scheduling", "version": "1"},
            "servers": [{"url": "https://scheduling.synthetic.example"}],
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
    app_candidate = {
        "capability": {
            "value": "appointment_management",
            "citation": {
                "citation_id": f"{app_source_id}:full-text",
                "quote": "scheduling application",
            },
        },
        "action": {
            "value": "schedule_appointments",
            "citation": {
                "citation_id": f"{app_source_id}:openapi",
                "quote": "\"post\"",
            },
        },
        "data_fields": [
            {
                "value": "appointment.id",
                "citation": {
                    "citation_id": f"{app_source_id}:openapi",
                    "quote": "/appointments",
                },
            },
            {
                "value": "appointment.start",
                "citation": {
                    "citation_id": f"{app_source_id}:openapi",
                    "quote": "/appointments",
                },
            },
        ],
        "location": {
            "value": "https://scheduling.synthetic.example",
            "citation": {
                "citation_id": f"{app_source_id}:openapi",
                "quote": "https://scheduling.synthetic.example",
            },
        },
    }
    app_result = ApplicationOnboardingCompiler(
        model=RecordedCandidateModel("application_onboarding_compiler", app_candidate)
    ).compile_application_with_bedrock(application, now=NOW)
    write("application-input.json", application)
    write("application-compilation.json", app_result)


if __name__ == "__main__":
    main()
