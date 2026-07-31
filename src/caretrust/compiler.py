"""Provider-neutral, draft-only compiler for patient delegation intent.

This is deliberately a compilation boundary, not an authorization boundary.  It
turns synthetic natural-language intent into the existing ``DelegationDraft``
contract, preserves exact source-span citations, and records enough immutable
metadata to replay a result without contacting a model provider.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from hashlib import sha256
import re
from typing import Any, Literal, Mapping, Protocol

from pydantic import AwareDatetime, field_validator, model_validator

from caretrust.delegation import (
    ClarificationCode,
    ClarificationRequest,
    DelegationAction,
    DelegationAudience,
    DelegationBlockingCode,
    DelegationDraft,
    DelegationPurpose,
    DelegationResource,
    DelegationUncertainty,
    DelegationUncertaintyCode,
    DraftEvidenceBinding,
    DraftEvidenceField,
    IntentSpan,
    IntentStatement,
    RelationshipCode,
)
from caretrust.models import StrictModel
from caretrust.trace import canonical_json


COMPILER_VERSION = "caretrust.intent-compiler.v1"
LOCAL_REPLAY_MODEL_ID = "caretrust-deterministic-replay-v1"
_FORBIDDEN_ASSERTIONS = re.compile(
    r"\b(?:approval|approved?|permits?|activation|activated?|revocation|revoked?|authori[sz](?:e|ed|ation))\b",
    re.IGNORECASE,
)
_INJECTION_PATTERNS = (
    "ignore previous",
    "ignore prior",
    "system prompt",
    "developer message",
    "set status",
    "grant access",
)


class CompilerSafetyError(ValueError):
    """Raised when untrusted model output tries to assert authority."""


class StructuredModel(Protocol):
    """The small provider-neutral seam used by the optional Bedrock path."""

    def extract(self, **kwargs: Any) -> Any: ...


class CompilationRun(StrictModel):
    """Hash-bound record of one compilation attempt, never an authority record."""

    schema_version: str = "caretrust.compiler-run.v1"
    run_id: str
    compiler_version: str
    provider: str
    model_id: str
    prompt_sha256: str
    input_sha256: str
    response_sha256: str
    started_at: AwareDatetime
    completed_at: AwareDatetime
    latency_ms: int
    estimated_cost_usd: float | None
    draft_only: bool = True
    authority_actions_available: bool = False

    @field_validator(
        "run_id", "compiler_version", "provider", "model_id"
    )
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value:
            raise ValueError("compiler run strings must not be blank")
        return value

    @field_validator("prompt_sha256", "input_sha256", "response_sha256")
    @classmethod
    def _hash(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", value.lower()):
            raise ValueError("compiler hashes must be SHA-256 hex digests")
        return value.lower()

    @model_validator(mode="after")
    def _draft_only(self) -> CompilationRun:
        if not self.draft_only or self.authority_actions_available:
            raise ValueError("compiler runs must remain draft-only with no authority actions")
        if self.completed_at < self.started_at or self.latency_ms < 0:
            raise ValueError("compiler run timing is invalid")
        return self


class CandidateCitation(StrictModel):
    """A model-proposed source reference that must match retained input exactly."""

    span_id: str
    quote: str

    @field_validator("span_id", "quote")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value:
            raise ValueError("candidate citations require a span and exact quote")
        return value


class CandidateValue(StrictModel):
    value: str
    citation: CandidateCitation

    @field_validator("value")
    @classmethod
    def _value_nonblank(cls, value: str) -> str:
        if not value:
            raise ValueError("candidate values must not be blank")
        return value


class IntentModelCandidate(StrictModel):
    """Strict, non-authoritative candidate schema accepted from a model provider.

    Values intentionally remain strings here.  They are converted to bounded
    vocabulary only after source/citation validation by ``CompilerService``.
    """

    delegate_ref: CandidateValue | None = None
    relationship_code: CandidateValue | None = None
    actions: tuple[CandidateValue, ...] = ()
    resources: tuple[CandidateValue, ...] = ()
    excluded_resources: tuple[CandidateValue, ...] = ()
    audience: CandidateValue | None = None
    purpose: CandidateValue | None = None
    valid_until: CandidateValue | None = None


class IntentCompilation(StrictModel):
    """A draft plus required questions and its hash-bound compiler run."""

    schema_version: str = "caretrust.intent-compilation.v1"
    draft: DelegationDraft
    clarifications: tuple[ClarificationRequest, ...]
    run: CompilationRun
    safety_flags: tuple[str, ...] = ()
    evidence_status: Literal["executed_local", "contract_tested"] = "executed_local"
    compilation_mode: Literal[
        "deterministic_fallback",
        "deterministic_fallback_after_model_rejection",
        "model_candidate_validated",
    ] = "deterministic_fallback"
    model_candidate: IntentModelCandidate | None = None
    candidate_validation_errors: tuple[str, ...] = ()
    non_claims: tuple[str, ...] = (
        "This compilation is an unverified draft and cannot create authority.",
    )

    @model_validator(mode="after")
    def _binds_draft(self) -> IntentCompilation:
        if self.draft.status != "draft" or self.draft.activation_permitted:
            raise ValueError("compiled output must be a non-activatable draft")
        if any(item.draft_id != self.draft.draft_id for item in self.clarifications):
            raise ValueError("clarifications must belong to the compiled draft")
        if self.compilation_mode == "model_candidate_validated":
            if self.model_candidate is None or self.candidate_validation_errors:
                raise ValueError("validated model compilation requires its candidate and no errors")
        elif self.model_candidate is not None:
            raise ValueError("only a validated model compilation may retain a candidate")
        if self.compilation_mode == "deterministic_fallback_after_model_rejection":
            if not self.candidate_validation_errors or "MODEL_CANDIDATE_REJECTED" not in self.safety_flags:
                raise ValueError("model rejection fallback requires a visible error and safety flag")
        return self


def sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def make_intent_statement(
    *,
    intent_id: str,
    patient_ref: str,
    utterance: str,
    created_at: datetime,
    synthetic: bool = True,
) -> IntentStatement:
    """Create a fully cited intent input for deterministic local fixtures.

    One full-utterance span is intentionally retained: it lets the compiler cite
    exact words even where an external intake has not pre-segmented spans.
    """

    if not utterance:
        raise ValueError("utterance must not be blank")
    return IntentStatement(
        schema_version="caretrust.intent-statement.v1",
        intent_id=intent_id,
        patient_ref=patient_ref,
        utterance=utterance,
        utterance_sha256=sha256_text(utterance),
        spans=(
            IntentSpan(
                span_id=f"{intent_id}:full-text",
                intent_id=intent_id,
                quote=utterance,
                start_char=0,
                end_char=len(utterance),
            ),
        ),
        created_at=created_at,
        synthetic=synthetic,
    )


def reject_authority_assertions(value: object) -> None:
    """Reject provider output that says it approved or changed authority.

    The check intentionally runs over output only; patients may use these words
    in untrusted input and that input must be surfaced as a safety flag, not
    treated as an instruction.
    """

    rendered = value if isinstance(value, str) else canonical_json(value)
    match = _FORBIDDEN_ASSERTIONS.search(rendered)
    if match:
        raise CompilerSafetyError(
            f"model output asserts forbidden authority term: {match.group(0)!r}"
        )


class CompilerService:
    """Deterministic intent compiler with an optional structured-model seam."""

    def __init__(
        self,
        *,
        delegate_directory: Mapping[str, str] | None = None,
        model: StructuredModel | None = None,
    ) -> None:
        self.delegate_directory = {
            "leilani": "person:synthetic-leilani-caregiver",
            **{key.casefold(): value for key, value in (delegate_directory or {}).items()},
        }
        self.model = model

    def compile_intent(
        self,
        intent: IntentStatement,
        *,
        now: datetime | None = None,
        run_id: str | None = None,
    ) -> IntentCompilation:
        """Compile by fixed rules, with exact source citations and no side effects."""

        when = now or datetime.now(UTC)
        if when.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        prompt = _intent_prompt()
        safety_flags = _input_safety_flags(intent.utterance)
        draft, clarifications = self._compile(
            intent,
            when,
            "PROMPT_INJECTION_ATTEMPT" in safety_flags,
        )
        response = {
            "draft": draft.model_dump(mode="json"),
            "clarifications": [item.model_dump(mode="json") for item in clarifications],
            "safety_flags": safety_flags,
        }
        return IntentCompilation(
            draft=draft,
            clarifications=tuple(clarifications),
            safety_flags=tuple(safety_flags),
            compilation_mode="deterministic_fallback",
            run=CompilationRun(
                run_id=run_id or f"compiler-run:{intent.intent_id}:local",
                compiler_version=COMPILER_VERSION,
                provider="deterministic_local",
                model_id=LOCAL_REPLAY_MODEL_ID,
                prompt_sha256=sha256_text(prompt),
                input_sha256=intent.utterance_sha256,
                response_sha256=sha256_text(canonical_json(response)),
                started_at=when,
                completed_at=when,
                latency_ms=0,
                estimated_cost_usd=0.0,
            ),
        )

    def compile_intent_with_bedrock(
        self,
        intent: IntentStatement,
        *,
        now: datetime | None = None,
        run_id: str | None = None,
    ) -> IntentCompilation:
        """Exercise an optional Bedrock-style structured-output seam.

        The provider proposes bounded draft fields with exact evidence citations.
        Deterministic validation controls vocabulary, identity, scope compatibility,
        dates, and citation grounding before candidate values can enter a draft.
        The resulting object remains non-authoritative and cannot be activated.
        """

        if self.model is None:
            raise RuntimeError("no structured model was configured")
        response = self.model.extract(
            system_prompt=(
                "Return one strict, evidence-cited candidate for a synthetic delegation draft. "
                "Every value needs an exact retained span_id and quote. Do not state approval, "
                "permission, activation, authorization, revocation, or status changes."
            ),
            user_text=intent.utterance,
            json_schema=IntentModelCandidate.model_json_schema(),
            schema_name="caretrust_intent_model_candidate",
            schema_description="Non-authoritative, exact-citation candidate over synthetic intent only",
            request_metadata={"caretrust_component": "intent_compiler"},
        )
        parsed = getattr(response, "parsed_json", response)
        reject_authority_assertions(parsed)
        candidate_rejected = False
        candidate_error: str | None = None
        try:
            candidate = IntentModelCandidate.model_validate(parsed)
            when = now or datetime.now(UTC)
            if when.tzinfo is None:
                raise ValueError("now must be timezone-aware")
            draft, clarifications = self._compile_candidate(
                intent,
                when,
                candidate,
                "PROMPT_INJECTION_ATTEMPT"
                in _input_safety_flags(intent.utterance),
            )
            compiled = IntentCompilation(
                draft=draft,
                clarifications=tuple(clarifications),
                safety_flags=tuple(_input_safety_flags(intent.utterance)),
                evidence_status="contract_tested",
                compilation_mode="model_candidate_validated",
                model_candidate=candidate,
                run=CompilationRun(
                    run_id=run_id or f"compiler-run:{intent.intent_id}:candidate",
                    compiler_version=COMPILER_VERSION, provider="candidate_pending_metadata",
                    model_id="candidate-pending-metadata", prompt_sha256=sha256_text(_intent_prompt()),
                    input_sha256=intent.utterance_sha256, response_sha256=sha256_text(canonical_json(parsed)),
                    started_at=when, completed_at=when, latency_ms=0, estimated_cost_usd=None,
                ),
            )
        except (ValueError, TypeError) as exc:
            candidate_rejected = True
            candidate_error = str(exc)
            compiled = self.compile_intent(intent, now=now, run_id=run_id)
        started = getattr(response, "started_at", compiled.run.started_at)
        completed = getattr(response, "completed_at", compiled.run.completed_at)
        raw_text = getattr(response, "raw_text", canonical_json(parsed))
        flags = list(compiled.safety_flags)
        if candidate_rejected:
            flags.append("MODEL_CANDIDATE_REJECTED")
        return IntentCompilation.model_validate(
            {
                **compiled.model_dump(mode="python"),
                "safety_flags": tuple(_unique(flags)),
                "compilation_mode": (
                    "deterministic_fallback_after_model_rejection"
                    if candidate_rejected else "model_candidate_validated"
                ),
                "evidence_status": "contract_tested",
                "candidate_validation_errors": (
                    (candidate_error or "model candidate validation failed",)
                    if candidate_rejected
                    else ()
                ),
                "run": CompilationRun(
                    run_id=run_id or f"compiler-run:{intent.intent_id}:bedrock",
                    compiler_version=COMPILER_VERSION,
                    provider=str(getattr(response, "provider", "bedrock_optional")),
                    model_id=str(getattr(response, "model_id", "bedrock-unknown")),
                    prompt_sha256=sha256_text(_intent_prompt()),
                    input_sha256=intent.utterance_sha256,
                    response_sha256=sha256_text(raw_text),
                    started_at=started,
                    completed_at=completed,
                    latency_ms=int(getattr(response, "latency_ms", 0)),
                    estimated_cost_usd=getattr(response, "estimated_cost_usd", None),
                ),
            }
        )

    def replay(self, intent: IntentStatement, recorded: IntentCompilation) -> IntentCompilation:
        """Recompile locally and require the meaningful output hash to match."""

        replayed = self.compile_intent(
            intent,
            now=recorded.run.started_at,
            run_id=recorded.run.run_id,
        )
        expected = _meaningful_hash(recorded)
        actual = _meaningful_hash(replayed)
        if expected != actual:
            raise ValueError("deterministic replay does not match the recorded compilation")
        return replayed

    def _compile(
        self, intent: IntentStatement, when: datetime, injected: bool
    ) -> tuple[DelegationDraft, list[ClarificationRequest]]:
        text = intent.utterance
        bindings: list[DraftEvidenceBinding] = []
        uncertainties: list[DelegationUncertainty] = []
        blocking: list[DelegationBlockingCode] = []
        questions: list[ClarificationRequest] = []

        def cite(phrase: str) -> tuple[str, ...] | None:
            phrase_l = phrase.casefold()
            candidates = [
                span for span in intent.spans if phrase_l in span.quote.casefold()
            ]
            if not candidates:
                return None
            # Prefer the narrowest supplied span, preserving an exact phrase
            # rather than citing a larger catch-all intake segment.
            return (min(candidates, key=lambda span: len(span.quote)).span_id,)

        def bind(field: DraftEvidenceField, value: str, phrase: str) -> bool:
            refs = cite(phrase)
            if refs is None:
                return False
            bindings.append(DraftEvidenceBinding(field_path=field, value=value, evidence_refs=refs))
            return True

        delegate_ref, relationship, delegate_phrase = self._delegate(text)
        if delegate_ref and delegate_phrase and bind(DraftEvidenceField.DELEGATE_REF, delegate_ref, delegate_phrase):
            if relationship is not None:
                bind(DraftEvidenceField.RELATIONSHIP_CODE, relationship.value, delegate_phrase)
        else:
            blocking.append(DelegationBlockingCode.MISSING_DELEGATE)
            self._uncertain(
                uncertainties, DelegationUncertaintyCode.AMBIGUOUS_DELEGATE,
                "delegate_ref", "The delegate is not mapped to a bounded synthetic identity.", intent,
            )
            questions.append(_question(intent, "delegate", ClarificationCode.IDENTIFY_DELEGATE, ("person:synthetic-leilani-caregiver", "choose another synthetic caregiver"), when))

        if delegate_ref and relationship is None:
            self._uncertain(uncertainties, DelegationUncertaintyCode.AMBIGUOUS_RELATIONSHIP, "relationship_code", "The relationship is not stated.", intent)
            questions.append(_question(intent, "relationship", ClarificationCode.CONFIRM_RELATIONSHIP, tuple(item.value for item in RelationshipCode if item is not RelationshipCode.UNSPECIFIED), when))

        actions: list[DelegationAction] = []
        resources: list[DelegationResource] = []
        for phrase, action, resource in _ACTION_RULES:
            if phrase.casefold() in text.casefold() and bind(DraftEvidenceField.ALLOWED_ACTIONS, action.value, phrase):
                actions.append(action)
                bind(DraftEvidenceField.ALLOWED_RESOURCES, resource.value, phrase)
                resources.append(resource)
        actions, resources = _unique(actions), _unique(resources)
        if not actions:
            self._uncertain(uncertainties, DelegationUncertaintyCode.AMBIGUOUS_ACTION, "allowed_actions", "No bounded caregiver action can be identified safely.", intent)
            questions.append(_question(intent, "action", ClarificationCode.CHOOSE_ACTION, tuple(item.value for item in DelegationAction), when))

        excluded: list[DelegationResource] = []
        for phrase, resource in _EXCLUSION_RULES:
            if phrase.casefold() in text.casefold() and bind(DraftEvidenceField.EXCLUDED_RESOURCES, resource.value, phrase):
                excluded.append(resource)
        excluded = _unique(excluded)

        audience: DelegationAudience | None = None
        for phrase, candidate in _AUDIENCE_RULES:
            if phrase.casefold() in text.casefold() and bind(DraftEvidenceField.ALLOWED_AUDIENCES, candidate.value, phrase):
                audience = candidate
                break
        if audience is None:
            blocking.append(DelegationBlockingCode.UNKNOWN_AUDIENCE)
            self._uncertain(uncertainties, DelegationUncertaintyCode.AMBIGUOUS_AUDIENCE, "allowed_audiences", "The application audience is not stated.", intent)
            questions.append(_question(intent, "audience", ClarificationCode.CHOOSE_AUDIENCE, tuple(item.value for item in DelegationAudience), when))

        purpose: DelegationPurpose | None = None
        for phrase, candidate in _PURPOSE_RULES:
            if phrase.casefold() in text.casefold() and bind(DraftEvidenceField.ALLOWED_PURPOSES, candidate.value, phrase):
                purpose = candidate
                break
        if purpose is None:
            self._uncertain(uncertainties, DelegationUncertaintyCode.AMBIGUOUS_PURPOSE, "allowed_purposes", "The purpose is not stated.", intent)
            questions.append(_question(intent, "purpose", ClarificationCode.CHOOSE_PURPOSE, tuple(item.value for item in DelegationPurpose), when))

        valid_until: date | None = None
        date_match = re.search(r"\b(?:through|until)\s+(\d{4}-\d{2}-\d{2})\b", text, re.IGNORECASE)
        if date_match:
            try:
                valid_until = date.fromisoformat(date_match.group(1))
                bind(DraftEvidenceField.VALID_UNTIL, valid_until.isoformat(), date_match.group(0))
            except ValueError:
                valid_until = None
        if valid_until is None:
            blocking.append(DelegationBlockingCode.MISSING_DURATION)
            self._uncertain(uncertainties, DelegationUncertaintyCode.AMBIGUOUS_DATE, "valid_until", "A bounded end date is required for this draft.", intent)
            questions.append(_question(intent, "valid-until", ClarificationCode.SET_END_DATE, ("7 days", "30 days", "enter a date"), when))

        if injected:
            self._uncertain(uncertainties, DelegationUncertaintyCode.CONTRADICTORY_SCOPE, "untrusted_input", "Untrusted text attempted to alter compiler instructions and was ignored.", intent)
            blocking.append(DelegationBlockingCode.CONTRADICTORY_SCOPE)
        if any(item.blocking for item in uncertainties):
            blocking.append(DelegationBlockingCode.UNRESOLVED_MATERIAL_UNCERTAINTY)

        draft = DelegationDraft(
            schema_version="caretrust.delegation-draft.v1",
            draft_id=f"delegation-draft:{intent.intent_id}:v1",
            draft_version=1,
            intent_id=intent.intent_id,
            intent_sha256=intent.utterance_sha256,
            patient_ref=intent.patient_ref,
            delegate_ref=delegate_ref if any(item.field_path is DraftEvidenceField.DELEGATE_REF for item in bindings) else None,
            relationship_code=relationship if any(item.field_path is DraftEvidenceField.RELATIONSHIP_CODE for item in bindings) else None,
            allowed_actions=tuple(actions),
            allowed_resources=tuple(resources),
            excluded_resources=tuple(excluded),
            allowed_purposes=(purpose,) if purpose else (),
            allowed_audiences=(audience,) if audience else (),
            valid_from=None,
            valid_until=valid_until,
            evidence_bindings=tuple(bindings),
            uncertainties=tuple(uncertainties),
            blocking_issues=tuple(_unique(blocking)),
            proposed_by="ai_model",
            authority_basis="unverified_patient_intent",
            legal_authority_status="not_established",
            status="draft",
            activation_permitted=False,
            authorization_permitted=False,
            synthetic=True,
        )
        return draft, questions

    def _compile_candidate(
        self,
        intent: IntentStatement,
        when: datetime,
        candidate: IntentModelCandidate,
        injected: bool,
    ) -> tuple[DelegationDraft, list[ClarificationRequest]]:
        """Validate a model candidate, then construct the draft from it only."""

        bindings: list[DraftEvidenceBinding] = []
        uncertainties: list[DelegationUncertainty] = []
        blocking: list[DelegationBlockingCode] = []
        questions: list[ClarificationRequest] = []

        def verified(item: CandidateValue, patterns: tuple[str, ...]) -> tuple[str, str]:
            span = next((span for span in intent.spans if span.span_id == item.citation.span_id), None)
            if span is None or item.citation.quote not in span.quote or item.citation.quote not in intent.utterance:
                raise ValueError("model candidate citation is not exact retained intent evidence")
            if patterns and not any(pattern.casefold() in item.citation.quote.casefold() for pattern in patterns):
                raise ValueError("model candidate value is not supported by its cited phrase")
            return item.value, span.span_id

        def enum_value(item: CandidateValue, enum: Any, field: DraftEvidenceField, patterns: Mapping[str, tuple[str, ...]]) -> Any:
            value, span_id = verified(item, patterns.get(item.value, ()))
            try:
                normalized = enum(value)
            except ValueError as exc:
                raise ValueError("model candidate proposed unsupported vocabulary") from exc
            bindings.append(DraftEvidenceBinding(field_path=field, value=normalized.value, evidence_refs=(span_id,)))
            return normalized

        delegate_ref: str | None = None
        relationship: RelationshipCode | None = None
        if candidate.delegate_ref is not None:
            value, span_id = verified(candidate.delegate_ref, ())
            cited_delegate = candidate.delegate_ref.citation.quote.casefold()
            found = [
                ref
                for name, ref in self.delegate_directory.items()
                if re.search(rf"\b{re.escape(name)}\b", cited_delegate)
            ]
            if value not in found:
                raise ValueError("model candidate delegate is not bound to a cited directory identity")
            delegate_ref = value
            bindings.append(DraftEvidenceBinding(field_path=DraftEvidenceField.DELEGATE_REF, value=value, evidence_refs=(span_id,)))
        else:
            blocking.append(DelegationBlockingCode.MISSING_DELEGATE)
            self._uncertain(uncertainties, DelegationUncertaintyCode.AMBIGUOUS_DELEGATE, "delegate_ref", "The model did not propose a cited bounded delegate.", intent)
            questions.append(_question(intent, "delegate", ClarificationCode.IDENTIFY_DELEGATE, ("person:synthetic-leilani-caregiver", "choose another synthetic caregiver"), when))
        if candidate.relationship_code is not None:
            relationship = enum_value(candidate.relationship_code, RelationshipCode, DraftEvidenceField.RELATIONSHIP_CODE, _RELATIONSHIP_PATTERNS)
        elif delegate_ref is not None:
            self._uncertain(uncertainties, DelegationUncertaintyCode.AMBIGUOUS_RELATIONSHIP, "relationship_code", "The model did not propose a cited relationship.", intent)
            questions.append(_question(intent, "relationship", ClarificationCode.CONFIRM_RELATIONSHIP, tuple(item.value for item in RelationshipCode if item is not RelationshipCode.UNSPECIFIED), when))

        actions = _unique([enum_value(item, DelegationAction, DraftEvidenceField.ALLOWED_ACTIONS, _ACTION_PATTERNS) for item in candidate.actions])
        resources = _unique([enum_value(item, DelegationResource, DraftEvidenceField.ALLOWED_RESOURCES, _RESOURCE_PATTERNS) for item in candidate.resources])
        excluded = _unique([enum_value(item, DelegationResource, DraftEvidenceField.EXCLUDED_RESOURCES, _RESOURCE_PATTERNS) for item in candidate.excluded_resources])
        if not actions:
            self._uncertain(uncertainties, DelegationUncertaintyCode.AMBIGUOUS_ACTION, "allowed_actions", "The model did not propose a cited bounded action.", intent)
            questions.append(_question(intent, "action", ClarificationCode.CHOOSE_ACTION, tuple(item.value for item in DelegationAction), when))
        required = frozenset().union(*( _ACTION_TO_RESOURCE[item] for item in actions)) if actions else frozenset()
        if set(resources) != set(required):
            raise ValueError(
                "model candidate resources must exactly match its bounded action requirements"
            )
        if set(resources) & set(excluded):
            raise ValueError("model candidate cannot allow an excluded resource")

        audience = enum_value(candidate.audience, DelegationAudience, DraftEvidenceField.ALLOWED_AUDIENCES, _AUDIENCE_PATTERNS) if candidate.audience else None
        if audience is None:
            blocking.append(DelegationBlockingCode.UNKNOWN_AUDIENCE)
            self._uncertain(uncertainties, DelegationUncertaintyCode.AMBIGUOUS_AUDIENCE, "allowed_audiences", "The model did not propose a cited application audience.", intent)
            questions.append(_question(intent, "audience", ClarificationCode.CHOOSE_AUDIENCE, tuple(item.value for item in DelegationAudience), when))
        purpose = enum_value(candidate.purpose, DelegationPurpose, DraftEvidenceField.ALLOWED_PURPOSES, _PURPOSE_PATTERNS) if candidate.purpose else None
        if purpose is None:
            self._uncertain(uncertainties, DelegationUncertaintyCode.AMBIGUOUS_PURPOSE, "allowed_purposes", "The model did not propose a cited purpose.", intent)
            questions.append(_question(intent, "purpose", ClarificationCode.CHOOSE_PURPOSE, tuple(item.value for item in DelegationPurpose), when))

        valid_until: date | None = None
        if candidate.valid_until is not None:
            value, span_id = verified(candidate.valid_until, (candidate.valid_until.value,))
            try:
                valid_until = date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("model candidate valid_until must be an ISO date") from exc
            if valid_until < when.date():
                raise ValueError("model candidate valid_until must not be in the past")
            bindings.append(DraftEvidenceBinding(field_path=DraftEvidenceField.VALID_UNTIL, value=value, evidence_refs=(span_id,)))
        else:
            blocking.append(DelegationBlockingCode.MISSING_DURATION)
            self._uncertain(uncertainties, DelegationUncertaintyCode.AMBIGUOUS_DATE, "valid_until", "The model did not propose a cited bounded end date.", intent)
            questions.append(_question(intent, "valid-until", ClarificationCode.SET_END_DATE, ("7 days", "30 days", "enter a date"), when))
        if injected:
            self._uncertain(uncertainties, DelegationUncertaintyCode.CONTRADICTORY_SCOPE, "untrusted_input", "Untrusted text attempted to alter compiler instructions and was ignored.", intent)
            blocking.append(DelegationBlockingCode.CONTRADICTORY_SCOPE)
        if any(item.blocking for item in uncertainties):
            blocking.append(DelegationBlockingCode.UNRESOLVED_MATERIAL_UNCERTAINTY)
        return DelegationDraft(
            schema_version="caretrust.delegation-draft.v1", draft_id=f"delegation-draft:{intent.intent_id}:v1", draft_version=1,
            intent_id=intent.intent_id, intent_sha256=intent.utterance_sha256, patient_ref=intent.patient_ref,
            delegate_ref=delegate_ref, relationship_code=relationship, allowed_actions=tuple(actions), allowed_resources=tuple(resources),
            excluded_resources=tuple(excluded), allowed_purposes=(purpose,) if purpose else (), allowed_audiences=(audience,) if audience else (),
            valid_from=None, valid_until=valid_until, evidence_bindings=tuple(bindings), uncertainties=tuple(uncertainties),
            blocking_issues=tuple(_unique(blocking)), proposed_by="ai_model", authority_basis="unverified_patient_intent",
            legal_authority_status="not_established", status="draft", activation_permitted=False, authorization_permitted=False, synthetic=True,
        ), questions

    def _delegate(self, text: str) -> tuple[str | None, RelationshipCode | None, str | None]:
        lowered = text.casefold()
        relationship = next((code for phrase, code in _RELATIONSHIP_RULES if phrase in lowered), None)
        for name, ref in self.delegate_directory.items():
            if re.search(rf"\b{re.escape(name)}\b", lowered):
                phrase = f"{relationship.value.replace('_', ' ')} {name}" if relationship else name
                return ref, relationship, phrase if phrase in lowered else name
        return None, relationship, None

    @staticmethod
    def _uncertain(
        target: list[DelegationUncertainty], code: DelegationUncertaintyCode,
        field: str, message: str, intent: IntentStatement,
    ) -> None:
        refs = tuple(span.span_id for span in intent.spans if span.quote)[:1]
        target.append(DelegationUncertainty(code=code, field_paths=(field,), message=message, evidence_refs=refs, blocking=True))


def _question(intent: IntentStatement, suffix: str, code: ClarificationCode, options: tuple[str, ...], when: datetime) -> ClarificationRequest:
    return ClarificationRequest(
        schema_version="caretrust.clarification-request.v1",
        clarification_id=f"clarification:{intent.intent_id}:{suffix}", intent_id=intent.intent_id,
        draft_id=f"delegation-draft:{intent.intent_id}:v1", code=code,
        field_paths=(suffix.replace("-", "_"),), question=f"Please clarify {suffix.replace('-', ' ')}.",
        options=options, required=True, requested_at=when, synthetic=True,
    )


def _input_safety_flags(text: str) -> list[str]:
    lowered = text.casefold()
    flags: list[str] = []
    if any(item in lowered for item in _INJECTION_PATTERNS):
        flags.append("PROMPT_INJECTION_ATTEMPT")
    if re.search(r"\bprotocol\s+9[-\s]?delta\b", lowered):
        flags.append("UNKNOWN_PROTOCOL_TERM")
    return flags


def _meaningful_hash(compilation: IntentCompilation) -> str:
    return sha256_text(
        canonical_json(
            {
                "draft": compilation.draft.model_dump(mode="json"),
                "clarifications": [item.model_dump(mode="json") for item in compilation.clarifications],
                "safety_flags": list(compilation.safety_flags),
            }
        )
    )


def _unique(values: list[Any]) -> list[Any]:
    return list(dict.fromkeys(values))


def _intent_prompt() -> str:
    return "Compile synthetic patient language into bounded, evidence-cited, review-required delegation drafts. Never assert authority."


_ACTION_RULES = (
    ("schedule appointments", DelegationAction.SCHEDULE_APPOINTMENTS, DelegationResource.APPOINTMENTS),
    ("view appointments", DelegationAction.VIEW_APPOINTMENTS, DelegationResource.APPOINTMENTS),
    ("see visit instructions", DelegationAction.VIEW_VISIT_INSTRUCTIONS, DelegationResource.VISIT_INSTRUCTIONS),
    ("view visit instructions", DelegationAction.VIEW_VISIT_INSTRUCTIONS, DelegationResource.VISIT_INSTRUCTIONS),
    ("message care team", DelegationAction.MESSAGE_CARE_TEAM, DelegationResource.CARE_TEAM_MESSAGES),
)
_EXCLUSION_RULES = (("billing", DelegationResource.BILLING), ("mental health records", DelegationResource.MENTAL_HEALTH_RECORDS))
_AUDIENCE_RULES = (("scheduling app", DelegationAudience.SCHEDULING_APP), ("care portal", DelegationAudience.CARE_PORTAL))
_PURPOSE_RULES = (("appointment management", DelegationPurpose.APPOINTMENT_MANAGEMENT), ("care coordination", DelegationPurpose.CARE_COORDINATION))
_RELATIONSHIP_RULES = (("daughter", RelationshipCode.CHILD), ("son", RelationshipCode.CHILD), ("spouse", RelationshipCode.SPOUSE_OR_PARTNER), ("partner", RelationshipCode.SPOUSE_OR_PARTNER), ("friend", RelationshipCode.FRIEND), ("neighbor", RelationshipCode.NEIGHBOR))
_ACTION_PATTERNS = {
    DelegationAction.SCHEDULE_APPOINTMENTS.value: ("schedule appointments",),
    DelegationAction.VIEW_APPOINTMENTS.value: (
        "view appointments",
        "look at appointments",
        "look at upcoming appointments",
    ),
    DelegationAction.VIEW_VISIT_INSTRUCTIONS.value: ("see visit instructions", "view visit instructions"),
    DelegationAction.MESSAGE_CARE_TEAM.value: ("message care team",),
}
_RESOURCE_PATTERNS = {
    DelegationResource.APPOINTMENTS.value: ("appointment",),
    DelegationResource.VISIT_INSTRUCTIONS.value: ("visit instruction",),
    DelegationResource.CARE_TEAM_MESSAGES.value: ("care team message", "message care team"),
    DelegationResource.BILLING.value: ("billing",),
    DelegationResource.MENTAL_HEALTH_RECORDS.value: ("mental health records",),
}
_AUDIENCE_PATTERNS = {
    DelegationAudience.SCHEDULING_APP.value: ("scheduling app",),
    DelegationAudience.CARE_PORTAL.value: ("care portal",),
}
_PURPOSE_PATTERNS = {
    DelegationPurpose.APPOINTMENT_MANAGEMENT.value: ("appointment management",),
    DelegationPurpose.CARE_COORDINATION.value: ("care coordination",),
}
_RELATIONSHIP_PATTERNS = {
    RelationshipCode.CHILD.value: ("daughter", "son"),
    RelationshipCode.SPOUSE_OR_PARTNER.value: ("spouse", "partner"),
    RelationshipCode.FRIEND.value: ("friend",),
    RelationshipCode.NEIGHBOR.value: ("neighbor",),
    RelationshipCode.PARENT.value: ("parent",),
    RelationshipCode.SIBLING.value: ("sibling",),
    RelationshipCode.OTHER_FAMILY.value: ("family",),
    RelationshipCode.OTHER_PERSONAL_RELATIONSHIP.value: ("relationship",),
    RelationshipCode.UNSPECIFIED.value: (),
}
_ACTION_TO_RESOURCE = {
    DelegationAction.SCHEDULE_APPOINTMENTS: frozenset({DelegationResource.APPOINTMENTS}),
    DelegationAction.VIEW_APPOINTMENTS: frozenset({DelegationResource.APPOINTMENTS}),
    DelegationAction.VIEW_VISIT_INSTRUCTIONS: frozenset({DelegationResource.VISIT_INSTRUCTIONS}),
    DelegationAction.MESSAGE_CARE_TEAM: frozenset({DelegationResource.CARE_TEAM_MESSAGES}),
}
