"""Draft-only compiler for synthetic application descriptions and OpenAPI input.

The output is a proposal for human/developer review: it is not registration,
OAuth client activation, a RAR request, or a data-access decision.
"""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import re
from typing import Any, Literal

from pydantic import AwareDatetime, field_validator, model_validator

from caretrust.compiler import (
    LOCAL_REPLAY_MODEL_ID,
    CompilationRun,
    StructuredModel,
    reject_authority_assertions,
    sha256_text,
)
from caretrust.models import StrictModel
from caretrust.trace import canonical_json


APP_COMPILER_VERSION = "caretrust.application-onboarding-compiler.v1"
SPEC_NAMESPACE = "https://caretrust-hub.github.io/caretrust-spec"
_EXCESSIVE_DATA = ("all records", "full chart", "entire chart", "raw document", "all data", "everything")
_CLINICAL_AUTHORITY = ("diagnos", "prescrib", "treatment plan", "clinical decision", "change medication", "order medication")
_INJECTION = ("ignore previous", "system prompt", "developer message", "grant access", "set status")


class SourceCitation(StrictModel):
    citation_id: str | None = None
    source_id: str
    quote: str
    start_char: int
    end_char: int
    source_kind: Literal["description", "openapi"] = "description"

    @model_validator(mode="after")
    def _offsets(self) -> SourceCitation:
        if not self.source_id or not self.quote or self.start_char < 0 or self.end_char <= self.start_char:
            raise ValueError("application source citations require a non-empty exact span")
        if self.citation_id is not None and not self.citation_id:
            raise ValueError("citation_id must not be blank when supplied")
        return self


