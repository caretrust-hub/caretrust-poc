"use strict";

const messages = {
  intent: {
    title: "IntentStatement",
    status: "Executed local",
    sender: "Authenticated synthetic patient session",
    receiver: "CareTrust intent service",
    contract: "caretrust.intent-statement.v1",
    standard: "CareTrust native contract",
    boundary: "The utterance is patient-supplied input. It is not consent, proof of relationship, legal authority, or permission.",
    json: {
      schema_version: "caretrust.intent-statement.v1",
      intent_id: "intent:synthetic-delegation-001",
      patient_ref: "patient:synthetic-001",
      utterance: "Let my daughter Leilani schedule appointments and see visit instructions through 2026-12-31, but not billing or mental health records.",
      utterance_sha256: "686fd43d9a47107538b81c1f7b2a848445ca8d4d2d624d207afaf141e8446fc4",
      created_at: "2026-07-30T10:00:00Z",
      synthetic: true
    }
  },
  draft: {
    title: "DelegationDraft",
    status: "Executed local",
    sender: "AI intent adapter",
    receiver: "Deterministic safety gate",
    contract: "caretrust.delegation-draft.v1",
    standard: "CareTrust native contract",
    boundary: "AI may emit only draft or clarification state. activation_permitted and authorization_permitted are structurally false.",
    json: {
      schema_version: "caretrust.delegation-draft.v1",
      draft_id: "delegation-draft:synthetic-001:v2",
      intent_id: "intent:synthetic-delegation-001",
      status: "draft",
      proposed_by: "ai_model",
      authority_basis: "unverified_patient_intent",
      relationship_code: "child",
      allowed_actions: ["schedule_appointments", "view_visit_instructions"],
      allowed_resources: ["appointments", "visit_instructions"],
      excluded_resources: ["billing", "mental_health_records"],
      allowed_audiences: ["app:synthetic-scheduling", "app:synthetic-care-portal"],
      valid_until: "2026-12-31",
      activation_permitted: false,
      authorization_permitted: false,
      legal_authority_status: "not_established",
      synthetic: true
    }
  },
  clarification: {
    title: "ClarificationRequest + Response",
    status: "Executed local",
    sender: "CareTrust clarification service",
    receiver: "Authenticated synthetic patient session",
    contract: "caretrust.clarification-request.v1",
    standard: "CareTrust native contracts",
    boundary: "The patient response narrows the proposed audiences and is hash-bound into approval; it does not authorize access by itself.",
    json: {
      request: {
        clarification_id: "clarification:synthetic-audience-001",
        draft_id: "delegation-draft:synthetic-001:v1",
        code: "CHOOSE_AUDIENCE",
        question: "Which synthetic applications should Leilani be able to use?",
        options: ["app:synthetic-scheduling", "app:synthetic-care-portal"],
        required: true
      },
      response: {
        response_id: "clarification-response:synthetic-001",
        patient_ref: "patient:synthetic-001",
        selected_values: ["app:synthetic-scheduling", "app:synthetic-care-portal"],
        response_sha256: "ad65b0cec76088dbd75579c157acf0bd753d1a904bb2a41c753663483c1fc83d"
      }
    }
  },
  invite: {
    title: "PatientInvite",
    status: "Executed local",
    sender: "CareTrust invitation service",
    receiver: "Synthetic out-of-band channel",
    contract: "caretrust.patient-invite.v1",
    standard: "CareTrust native contract",
    boundary: "No recipient contact, invite token, or nonce is retained in plaintext. The invite is synthetic, expiring, and single use.",
    json: {
      schema_version: "caretrust.patient-invite.v1",
      invite_id: "invite:synthetic-001",
      patient_ref: "patient:synthetic-001",
      draft_id: "delegation-draft:synthetic-001:v2",
      delivery_channel: "synthetic_out_of_band",
      recipient_hint_sha256: "fcd4304af64f47429d3faf287ee7594ac92f6dfb8b614bfecd901bca3b5d62f2",
      invite_token_sha256: "667eff78639bb145217c5a625ec85cc03d90d9e0181504c5c220c1b948ebeb2a",
      nonce_sha256: "a279b165334303a3f576eb0e583db2bc4b830060ec2b9fae256acbfdbab5e049",
      status: "pending",
      single_use: true,
      expires_at: "2026-07-30T11:01:00Z",
      synthetic: true
    }
  },
  acceptance: {
    title: "InviteAcceptance",
    status: "Executed local",
    sender: "Synthetic invited account",
    receiver: "CareTrust invitation service",
    contract: "caretrust.invite-acceptance.v1",
    standard: "CareTrust native contract",
    boundary: "Acceptance shows control of a synthetic invited account only. It establishes neither identity, relationship, patient consent, delegation, nor legal authority.",
    json: {
      schema_version: "caretrust.invite-acceptance.v1",
      acceptance_id: "invite-acceptance:synthetic-001",
      invite_id: "invite:synthetic-001",
      caregiver_ref: "account:synthetic-leilani",
      patient_ref: "patient:synthetic-001",
      status: "accepted",
      identity_assurance: "synthetic_account_only",
      relationship_verified: false,
      patient_consent_established: false,
      delegation_activated: false,
      legal_authority_status: "not_established",
      synthetic: true
    }
  },
  approval: {
    title: "PatientApprovalRecord",
    status: "Executed local",
    sender: "Authenticated synthetic patient session",
    receiver: "CareTrust approval service",
    contract: "caretrust.patient-approval-record.v1",
    standard: "CareTrust native contract",
    boundary: "Approval is bound to the exact intent, clarification bundle, final draft, and invite acceptance. Approval is necessary but not sufficient for application access.",
    json: {
      schema_version: "caretrust.patient-approval-record.v1",
      approval_id: "approval:synthetic-001",
      patient_ref: "patient:synthetic-001",
      final_draft_id: "delegation-draft:synthetic-001:v2",
      invite_acceptance_id: "invite-acceptance:synthetic-001",
      decision: "approved",
      explicit_patient_action: true,
      approval_basis: "patient_attestation",
      activation_permitted: false,
      authorization_permitted: false,
      legal_authority_status: "not_established",
      approved_at: "2026-07-30T10:03:00Z",
      synthetic: true
    }
  },
  relationship: {
    title: "CareRelationshipClaim",
    status: "Executed local",
    sender: "CareTrust claim service",
    receiver: "Organization case projection",
    contract: "caretrust.care-relationship-claim.v1",
    standard: "RelatedPerson candidate projection",
    boundary: "This is a patient-asserted relationship only. It contains no permission scope and does not establish formal responsibility or legal authority.",
    json: {
      relationship_claim_id: "relationship:synthetic-001",
      patient_ref: "patient:synthetic-001",
      caregiver_ref: "account:synthetic-leilani",
      relationship_code: "child",
      relationship_basis: "patient_attestation",
      relationship_assertion_only: true,
      status: "active",
      legal_authority_status: "not_established",
      valid_until: "2026-12-31",
      synthetic: true
    }
  },
  grant: {
    title: "Linked relationship + delegation",
    status: "Executed local",
    sender: "CareTrust claim service",
    receiver: "Registered synthetic applications",
    contract: "caretrust.delegation-grant.v1",
    standard: "FHIR Consent + OAuth RAR candidate projections",
    boundary: "The relationship and delegation are separate artifacts. The active grant supports a request but every application must apply its own current policy.",
    json: {
      grant_id: "grant:synthetic-001",
      relationship_claim_id: "relationship:synthetic-001",
      patient_ref: "patient:synthetic-001",
      delegate_ref: "account:synthetic-leilani",
      allowed_actions: ["schedule_appointments", "view_visit_instructions"],
      allowed_resources: ["appointments", "visit_instructions"],
      excluded_resources: ["billing", "mental_health_records"],
      allowed_audiences: ["app:synthetic-scheduling", "app:synthetic-care-portal"],
      allowed_purposes: ["appointment_management", "care_coordination"],
      status: "active",
      application_decision_required: true,
      legal_authority_status: "not_established",
      valid_until: "2026-12-31",
      synthetic: true
    }
  },
  "schedule-decision": {
    title: "Scheduling authorization decision",
    status: "Executed local",
    sender: "Kākou Scheduling",
    receiver: "CareTrust authorization service",
    contract: "caretrust.delegation-authorization.v1",
    standard: "OAuth RAR candidate projection",
    boundary: "The scheduling application makes an independent, current decision for one audience, purpose, action, and resource.",
    json: {
      request: { request_id: "delegation-request:synthetic-001", grant_id: "grant:synthetic-001", audience: "app:synthetic-scheduling", purpose: "appointment_management", action: "schedule_appointments", resource: "appointments", requested_at: "2026-07-30T10:04:00Z" },
      decision: { decision_id: "delegation-decision:synthetic-001", policy_version: "caretrust.delegation-authorization.v1", decision: "permit", reason_codes: ["POLICY_REQUIREMENTS_SATISFIED"], supporting_grant_ids: ["grant:synthetic-001"], decided_at: "2026-07-30T10:04:01Z" }
    }
  },
  "portal-decision": {
    title: "Care-portal authorization decision",
    status: "Executable scenario",
    sender: "Care Instructions app",
    receiver: "CareTrust authorization service",
    contract: "caretrust.delegation-authorization.v1",
    standard: "OAuth RAR candidate projection",
    boundary: "A second application evaluates the same grant independently and receives no billing, mental-health, or underlying eligibility evidence.",
    json: {
      request: { request_id: "delegation-request:synthetic-portal-001", grant_id: "grant:synthetic-001", audience: "app:synthetic-care-portal", purpose: "care_coordination", action: "view_visit_instructions", resource: "visit_instructions" },
      decision: { decision_id: "delegation-decision:synthetic-portal-001", policy_version: "caretrust.delegation-authorization.v1", decision: "permit", reason_codes: ["POLICY_REQUIREMENTS_SATISFIED"], supporting_grant_ids: ["grant:synthetic-001"] },
      disclosure_summary: { claim_ids: ["grant:synthetic-001"], raw_evidence_shared: false }
    }
  },
  "medication-denial": {
    title: "Unknown-action denial",
    status: "Fail-closed scenario",
    sender: "Unregistered medication action",
    receiver: "CareTrust request validator",
    contract: "caretrust.delegation-authorization.v1",
    standard: "CareTrust governed vocabulary",
    boundary: "Medication refill is outside the governed action vocabulary and outside this grant. The request fails before any clinical-data processing.",
    json: {
      attempted_request: { audience: "app:synthetic-medication", purpose: "care_coordination", action: "medication_refill", resource: "medication_request" },
      decision: { decision: "deny", policy_version: "caretrust.delegation-authorization.v1", reason_codes: ["ACTION_NOT_IN_VOCABULARY", "ACTION_NOT_DELEGATED"], supporting_grant_ids: [], data_released: false }
    }
  },
  "case-assignment": {
    title: "CaseAssignmentEvent",
    status: "UI fixture",
    sender: "Synthetic organization console",
    receiver: "Case projection",
    contract: "caretrust.case-event.candidate.v1",
    standard: "No standards claim",
    boundary: "The coordinator assignment is illustrative organization workflow state, not part of the executed delegation contract family.",
    json: { case_id: "case:synthetic-0042", coordinator_ref: "staff:synthetic-nohea", organization_ref: "org:synthetic-ke-ola", status: "assigned", synthetic: true }
  },
  "care-document": {
    title: "UploadedCareDocument",
    status: "Executable contract in progress",
    sender: "Invited synthetic caregiver account",
    receiver: "CareTrust restricted document store",
    contract: "caretrust.uploaded-care-document.v1",
    standard: "FHIR DocumentReference candidate projection",
    boundary: "Uploader provenance identifies who supplied this copy. It does not prove clinical authorship, authenticity, accuracy, currentness, or legal authority.",
    json: {
      document_id: "care-document:synthetic-discharge-001",
      patient_ref: "patient:synthetic-001",
      uploader_ref: "account:synthetic-leilani",
      uploader_capacity: "patient_invited_coordinator",
      source_assertion: "patient_provided_unverified_copy",
      artifact_sha256: "8a21f39d73e98b7ba6e0db2d818a75db8ead76c3912e7d540d3fb62207a24d9c",
      content_type: "application/pdf",
      page_count: 3,
      data_classification: "synthetic_health_information",
      file_validation: "passed",
      malware_scan: "passed",
      document_authorship_verified: false,
      clinically_current_verified: false,
      synthetic: true
    }
  },
  "document-extraction": {
    title: "DocumentExtractionDraft",
    status: "AI draft · unverified",
    sender: "CareTrust document AI adapter",
    receiver: "Document safety and review gate",
    contract: "caretrust.document-extraction-draft.v1",
    standard: "CareTrust native evidence model",
    boundary: "The model locates and classifies candidate coordination items. It cannot create clinical facts, medication orders, approved Tasks, or sharing permission.",
    json: {
      extraction_id: "document-extraction:synthetic-001",
      document_id: "care-document:synthetic-discharge-001",
      status: "draft",
      clinical_authority_established: false,
      candidates: [
        { item_id: "coordination-item:followup-001", category: "administrative_follow_up", proposed_action: "schedule_follow_up", source: { page: 1, lines: [14, 16], quote: "Schedule a follow-up visit with the cardiology clinic within 7 days.", region: [82, 430, 1180, 512] }, status: "human_review_required" },
        { item_id: "coordination-item:weight-log-001", category: "caregiver_reminder", proposed_action: "record_weight_log", source: { page: 1, lines: [18, 19], quote: "Record weight each morning and bring the log to the next visit.", region: [82, 530, 1180, 612] }, status: "human_review_required" },
        { item_id: "coordination-item:medication-001", category: "medication_evidence", proposed_action: null, source: { page: 1, lines: [21, 23] }, status: "clinical_review_required", blocking_code: "CLINICAL_SOURCE_CLARIFICATION_REQUIRED" },
        { item_id: "coordination-item:warning-001", category: "warning_sign_evidence", proposed_action: null, source: { page: 1, lines: [25, 26] }, status: "clinical_review_required", blocking_code: "CLINICAL_SOURCE_CLARIFICATION_REQUIRED" }
      ],
      forbidden_outputs: ["MedicationRequest", "MedicationStatement", "active CarePlan"],
      synthetic: true
    }
  },
  "document-review": {
    title: "DocumentItemReviewRecord",
    status: "Executable contract in progress",
    sender: "Patient + organization coordinator",
    receiver: "CareTrust coordination router",
    contract: "caretrust.document-item-review.v1",
    standard: "FHIR Task candidate projection",
    boundary: "Patient approval selects administrative coordination intent; organization review confirms routing. Neither action clinically validates medication or warning-sign content.",
    json: {
      review_id: "document-review:synthetic-001",
      document_id: "care-document:synthetic-discharge-001",
      patient_approved_item_ids: ["coordination-item:followup-001", "coordination-item:weight-log-001"],
      coordinator_routing_confirmed: true,
      clinical_items_blocked: ["coordination-item:medication-001", "coordination-item:warning-001"],
      reviewed_extraction_id: "document-extraction:synthetic-001",
      decision: "approved_for_bounded_routing",
      synthetic: true
    }
  },
  "document-share": {
    title: "Purpose-minimized route requests",
    status: "Executable contract in progress",
    sender: "CareTrust coordination router",
    receiver: "Independent synthetic applications",
    contract: "caretrust.document-item-route-request.v1",
    standard: "FHIR Task candidate projection",
    boundary: "Each app receives a disjoint projection. The raw packet, medications, warning signs, diagnosis, and unrelated case history are excluded.",
    json: {
      requests: [
        { route_id: "route:followup-001", item_id: "coordination-item:followup-001", audience: "app:synthetic-scheduling", purpose: "coordinate_approved_follow_up", included_fields: ["subject", "requested_window", "provider_role", "source_reference"], excluded_fields: ["raw_document", "medications", "warning_signs", "diagnosis"] },
        { route_id: "route:weight-log-001", item_id: "coordination-item:weight-log-001", audience: "app:synthetic-direct-care-tasks", purpose: "caregiver_reminder", included_fields: ["subject", "reminder_text", "source_reference"], excluded_fields: ["raw_document", "diagnosis", "medications", "warning_signs"] }
      ],
      raw_document_shared: false,
      synthetic: true
    }
  },
  "document-denial": {
    title: "Clinical-item routing denial",
    status: "Fail-closed scenario",
    sender: "Medication Support app",
    receiver: "CareTrust coordination router",
    contract: "caretrust.document-item-route-decision.v1",
    standard: "CareTrust native policy",
    boundary: "A patient-provided discharge excerpt cannot create or modify a medication order or a structured statement of what the patient is taking.",
    json: { item_id: "coordination-item:medication-001", decision: "deny", reason_codes: ["CLINICAL_REVIEW_REQUIRED", "NO_MEDICATION_ORDER_AUTHORITY"], data_released: false, generated_resources: [], synthetic: true }
  },
  "clinical-permit": {
    title: "Synthetic clinical-data holder receipt",
    status: "Local simulation",
    sender: "Authorized synthetic organization application",
    receiver: "Synthetic clinical-data holder",
    contract: "caretrust.clinical-data-handoff.candidate.v1",
    standard: "FHIR R4-shaped local Bundle + CarePlan fixture",
    boundary: "No HIE or EHR was contacted. The holder independently established synthetic participant/user trust, patient match, and disclosure policy before returning one bounded fixture.",
    json: {
      request: { participant_org_ref: "org:synthetic-ke-ola", authorized_user_ref: "staff:synthetic-nohea", caretrust_role: "delegation_and_trust_context_only", patient_match_hint: "patient:synthetic-001", purpose: "care_coordination", requested_fhir_resource_types: ["CarePlan"], requested_scopes: ["patient/CarePlan.rs"], caretrust_context_id: "context:clinical:permit-001" },
      holder_decision: { decision: "permit", patient_match_authority: "data_holder", disclosure_policy_authority: "data_holder", policy_version: "synthetic.data-holder.disclosure.v1", reason_codes: ["DATA_HOLDER_POLICY_SATISFIED"], fhir_bundle_included: true },
      returned_fhir_bundle: { resourceType: "Bundle", type: "collection", entry: [{ resource: { resourceType: "CarePlan", id: "synthetic-care-plan-001", status: "active", intent: "plan", title: "Synthetic caregiver visit instructions" } }] },
      live_hie_or_ehr_connected: false,
      network_calls: false
    }
  },
  revocation: {
    title: "DelegationRevocationRecord",
    status: "Executed local",
    sender: "Authenticated synthetic patient session",
    receiver: "CareTrust status service",
    contract: "caretrust.delegation-revocation-record.v1",
    standard: "FHIR Consent inactive projection candidate",
    boundary: "The relationship may remain current. Revocation makes fresh local authorization requests deny; no existing-session termination is claimed.",
    json: { schema_version: "caretrust.delegation-revocation-record.v1", revocation_id: "delegation-revocation:synthetic-001", grant_id: "grant:synthetic-001", actor_ref: "patient:synthetic-001", reason_code: "PATIENT_REVOKED_DELEGATION", revoked_at: "2026-07-30T10:05:00Z", synthetic: true }
  },
  "post-revocation-denial": {
    title: "Revocation + fresh authorization denial",
    status: "Executed local trace",
    sender: "Synthetic patient, caregiver, and scheduling policy",
    receiver: "CareTrust status seam and requesting account",
    contract: "CareTrust revocation, request, and decision v1 messages",
    standard: "FHIR Consent inactive projection candidate + CareTrust policy",
    boundary: "The fresh request is evaluated after revocation and denied with GRANT_REVOKED. Earlier receipts remain historical; termination of an existing application session is not claimed.",
    json: {
      revocation: {
        schema_version: "caretrust.delegation-revocation-record.v1",
        revocation_id: "delegation-revocation:synthetic-001",
        grant_id: "grant:synthetic-001",
        actor_ref: "patient:synthetic-001",
        reason_code: "PATIENT_REVOKED_DELEGATION",
        revoked_at: "2026-07-30T10:05:00Z",
        synthetic: true
      },
      fresh_request: {
        schema_version: "caretrust.delegation-authorization-request.v1",
        request_id: "delegation-request:synthetic-002",
        grant_id: "grant:synthetic-001",
        patient_ref: "patient:synthetic-001",
        delegate_ref: "account:synthetic-leilani",
        audience: "app:synthetic-scheduling",
        action: "schedule_appointments",
        resource: "appointments",
        purpose: "appointment_management",
        requested_at: "2026-07-30T10:05:01Z",
        synthetic: true
      },
      fresh_decision: {
        schema_version: "caretrust.delegation-authorization-decision.v1",
        decision_id: "delegation-decision:synthetic-002",
        request_id: "delegation-request:synthetic-002",
        decision: "deny",
        reason_codes: ["GRANT_REVOKED"],
        supporting_grant_ids: [],
        policy_version: "caretrust.delegation-authorization.v1",
        decided_at: "2026-07-30T10:05:02Z",
        synthetic: true
      }
    }
  }
};

