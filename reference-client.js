"use strict";

const retained = window.CARETRUST_DEMO_DATA;
const inspector = document.querySelector("#inspector");
const inspectorTitle = document.querySelector("#inspector-title");
const inspectorKind = document.querySelector("#inspector-kind");
const inspectorMeta = document.querySelector("#inspector-meta");
const inspectorBoundary = document.querySelector("#inspector-boundary");
const inspectorJson = document.querySelector("#inspector-json");
const latestDecision = document.querySelector("#latest-decision");
let revoked = false;

const records = {
  invite: {
    title: "PatientInvite",
    contract: retained.invite.schema_version,
    standard: "CareTrust Core 0.1",
    evidence: "Executed local",
    boundary: "The expiring, single-use invitation starts an account-binding workflow. It does not establish identity, relationship, consent, delegation, or legal authority.",
    json: retained.invite
  },
  acceptance: {
    title: "InviteAcceptance",
    contract: retained.acceptance.schema_version,
    standard: "CareTrust Core 0.1",
    evidence: "Executed local",
    boundary: "Acceptance binds the invitation to an authenticated synthetic account. All authority booleans remain false until separate patient and organization actions occur.",
    json: retained.acceptance
  },
  approval: {
    title: "PatientApprovalRecord",
    contract: retained.approval.schema_version,
    standard: "CareTrust Core 0.1",
    evidence: "Executed local",
    boundary: "The authenticated patient approved the exact hash-bound draft. The client observes this record; the caregiver cannot self-approve it.",
    json: retained.approval
  },
  grant: {
    title: "DelegationGrant",
    contract: retained.grant.schema_version,
    standard: "CareTrust Core 0.1",
    evidence: "Executed local",
    boundary: "The grant is an input to app-specific policy, not a universal bearer credential. Every request still checks app audience, purpose, action, resource, period, and revocation.",
    json: retained.grant
  },
  session: {
    title: "Synthetic OIDC + PKCE session",
    contract: "caretrust.auth-harness.v1",
    standard: "OpenID Connect · OAuth 2.0 PKCE",
    evidence: "Executed local",
    boundary: "This retained harness imports an authenticated subject. It does not perform production identity proofing or establish caregiver authority.",
    json: retained.auth_harness
  },
  contract: {
    title: "Reference client integration contract",
    contract: "caretrust.reference-client.v1",
    standard: "OIDC · OAuth RAR · CareTrust Core 0.1",
    evidence: "Static reference implementation",
    boundary: "The reference client holds UI state only. Canonical identity links, approvals, claims, grants, reviews, decisions, receipts, and revocations remain hub records.",
    json: {
      client_id: "app:synthetic-caregiver-reference",
      product_status: "test_and_demo_only",
      authority_state_owner: "caretrust_hub",
      client_local_authority_state: false,
      authentication: {
        protocol: "openid_connect",
        flow: "authorization_code",
        pkce: "S256",
        imported_subject: "account:synthetic-leilani"
      },
      authorization: {
        protocol: "oauth_rich_authorization_requests",
        profile: "https://caretrust-hub.github.io/caretrust-spec/rar/care-data/v1",
        decision_mode: "fresh_per_request"
      },
      canonical_records_consumed: [
        "PatientInvite",
        "InviteAcceptance",
        "PatientApprovalRecord",
        "CareRelationshipClaim",
        "DelegationGrant",
        "UploadedCareDocument",
        "DelegationAuthorizationDecision",
        "DelegationRevocationRecord"
      ]
    }
  },
  upload: {
    title: "UploadedCareDocument",
    contract: retained.care_document.schema_version,
    standard: "CareTrust document intake contract",
    evidence: "Executed local",
    boundary: "The caregiver can upload a patient-provided copy. File checks and provenance are retained, but uploader identity does not establish document authorship, clinical accuracy, currentness, or legal authority.",
    json: retained.care_document
  },
  schedule: {
    title: "Scheduling request + decision",
    contract: retained.schedule_decision.decision.schema_version,
    standard: "OAuth RAR · CareTrust policy · FHIR/SMART mapping",
    evidence: "Executed local",
    boundary: "The scheduling application receives a permit for this exact action and purpose. The decision does not authorize billing, mental-health access, medication management, or a different app.",
    json: retained.schedule_decision
  },
  instructions: {
    title: "Visit-instructions request",
    contract: "caretrust.delegation-authorization-decision.v1",
    standard: "OAuth RAR · CareTrust policy",
    evidence: "Executed local",
    boundary: "A distinct application request is evaluated against the same grant but a different audience, resource, action, and purpose.",
    json: {
      request: {
        schema_version: "caretrust.delegation-authorization-request.v1",
        request_id: "delegation-request:synthetic-care-portal-001",
        delegate_ref: retained.grant.delegate_ref,
        patient_ref: retained.grant.patient_ref,
        audience: "app:synthetic-care-portal",
        purpose: "care_coordination",
        action: "view_visit_instructions",
        resource: "visit_instructions",
        grant_id: retained.grant.grant_id,
        synthetic: true
      },
      decision: {
        schema_version: "caretrust.delegation-authorization-decision.v1",
        decision_id: "delegation-decision:synthetic-care-portal-001",
        decision: "permit",
        reason_codes: ["POLICY_REQUIREMENTS_SATISFIED"],
        supporting_grant_ids: [retained.grant.grant_id],
        policy_version: "caretrust.delegation-authorization.v1",
        synthetic: true
      }
    }
  },
  medication: {
    title: "Medication-support denial",
    contract: "caretrust.delegation-authorization-decision.v1",
    standard: "OAuth RAR · CareTrust policy",
    evidence: "Executed local",
    boundary: "The requested action is outside the patient-approved grant and fails closed. AI never widens the scope.",
    json: {
      request: {
        schema_version: "caretrust.delegation-authorization-request.v1",
        request_id: "delegation-request:synthetic-medication-deny-001",
        delegate_ref: retained.grant.delegate_ref,
        patient_ref: retained.grant.patient_ref,
        audience: "app:synthetic-medication-support",
        purpose: "care_coordination",
        action: "manage_medications",
        resource: "medications",
        grant_id: retained.grant.grant_id,
        synthetic: true
      },
      decision: {
        schema_version: "caretrust.delegation-authorization-decision.v1",
        decision_id: "delegation-decision:synthetic-medication-deny-001",
        decision: "deny",
        reason_codes: ["ACTION_NOT_DELEGATED", "AUDIENCE_NOT_ALLOWED"],
        supporting_grant_ids: [],
        policy_version: "caretrust.delegation-authorization.v1",
        synthetic: true
      }
    }
  },
  revocation: {
    title: "Revocation + fresh denial",
    contract: "caretrust.delegation-revocation-record.v1",
    standard: "CareTrust Core 0.1 · deterministic policy",
    evidence: "Executed local",
    boundary: "The patient revocation is a hub event. The reference client discards its presentation state and requests a fresh decision; prior receipts remain in append-only history.",
    json: {
      revocation: {
        schema_version: "caretrust.delegation-revocation-record.v1",
        revocation_id: "delegation-revocation:synthetic-001",
        grant_id: retained.grant.grant_id,
        patient_ref: retained.grant.patient_ref,
        revoked_by_account_ref: retained.grant.patient_ref,
        revoked_at: "2026-07-30T10:05:00Z",
        historical_decisions_retained: true
      },
      fresh_decision: {
        schema_version: "caretrust.delegation-authorization-decision.v1",
        decision_id: "delegation-decision:synthetic-post-revocation-001",
        decision: "deny",
        reason_codes: ["GRANT_REVOKED"],
        supporting_grant_ids: [],
        policy_version: "caretrust.delegation-authorization.v1",
        synthetic: true
      }
    }
  }
};