class ApplicationDescription(StrictModel):
    """Untrusted synthetic description and optional OpenAPI object supplied to the compiler."""

    schema_version: str = "caretrust.application-description.v1"
    application_id: str
    source_id: str
    description: str
    description_sha256: str
    source_citations: tuple[SourceCitation, ...]
    openapi: dict[str, Any] | None = None
    synthetic: bool = True

    @field_validator("application_id", "source_id", "description")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value:
            raise ValueError("application description strings must not be blank")
        return value

    @field_validator("description_sha256")
    @classmethod
    def _hash(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", value.lower()):
            raise ValueError("description_sha256 must be a SHA-256 hex digest")
        return value.lower()

    @model_validator(mode="after")
    def _source_bound(self) -> ApplicationDescription:
        if self.description_sha256 != sha256_text(self.description):
            raise ValueError("description_sha256 must bind the exact description")
        if not self.source_citations:
            raise ValueError("application description requires at least one source citation")
        for citation in self.source_citations:
            if citation.source_id != self.source_id:
                raise ValueError("citation source_id must match application source_id")
            cited_source = (
                self.description
                if citation.source_kind == "description"
                else canonical_json(self.openapi or {})
            )
            if citation.source_kind == "openapi" and self.openapi is None:
                raise ValueError("OpenAPI citations require an OpenAPI source")
            if citation.end_char > len(cited_source) or cited_source[citation.start_char:citation.end_char] != citation.quote:
                raise ValueError("citation quote must match exact source offsets")
        return self


class AppCandidateCitation(StrictModel):
    citation_id: str
    quote: str

    @field_validator("citation_id", "quote")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value:
            raise ValueError("application model citations require id and exact quote")
        return value


class AppCandidateValue(StrictModel):
    value: str
    citation: AppCandidateCitation

    @field_validator("value")
    @classmethod
    def _value_nonblank(cls, value: str) -> str:
        if not value:
            raise ValueError("application model candidate values must not be blank")
        return value


class AppOnboardingModelCandidate(StrictModel):
    """Strict candidate schema returned by a structured model provider."""

    capability: AppCandidateValue
    action: AppCandidateValue
    data_fields: tuple[AppCandidateValue, ...]
    location: AppCandidateValue | None = None


class ProposedRARDetail(StrictModel):
    """A proposal shaped for OAuth 2.0 Rich Authorization Requests."""

    type: str = f"{SPEC_NAMESPACE}/rar/care-data/v1"
    locations: tuple[str, ...]
    actions: tuple[str, ...]
    datatypes: tuple[str, ...]
    purpose: str
    evidence_refs: tuple[str, ...]

    @model_validator(mode="after")
    def _minimum(self) -> ProposedRARDetail:
        if not self.locations or not self.actions or not self.datatypes or not self.purpose or not self.evidence_refs:
            raise ValueError("a proposed RAR detail requires bounded location, action, data, purpose, and citations")
        return self


class MinimumDataField(StrictModel):
    field: str
    rationale: str
    evidence_refs: tuple[str, ...]

    @model_validator(mode="after")
    def _bound(self) -> MinimumDataField:
        if not self.field or not self.rationale or not self.evidence_refs:
            raise ValueError("minimum-data fields require a rationale and source citation")
        return self


class OnboardingFlag(StrictModel):
    code: str
    severity: str
    message: str
    evidence_refs: tuple[str, ...]
    blocking: bool

    @model_validator(mode="after")
    def _complete(self) -> OnboardingFlag:
        if not self.code or not self.severity or not self.message or not self.evidence_refs:
            raise ValueError("onboarding flags require code, severity, message, and evidence")
        return self


class AppClarification(StrictModel):
    clarification_id: str
    question: str
    options: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    required: bool = True

    @model_validator(mode="after")
    def _options(self) -> AppClarification:
        if not self.question or len(self.options) < 2 or not self.evidence_refs or not self.required:
            raise ValueError("application clarification must be required, cited, and have bounded options")
        return self


class ApplicationOnboardingDraft(StrictModel):
    schema_version: str = "caretrust.application-onboarding-draft.v1"
    draft_id: str
    application_id: str
    source_sha256: str
    status: str = "draft"
    proposed_profile: str
    proposed_rar: tuple[ProposedRARDetail, ...]
    minimum_data_plan: tuple[MinimumDataField, ...]
    flags: tuple[OnboardingFlag, ...]
    clarifications: tuple[AppClarification, ...]
    registration_permitted: bool = False
    authorization_permitted: bool = False
    activation_permitted: bool = False
    synthetic: bool = True

    @model_validator(mode="after")
    def _draft_only(self) -> ApplicationOnboardingDraft:
        if self.status != "draft" or self.registration_permitted or self.authorization_permitted or self.activation_permitted:
            raise ValueError("application compiler output must remain a non-authoritative draft")
        if not self.draft_id or not self.application_id or not self.proposed_profile:
            raise ValueError("application draft identifiers and profile must not be blank")
        if not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256):
            raise ValueError("source_sha256 must be a SHA-256 digest")
        if not self.proposed_rar or not self.minimum_data_plan:
            raise ValueError("application draft requires a RAR proposal and minimum-data plan")
        return self


class ApplicationCompilation(StrictModel):
    schema_version: str = "caretrust.application-compilation.v1"
    draft: ApplicationOnboardingDraft
    run: CompilationRun
    evidence_status: Literal["executed_local", "contract_tested"] = "executed_local"
    compilation_mode: Literal[
        "deterministic_fallback",
        "deterministic_fallback_after_model_rejection",
        "model_candidate_validated",
    ] = "deterministic_fallback"
    model_candidate: AppOnboardingModelCandidate | None = None
    candidate_validation_errors: tuple[str, ...] = ()
    safety_flags: tuple[str, ...] = ()
    non_claims: tuple[str, ...] = (
        "This is a proposed application profile and does not register an application or authorize access.",
    )

    @model_validator(mode="after")
    def _candidate_lineage(self) -> ApplicationCompilation:
        if self.compilation_mode == "model_candidate_validated":
            if self.model_candidate is None or self.candidate_validation_errors:
                raise ValueError("validated application compilation requires its candidate and no errors")
        elif self.model_candidate is not None:
            raise ValueError("only a validated application compilation may retain a candidate")
        if self.compilation_mode == "deterministic_fallback_after_model_rejection":
            if not self.candidate_validation_errors or "MODEL_CANDIDATE_REJECTED" not in self.safety_flags:
                raise ValueError("application model rejection fallback requires a visible error and flag")
        return self