const retained = window.CARETRUST_DEMO_DATA;
const caseDecision = (requestId) => retained.case_bundle.decisions.find((item) => item.request_id === requestId);
const providerProof = retained.provider_operations;

document.querySelector("#care-context-count").textContent = String(providerProof.care_context_count);
document.querySelector("#application-count").textContent = String(providerProof.application_count);
document.querySelector("#decision-count").textContent = String(providerProof.decision_count);
document.querySelector("#decision-split").textContent = `${providerProof.permit_count} permit · ${providerProof.deny_count} fail-closed`;
document.querySelector("#field-outcome-label").textContent = providerProof.field_outcome_label;
document.querySelector("#field-outcome-next").textContent = providerProof.field_outcome_next_step;

Object.assign(messages, {
  "family-lifecycle": {
    title: "Family caregiver decision lifecycle",
    status: "Executed local",
    sender: "Kākou Scheduling reference client",
    receiver: "CareTrust case-access.v1 policy",
    contract: "CareTrust Core case decision",
    standard: "OAuth RAR care-data profile candidate",
    boundary: "The relationship and grant support only the requested scheduling transaction. A fresh request after patient revocation denies; historical receipts remain.",
    json: {
      permit: caseDecision("request:case:family-permit-001"),
      wrong_purpose_deny: caseDecision("request:case:family-wrong-purpose-001"),
      post_revocation_fresh_deny: caseDecision("request:case:family-revoked-001")
    }
  },
  "cna-lifecycle": {
    title: "Agency CNA decision lifecycle",
    status: "Executed local",
    sender: "Direct Care Tasks reference client",
    receiver: "CareTrust case-access.v1 policy",
    contract: "CareTrust Core case decision",
    standard: "W3C VC / FHIR Practitioner qualification mappings + OAuth RAR candidate",
    boundary: "An organization role alone is insufficient. The permit requires a current reviewed credential claim, active organization assignment, patient-specific task grant, app audience, purpose, and action. Revoking the claim produces a fresh deny.",
    json: {
      permit: caseDecision("request:case:cna-permit-001"),
      missing_claim_deny: caseDecision("request:case:cna-missing-claim-001"),
      post_revocation_fresh_deny: caseDecision("request:case:cna-revoked-001")
    }
  },
  "respite-lifecycle": {
    title: "Community respite decision lifecycle",
    status: "Contract tested",
    sender: "Respite Connect reference client",
    receiver: "CareTrust case-access.v1 policy",
    contract: "CareTrust Core case decision",
    standard: "CareTrust time-bounded service grant + OAuth RAR candidate",
    boundary: "The service assignment is time bounded. Unverified clinical content remains blocked even during the valid service window; expiry and revocation each fail closed.",
    json: {
      historical_permit: caseDecision("request:case:respite-historical-001"),
      clinical_content_deny: caseDecision("request:case:respite-clinical-block-001"),
      expired_assignment_deny: caseDecision("request:case:respite-expired-001"),
      post_revocation_fresh_deny: caseDecision("request:case:respite-revoked-001")
    }
  },
  "app-compilation": {
    title: "AI-assisted application onboarding draft",
    status: retained.application_compilation.evidence_status,
    sender: "Retained OpenAPI requirements",
    receiver: "Human application reviewer",
    contract: retained.application_compilation.schema_version,
    standard: "OpenAPI input → OAuth RAR + CareTrust app profile candidates",
    boundary: "AI proposes capabilities, actions, locations, and a minimum-data plan. It cannot register, activate, trust, or authorize the application.",
    json: retained.application_compilation
  },
  "auth-flow": {
    title: "Synthetic app authentication and authorization trace",
    status: retained.auth_harness.evidence_status,
    sender: "Synthetic caregiver + reviewed application",
    receiver: "CareTrust authorization harness",
    contract: retained.auth_harness.record_type,
    standard: "OIDC identity link + OAuth Authorization Code, PKCE, RAR",
    boundary: retained.auth_harness.non_claims.join(" "),
    json: {
      identity_link: retained.auth_harness.upstream_identity_link,
      reviewed_registration: retained.auth_harness.human_reviewed_registration,
      authorization_request: retained.auth_harness.authorization_code_request,
      fresh_case_decision: retained.auth_harness.fresh_case_decision,
      downstream_token_receipt: retained.auth_harness.downstream_token_receipt
    }
  },
  "fhir-scheduling": {
    title: "FHIR/SMART scheduling projection",
    status: retained.fhir_scheduling.evidence_status,
    sender: "CareTrust case decision",
    receiver: "Synthetic scheduling reference client",
    contract: retained.fhir_scheduling.schema_version,
    standard: "FHIR R4 Appointment/AppointmentResponse + SMART App Launch resource scopes",
    boundary: retained.fhir_scheduling.non_claims.join(" "),
    json: {
      action_mapping: retained.fhir_scheduling.business_action_mapping,
      capability_matrix: retained.fhir_scheduling.capability_matrix,
      appointment_workflow: retained.fhir_scheduling.proposed_appointment_workflow,
      fresh_revocation_check: retained.fhir_scheduling.fresh_revocation_check
    }
  },
  "federation-lab": {
    title: "Two-hub federation laboratory",
    status: retained.federation_lab.evidence_status,
    sender: "Two independently keyed synthetic CareTrust hubs",
    receiver: "Locally pinned federation trust anchors",
    contract: retained.federation_lab.artifact_type,
    standard: "OpenID Federation 1.0 local profile laboratory",
    boundary: retained.federation_lab.claim_boundary.join(" "),
    json: {
      hubs: retained.federation_lab.two_independent_hubs,
      resolved_trust: retained.federation_lab.participant_and_client_entity_trust,
      negative_exercises: retained.federation_lab.negative_exercises,
      key_rollover: retained.federation_lab.key_rollover,
      fresh_local_decision_after_trust: retained.federation_lab.fresh_local_caregiver_decision_after_trust,
      network_calls: retained.federation_lab.network_calls
    }
  }
});