function showScreen(id) {
  document.querySelectorAll(".phone-screen").forEach((screen) => {
    screen.hidden = screen.id !== id;
  });
}

function showRecord(key) {
  const record = records[key];
  inspectorKind.textContent = record.standard;
  inspectorTitle.textContent = record.title;
  inspectorMeta.innerHTML = [
    ["Contract", record.contract],
    ["Evidence status", record.evidence],
    ["Authority owner", "CareTrust hub"]
  ].map(([term, value]) => `<div><dt>${term}</dt><dd>${value}</dd></div>`).join("");
  inspectorBoundary.textContent = record.boundary;
  inspectorJson.textContent = JSON.stringify(record.json, null, 2);
  inspector.showModal();
}

function renderDecision(kind) {
  if (revoked) {
    latestDecision.className = "latest-decision deny";
    latestDecision.innerHTML = "<span>Fresh CareTrust policy decision</span><strong>DENY · GRANT_REVOKED</strong>";
    showRecord("revocation");
    return;
  }
  const permitted = kind !== "medication";
  latestDecision.className = `latest-decision ${permitted ? "permit" : "deny"}`;
  latestDecision.innerHTML = `<span>Fresh CareTrust policy decision</span><strong>${permitted ? "PERMIT · POLICY_REQUIREMENTS_SATISFIED" : "DENY · ACTION_NOT_DELEGATED"}</strong>`;
  showRecord(kind);
}

document.querySelector("#sign-in").addEventListener("click", () => {
  showScreen("screen-accept");
  showRecord("session");
});

document.querySelector("#accept-invite").addEventListener("click", () => {
  showScreen("screen-home");
  showRecord("approval");
});

document.querySelector("#upload-record").addEventListener("click", (event) => {
  event.currentTarget.querySelector("strong").textContent = "Synthetic discharge record uploaded";
  event.currentTarget.querySelector("small").textContent = "Hash + provenance retained · review still required";
  showRecord("upload");
});

document.querySelectorAll("[data-request]").forEach((button) => {
  button.addEventListener("click", () => renderDecision(button.dataset.request));
});

document.querySelector("#replay-revocation").addEventListener("click", (event) => {
  revoked = true;
  const grantState = document.querySelector("#grant-state");
  grantState.className = "status revoked";
  grantState.innerHTML = '<i aria-hidden="true"></i> Patient delegation revoked';
  latestDecision.className = "latest-decision deny";
  latestDecision.innerHTML = "<span>Fresh CareTrust policy decision</span><strong>DENY · GRANT_REVOKED</strong>";
  event.currentTarget.textContent = "Revocation replayed · history retained";
  event.currentTarget.disabled = true;
  showRecord("revocation");
});

document.querySelectorAll("[data-inspect]").forEach((button) => {
  button.addEventListener("click", () => showRecord(button.dataset.inspect));
});
document.querySelector("#open-session").addEventListener("click", () => showRecord("session"));
document.querySelector("#open-contract").addEventListener("click", () => showRecord("contract"));
document.querySelector("#close-inspector").addEventListener("click", () => inspector.close());