def make_application_description(
    *, application_id: str, source_id: str, description: str, openapi: dict[str, Any] | None = None
) -> ApplicationDescription:
    """Create a complete exact-source fixture input from synthetic application text."""

    citations = [
        SourceCitation(
            citation_id=f"{source_id}:full-text",
            source_id=source_id,
            quote=description,
            start_char=0,
            end_char=len(description),
        )
    ]
    if openapi is not None:
        rendered_openapi = canonical_json(openapi)
        citations.append(
            SourceCitation(
                citation_id=f"{source_id}:openapi",
                source_id=source_id,
                quote=rendered_openapi,
                start_char=0,
                end_char=len(rendered_openapi),
                source_kind="openapi",
            )
        )
    return ApplicationDescription(
        application_id=application_id,
        source_id=source_id,
        description=description,
        description_sha256=sha256_text(description),
        source_citations=tuple(citations),
        openapi=openapi,
    )


class ApplicationOnboardingCompiler:
    """Compile untrusted app material into a minimum-data RAR/profile proposal."""

    def __init__(self, *, model: StructuredModel | None = None) -> None:
        self.model = model

    def compile_application(
        self, source: ApplicationDescription, *, now: datetime | None = None, run_id: str | None = None
    ) -> ApplicationCompilation:
        when = now or datetime.now(UTC)
        if when.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        draft = self._compile(source)
        response = draft.model_dump(mode="json")
        return ApplicationCompilation(
            draft=draft,
            compilation_mode="deterministic_fallback",
            run=CompilationRun(
                run_id=run_id or f"compiler-run:{source.application_id}:local",
                compiler_version=APP_COMPILER_VERSION,
                provider="deterministic_local",
                model_id=LOCAL_REPLAY_MODEL_ID,
                prompt_sha256=sha256_text(_app_prompt()),
                input_sha256=source.description_sha256,
                response_sha256=sha256_text(canonical_json(response)),
                started_at=when, completed_at=when, latency_ms=0, estimated_cost_usd=0.0,
            ),
        )

    def compile_application_with_bedrock(
        self, source: ApplicationDescription, *, now: datetime | None = None, run_id: str | None = None
    ) -> ApplicationCompilation:
        if self.model is None:
            raise RuntimeError("no structured model was configured")
        response = self.model.extract(
            system_prompt="Return one strict, exact-citation candidate application capability and bounded minimum-data plan from synthetic source material; never claim approval, permission, activation, authorization, registration, or revocation.",
            user_text=_combined_source(source),
            json_schema=AppOnboardingModelCandidate.model_json_schema(),
            schema_name="caretrust_application_model_candidate",
            schema_description="Non-authoritative cited capability and minimum-data candidate",
            request_metadata={"caretrust_component": "application_onboarding_compiler"},
        )
        parsed = getattr(response, "parsed_json", response)
        reject_authority_assertions(parsed)
        candidate_rejected = False
        candidate_error: str | None = None
        try:
            candidate = AppOnboardingModelCandidate.model_validate(parsed)
            draft = self._compile_candidate(source, candidate)
            when = now or datetime.now(UTC)
            if when.tzinfo is None:
                raise ValueError("now must be timezone-aware")
            compiled = ApplicationCompilation(
                draft=draft,
                evidence_status="contract_tested",
                compilation_mode="model_candidate_validated",
                model_candidate=candidate,
                run=CompilationRun(
                    run_id=run_id or f"compiler-run:{source.application_id}:candidate", compiler_version=APP_COMPILER_VERSION,
                    provider="candidate_pending_metadata", model_id="candidate-pending-metadata", prompt_sha256=sha256_text(_app_prompt()),
                    input_sha256=source.description_sha256, response_sha256=sha256_text(canonical_json(parsed)),
                    started_at=when, completed_at=when, latency_ms=0, estimated_cost_usd=None,
                ),
            )
        except (ValueError, TypeError) as exc:
            candidate_rejected = True
            candidate_error = str(exc)
            compiled = self.compile_application(source, now=now, run_id=run_id)
        return ApplicationCompilation.model_validate({
            **compiled.model_dump(mode="python"),
            "compilation_mode": "deterministic_fallback_after_model_rejection" if candidate_rejected else "model_candidate_validated",
            "evidence_status": "contract_tested",
            "safety_flags": ("MODEL_CANDIDATE_REJECTED",) if candidate_rejected else (),
            "candidate_validation_errors": (
                (candidate_error or "model candidate validation failed",)
                if candidate_rejected
                else ()
            ),
            "run": CompilationRun(
            run_id=run_id or f"compiler-run:{source.application_id}:bedrock",
            compiler_version=APP_COMPILER_VERSION,
            provider=str(getattr(response, "provider", "bedrock_optional")),
            model_id=str(getattr(response, "model_id", "bedrock-unknown")),
            prompt_sha256=sha256_text(_app_prompt()), input_sha256=source.description_sha256,
            response_sha256=sha256_text(getattr(response, "raw_text", canonical_json(parsed))),
            started_at=getattr(response, "started_at", compiled.run.started_at),
            completed_at=getattr(response, "completed_at", compiled.run.completed_at),
            latency_ms=int(getattr(response, "latency_ms", 0)), estimated_cost_usd=getattr(response, "estimated_cost_usd", None),
        )})

    def replay(self, source: ApplicationDescription, recorded: ApplicationCompilation) -> ApplicationCompilation:
        replayed = self.compile_application(source, now=recorded.run.started_at, run_id=recorded.run.run_id)
        if _meaningful_hash(replayed) != _meaningful_hash(recorded):
            raise ValueError("deterministic replay does not match the recorded application compilation")
        return replayed

    def _compile(self, source: ApplicationDescription) -> ApplicationOnboardingDraft:
        text = _combined_source(source)
        citations = tuple(item.citation_id or item.source_id for item in source.source_citations)
        flags: list[OnboardingFlag] = []
        clarifications: list[AppClarification] = []
        lowered = text.casefold()
        for phrase in _EXCESSIVE_DATA:
            if phrase in lowered:
                flags.append(OnboardingFlag(code="EXCESSIVE_DATA_REQUEST", severity="high", message="The requested data exceeds a minimum-data onboarding proposal.", evidence_refs=citations, blocking=True))
                break
        for phrase in _CLINICAL_AUTHORITY:
            if phrase in lowered:
                flags.append(OnboardingFlag(code="CLINICAL_AUTHORITY_REQUEST", severity="high", message="Clinical authority is outside this application-onboarding compiler and requires accountable review.", evidence_refs=citations, blocking=True))
                break
        if any(item in lowered for item in _INJECTION):
            flags.append(OnboardingFlag(code="PROMPT_INJECTION_ATTEMPT", severity="high", message="Untrusted source text attempted to alter compiler behavior and was ignored.", evidence_refs=citations, blocking=True))

        capability = _capability(text)
        if capability is None:
            capability = "care_coordination"
            clarifications.append(AppClarification(clarification_id=f"clarification:{source.application_id}:capability", question="Which bounded care workflow does this application support?", options=("appointment_management", "care_coordination"), evidence_refs=citations))
        purpose = "appointment_management" if capability == "appointment_management" else "care_coordination"
        location = _location(source) or f"https://{source.application_id.split(':')[-1]}.synthetic.example"
        if _location(source) is None:
            clarifications.append(AppClarification(clarification_id=f"clarification:{source.application_id}:location", question="Confirm the registered resource location for this synthetic application.", options=(location, "provide a different synthetic location"), evidence_refs=citations))

        data_fields = _minimum_fields(capability)
        action, action_needs_clarification = _rar_action(source, capability)
        if action_needs_clarification:
            clarifications.append(
                AppClarification(
                    clarification_id=f"clarification:{source.application_id}:action",
                    question="Does this application only view appointments, or may it create and update them?",
                    options=("view_appointments", "schedule_appointments"),
                    evidence_refs=citations,
                )
            )
        return ApplicationOnboardingDraft(
            draft_id=f"app-onboarding-draft:{source.application_id}:v1", application_id=source.application_id,
            source_sha256=source.description_sha256,
            proposed_profile=f"{SPEC_NAMESPACE}/profiles/{capability}/v1",
            proposed_rar=(ProposedRARDetail(locations=(location,), actions=(action,), datatypes=tuple(item[0] for item in data_fields), purpose=purpose, evidence_refs=citations),),
            minimum_data_plan=tuple(MinimumDataField(field=field, rationale=rationale, evidence_refs=citations) for field, rationale in data_fields),
            flags=tuple(flags), clarifications=tuple(clarifications),
        )

    def _compile_candidate(
        self, source: ApplicationDescription, candidate: AppOnboardingModelCandidate
    ) -> ApplicationOnboardingDraft:
        """Apply only a source-bound and minimum-data-valid model candidate."""

        citations = {item.citation_id or item.source_id: item for item in source.source_citations}

        def verify(item: AppCandidateValue, patterns: tuple[str, ...] = ()) -> str:
            source_citation = citations.get(item.citation.citation_id)
            if source_citation is None or item.citation.quote not in source_citation.quote:
                raise ValueError("application model candidate citation is not exact retained source evidence")
            if patterns and not any(pattern.casefold() in item.citation.quote.casefold() for pattern in patterns):
                raise ValueError("application model candidate is not supported by its citation")
            return item.citation.citation_id

        capability = candidate.capability.value
        if capability not in {"appointment_management", "care_coordination"}:
            raise ValueError("application model candidate proposed an unsupported capability")
        capability_ref = verify(candidate.capability, _CAPABILITY_PATTERNS[capability])
        action = candidate.action.value
        if action not in _ALLOWED_ACTIONS[capability]:
            raise ValueError("application model candidate action does not match its capability")
        action_ref = verify(candidate.action, _ACTION_PATTERNS[action])
        allowed = {field for field, _ in _minimum_fields(capability)}
        if not candidate.data_fields or len(candidate.data_fields) > len(allowed):
            raise ValueError("application model candidate must propose a bounded data plan")
        fields: list[str] = []
        field_refs: dict[str, str] = {}
        for item in candidate.data_fields:
            if item.value not in allowed:
                raise ValueError("application model candidate proposed excessive or unsupported data")
            if item.value in fields:
                raise ValueError("application model candidate data fields must be unique")
            field_refs[item.value] = verify(item, _DATA_PATTERNS[item.value])
            fields.append(item.value)
        location = _location(source)
        location_ref = capability_ref
        if candidate.location is not None:
            location_ref = verify(candidate.location, (candidate.location.value,))
            if not candidate.location.value.startswith("https://"):
                raise ValueError("application model candidate location must be an HTTPS URI")
            location = candidate.location.value
        if location is None:
            raise ValueError("application model candidate needs a bounded HTTPS location")
        text = _combined_source(source)
        flags = _source_flags(text, tuple(citations))
        purpose = "appointment_management" if capability == "appointment_management" else "care_coordination"
        rationale = dict(_minimum_fields(capability))
        return ApplicationOnboardingDraft(
            draft_id=f"app-onboarding-draft:{source.application_id}:v1", application_id=source.application_id,
            source_sha256=source.description_sha256,
            proposed_profile=f"{SPEC_NAMESPACE}/profiles/{capability}/v1",
            proposed_rar=(ProposedRARDetail(
                locations=(location,),
                actions=(action,),
                datatypes=tuple(fields),
                purpose=purpose,
                evidence_refs=tuple(dict.fromkeys(
                    (capability_ref, action_ref, location_ref, *(field_refs[field] for field in fields))
                )),
            ),),
            minimum_data_plan=tuple(MinimumDataField(field=field, rationale=rationale[field], evidence_refs=(field_refs[field],)) for field in fields),
            flags=tuple(flags), clarifications=(),
        )