const tabs = [...document.querySelectorAll(".workspace-tabs [data-view]")];
const panels = [...document.querySelectorAll(".workspace-view[data-panel]")];
const inspector = document.querySelector("#message-inspector");
const inspectorTitle = document.querySelector("#inspector-title");
const inspectorStatus = document.querySelector("#inspector-status");
const messageMeta = document.querySelector("#message-meta");
const messageJson = document.querySelector("#message-json");
const inspectorBoundary = document.querySelector("#inspector-boundary");
const evidenceDialog = document.querySelector("#evidence-dialog");
let revoked = false;
let reviewHistoryRecorded = false;
let routeHistoryRecorded = false;

function switchView(name) {
  tabs.forEach((tab) => {
    const selected = tab.dataset.view === name;
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", String(selected));
  });
  panels.forEach((panel) => {
    const selected = panel.dataset.panel === name;
    panel.hidden = !selected;
    panel.classList.toggle("active", selected);
  });
}

function showMessage(key) {
  const message = messages[key];
  if (!message) return;
  inspectorTitle.textContent = message.title;
  inspectorStatus.textContent = message.status;
  messageMeta.innerHTML = [
    ["Sender", message.sender],
    ["Receiver", message.receiver],
    ["Contract", message.contract],
    ["Standard / profile", message.standard]
  ].map(([term, value]) => `<div><dt>${term}</dt><dd>${value}</dd></div>`).join("");
  messageJson.textContent = JSON.stringify(message.json, null, 2);
  inspectorBoundary.textContent = message.boundary;
  inspector.showModal();
}