def _combined_source(source: ApplicationDescription) -> str:
    return source.description + "\n" + canonical_json(source.openapi or {})


def _location(source: ApplicationDescription) -> str | None:
    candidates = re.findall(r"https://[^\s\"']+", _combined_source(source))
    return candidates[0].rstrip(".,)") if candidates else None


def _capability(text: str) -> str | None:
    lowered = text.casefold()
    if "appointment" in lowered or "schedul" in lowered:
        return "appointment_management"
    if "care coordination" in lowered or "care team" in lowered:
        return "care_coordination"
    return None


def _minimum_fields(capability: str) -> tuple[tuple[str, str], ...]:
    if capability == "appointment_management":
        return (("appointment.id", "Identifies the appointment to display."), ("appointment.start", "Shows the scheduled time."), ("appointment.location", "Shows where the visit occurs."), ("appointment.status", "Shows cancellation or completion state."))
    return (("care_team.member", "Identifies the care-team contact."), ("care_team.role", "Explains the contact's role."), ("message.thread_id", "Keeps communications within one thread."))


def _rar_action(
    source: ApplicationDescription, capability: str
) -> tuple[str, bool]:
    """Return the least-privilege source-supported action and ambiguity flag."""

    if capability == "care_coordination":
        return "message_care_team", False

    methods = {
        method.casefold()
        for path_item in (source.openapi or {}).get("paths", {}).values()
        if isinstance(path_item, dict)
        for method in path_item
        if method.casefold() in {"get", "post", "put", "patch", "delete"}
    }
    if methods & {"post", "put", "patch", "delete"}:
        return "schedule_appointments", False
    if methods and methods <= {"get"}:
        return "view_appointments", False

    lowered = source.description.casefold()
    if any(
        marker in lowered
        for marker in (
            "create appointment",
            "book appointment",
            "manage appointment",
            "reschedule",
            "cancel appointment",
            "schedule appointment",
        )
    ):
        return "schedule_appointments", False
    if any(marker in lowered for marker in ("read appointment", "reads appointment", "view appointment", "list appointment", "look at appointment")):
        return "view_appointments", False
    return "view_appointments", True


def _source_flags(text: str, citations: tuple[str, ...]) -> list[OnboardingFlag]:
    lowered = text.casefold()
    flags: list[OnboardingFlag] = []
    if any(phrase in lowered for phrase in _EXCESSIVE_DATA):
        flags.append(OnboardingFlag(code="EXCESSIVE_DATA_REQUEST", severity="high", message="The requested data exceeds a minimum-data onboarding proposal.", evidence_refs=citations, blocking=True))
    if any(phrase in lowered for phrase in _CLINICAL_AUTHORITY):
        flags.append(OnboardingFlag(code="CLINICAL_AUTHORITY_REQUEST", severity="high", message="Clinical authority is outside this application-onboarding compiler and requires accountable review.", evidence_refs=citations, blocking=True))
    if any(phrase in lowered for phrase in _INJECTION):
        flags.append(OnboardingFlag(code="PROMPT_INJECTION_ATTEMPT", severity="high", message="Untrusted source text attempted to alter compiler behavior and was ignored.", evidence_refs=citations, blocking=True))
    return flags


def _app_prompt() -> str:
    return "Propose only draft application authorization profiles and minimum-data plans from synthetic source material. Never create authority."


def _meaningful_hash(compilation: ApplicationCompilation) -> str:
    return sha256_text(canonical_json(compilation.draft))


_CAPABILITY_PATTERNS = {
    "appointment_management": ("appointment", "schedul"),
    "care_coordination": ("care coordination", "care team"),
}
_ALLOWED_ACTIONS = {
    "appointment_management": {"view_appointments", "schedule_appointments"},
    "care_coordination": {"message_care_team"},
}
_ACTION_PATTERNS = {
    "view_appointments": ("read appointment", "reads appointment", "view appointment", "listappointment", "list appointment", "look at appointment", "\"get\""),
    "schedule_appointments": ("create appointment", "book appointment", "manage appointment", "reschedul", "cancel appointment", "schedule appointment", "\"post\"", "\"put\"", "\"patch\""),
    "message_care_team": ("message", "care coordination", "care team"),
}
_DATA_PATTERNS = {
    "appointment.id": ("appointment",),
    "appointment.start": ("appointment", "date", "time"),
    "appointment.location": ("appointment", "location"),
    "appointment.status": ("appointment", "status"),
    "care_team.member": ("care team",),
    "care_team.role": ("care team",),
    "message.thread_id": ("message", "care team"),
}