tabs.forEach((tab) => tab.addEventListener("click", () => switchView(tab.dataset.view)));
document.querySelectorAll("[data-switch]").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.switch)));
document.querySelectorAll("[data-message]").forEach((button) => button.addEventListener("click", () => showMessage(button.dataset.message)));
document.querySelector("#close-inspector").addEventListener("click", () => inspector.close());
document.querySelector("#open-evidence").addEventListener("click", () => evidenceDialog.showModal());
document.querySelector("#close-evidence").addEventListener("click", () => evidenceDialog.close());
document.querySelector("#copy-message").addEventListener("click", async (event) => {
  await navigator.clipboard.writeText(messageJson.textContent);
  event.currentTarget.textContent = "Copied";
  setTimeout(() => { event.currentTarget.textContent = "Copy"; }, 1200);
});

document.querySelectorAll(".evidence-button[data-highlight]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".discharge-page mark").forEach((mark) => mark.classList.remove("focused"));
    const evidence = document.querySelector(`.discharge-page mark[data-evidence="${button.dataset.highlight}"]`);
    if (evidence) {
      evidence.classList.add("focused");
      evidence.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  });
});

document.querySelector("#review-document-items").addEventListener("click", (event) => {
  document.querySelector("#packet-sharing").hidden = false;
  document.querySelectorAll('.extracted-items li[data-item-state="ready"] .review-state').forEach((state) => {
    state.textContent = "Patient approved · routing ready";
  });
  event.currentTarget.textContent = "2 administrative items approved";
  event.currentTarget.disabled = true;
  if (!reviewHistoryRecorded) {
    const historyItem = document.createElement("li");
    historyItem.innerHTML = "<time>10:04:30</time><span class=\"event-dot patient\"></span><div><strong>Patient approved two administrative items</strong><p>Organization coordinator confirmed routing; two clinical items remain blocked.</p><button class=\"trace-link\" type=\"button\">DocumentItemReviewRecord</button></div>";
    historyItem.querySelector("button").addEventListener("click", () => showMessage("document-review"));
    document.querySelector("#case-history").append(historyItem);
    reviewHistoryRecorded = true;
    document.querySelector("#history-count").textContent = String(document.querySelectorAll("#case-history li").length);
  }
  document.querySelector("#packet-sharing").scrollIntoView({ block: "nearest", behavior: "smooth" });
});

document.querySelector("#run-document-sharing").addEventListener("click", () => {
  const result = document.querySelector("#clinical-result");
  if (revoked) {
    result.className = "clinical-result deny";
    result.innerHTML = "<span>Deny</span><strong>DELEGATION_REVOKED · no new items disclosed</strong><small>Historical receipts remain</small>";
    return;
  }
  result.className = "clinical-result permit";
  result.innerHTML = "<span>Routed</span><strong>2 disjoint coordination items · raw packet withheld</strong><button class=\"trace-link\" type=\"button\" id=\"document-receipt\">Inspect disclosure receipts</button>";
  document.querySelectorAll(".pending-share").forEach((state) => {
    state.className = "decision permit";
    state.textContent = "PERMIT";
  });
  document.querySelector("#document-receipt").addEventListener("click", () => showMessage("document-share"));
  if (!routeHistoryRecorded) {
    const historyItem = document.createElement("li");
    historyItem.innerHTML = "<time>10:04:40</time><span class=\"event-dot app\"></span><div><strong>Two purpose-minimized items routed</strong><p>Scheduling and direct-care apps received disjoint projections; raw packet and clinical items were withheld.</p><button class=\"trace-link\" type=\"button\">Route requests + receipts</button></div>";
    historyItem.querySelector("button").addEventListener("click", () => showMessage("document-share"));
    document.querySelector("#case-history").append(historyItem);
    routeHistoryRecorded = true;
    document.querySelector("#history-count").textContent = String(document.querySelectorAll("#case-history li").length);
  }
});

document.querySelector("#revoke-grant").addEventListener("click", (event) => {
  if (revoked) return;
  revoked = true;
  event.currentTarget.textContent = "Permission revoked";
  event.currentTarget.disabled = true;
  document.querySelector(".case-state .status").className = "status neutral";
  document.querySelector(".case-state .status").innerHTML = "<i aria-hidden=\"true\"></i> Delegation revoked";
  const grantSummary = document.querySelector("#grant-summary");
  if (grantSummary) grantSummary.textContent = "Revoked · history retained";
  const clinicalGrantState = document.querySelector("#clinical-grant-state");
  if (clinicalGrantState) clinicalGrantState.textContent = "Revoked";
  const history = document.querySelector("#case-history");
  const eventItem = document.createElement("li");
  eventItem.innerHTML = "<time>10:05:00</time><span class=\"event-dot patient\"></span><div><strong>Malia revoked the delegation</strong><p>The relationship remains; a fresh scheduling request is denied with GRANT_REVOKED.</p><button class=\"trace-link\" type=\"button\" data-message=\"post-revocation-denial\">Inspect revocation + fresh denial</button></div>";
  history.append(eventItem);
  eventItem.querySelector("button").addEventListener("click", () => showMessage("post-revocation-denial"));
  document.querySelector("#history-count").textContent = String(document.querySelectorAll("#case-history li").length);
  switchView("history");
});
