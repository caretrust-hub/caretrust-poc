const scenario = document.querySelector("#scenario");
const reset = document.querySelector("#reset");
const reviewAction = document.querySelector("#review-action");
const sourceAction = document.querySelector("#source-action");
const claimAction = document.querySelector("#claim-action");
const appAAction = document.querySelector("#app-a-action");
const appBAction = document.querySelector("#app-b-action");
const revokeAction = document.querySelector("#revoke-action");
const decision = document.querySelector("#decision");
const notice = document.querySelector("#notice");
const uncertainty = document.querySelector("#uncertainty");
const instruction = document.querySelector("#embedded-instruction");
const audit = document.querySelector("#audit-events");
const evidencePopover = document.querySelector("#evidence-popover");
const evidenceButtons = [...document.querySelectorAll(".evidence-link")];
const stepIndicators = [...document.querySelectorAll(".steps [data-step]")];
const reuseState = document.querySelector("#reuse-state");
const appAReceipt = document.querySelector("#app-a-receipt");
const appBReceipt = document.querySelector("#app-b-receipt");

let workflow = {};

const scenarios = {
  clean: {
    name: "Leilani Kealoha",
    id: "HI-CNA-SYN-1001",
    start: "04/15/2024",
    end: "04/15/2028",
    normalizedEnd: "2028-04-15",
    ocrNameConfidence: "99.4%",
    ocrEndConfidence: "98.7%",
    sourceResult: "match"
  },
  corrected: {
    name: "Noelani Aki",
    id: "HI-CNA-SYN-1007",
    start: "04/15/2024",
    end: "04/15/2828",
    normalizedEnd: "2828-04-15",
    correctedEnd: "2028-04-15",
    ocrNameConfidence: "99.0%",
    ocrEndConfidence: "74.1%",
    correction: true,
    sourceResult: "match"
  },
  ambiguous: {
    name: "Malia Kanoa",
    id: "HI-CNA-SYN-1002",
    start: "03/04/2025 or 04/03/2025",
    end: "Unknown",
    normalizedEnd: "Not extracted",
    ocrNameConfidence: "98.8%",
    ocrEndConfidence: "61.2%",
    uncertainty: true,
    sourceResult: "match"
  },
  mismatch: {
    name: "Kimo Nalu",
    id: "HI-CNA-SYN-MISMATCH",
    start: "02/12/2024",
    end: "02/12/2028",
    normalizedEnd: "2028-02-12",
    ocrNameConfidence: "99.3%",
    ocrEndConfidence: "98.5%",
    sourceResult: "mismatch"
  },
  injection: {
    name: "Pua Kaleo",
    id: "HI-CNA-SYN-1009",
    start: "08/20/2024",
    end: "08/20/2028",
    normalizedEnd: "2028-08-20",
    ocrNameConfidence: "99.1%",
    ocrEndConfidence: "98.9%",
    sourceResult: "match",
    injection: true
  }
};

function setStep(name) {
  stepIndicators.forEach((indicator) => {
    if (indicator.dataset.step === name) {
      indicator.setAttribute("aria-current", "step");
    } else {
      indicator.removeAttribute("aria-current");
    }
  });
}

function setGate(id, status, detail) {
  const gate = document.querySelector(`#${id}`);
  gate.dataset.status = status;
  gate.querySelector(":scope > span").textContent =
    status === "pass" ? "✓" : status === "fail" ? "×" : "○";
  if (detail) gate.querySelector("small").textContent = detail;
}

function addAudit(step, title, detail) {
  const item = document.createElement("li");
  const time = document.createElement("time");
  const strong = document.createElement("strong");
  const span = document.createElement("span");
  time.textContent = step;
  strong.textContent = title;
  span.textContent = detail;
  item.append(time, strong, span);
  audit.append(item);
}

function showDecision(kind, title, detail) {
  decision.className = `decision ${kind}`;
  decision.querySelector("strong").textContent = title;
  decision.querySelector("small").textContent = detail;
}

function claimIdFor(item) {
  return `urn:caretrust:claim:${item.id.toLowerCase()}:v1`;
}

function setReceipt(element, kind, title, detail) {
  element.className = `policy-receipt ${kind}`;
  element.querySelector("strong").textContent = title;
  element.querySelector("small").textContent = detail;
}

function updateEvidence(item) {
  const evidence = {
    name: `“${item.name.toUpperCase()}” · ${item.ocrNameConfidence} confidence`,
    id: `“${item.id}” · 99.2% confidence`,
    credential: "“CERTIFIED NURSE AIDE” · 99.0% confidence",
    jurisdiction: "“HAWAII” · 99.6% confidence",
    expiration: `“${item.end}” · ${item.ocrEndConfidence} confidence`
  };
  evidenceButtons.forEach((button) => {
    button.dataset.evidence = evidence[button.dataset.evidenceField];
  });
  evidencePopover.textContent =
    "Select “View OCR evidence” to reveal the retained supporting line and confidence.";
}

function loadScenario() {
  const item = scenarios[scenario.value];
  workflow = {
    humanReviewed: false,
    sourceChecked: false,
    signed: false,
    appAPermit: false,
    appBPermit: false,
    revoked: false,
    freshBRequested: false
  };

  document.querySelector(".case-title strong").textContent = item.name;
  document.querySelector("#doc-name").textContent = item.name;
  document.querySelector("#doc-id").textContent = item.id;
  document.querySelector("#doc-start").textContent = item.start;
  document.querySelector("#doc-end").textContent = item.end;
  document.querySelector("#ocr-name").textContent = item.name.toUpperCase();
  document.querySelector("#ocr-id").textContent = item.id;
  document.querySelector("#ocr-end").textContent = item.end;
  document.querySelector("#ocr-name-confidence").textContent = item.ocrNameConfidence;
  document.querySelector("#ocr-name-meter").value = Number.parseFloat(item.ocrNameConfidence);
  document.querySelector("#ocr-end-confidence").textContent = item.ocrEndConfidence;
  document.querySelector("#ocr-end-meter").value = Number.parseFloat(item.ocrEndConfidence);
  document.querySelector("#claim-name").textContent = item.name;
  document.querySelector("#claim-registry-id").textContent = item.id;
  document.querySelector("#claim-end").textContent = item.normalizedEnd;
  document.querySelector("#stable-claim-id").textContent = claimIdFor(item);
  document.querySelector("#shared-claim-status").textContent = "DRAFT";

  updateEvidence(item);
  uncertainty.hidden = !item.uncertainty;
  instruction.hidden = !item.injection;
  notice.textContent = item.injection
    ? "Embedded instructions were retained as untrusted OCR text and ignored. The structured output remains an unverified draft."
    : item.correction
      ? "Retained model output normalized the expiration year incorrectly. A human correction is required."
      : item.uncertainty
        ? "Retained model output contains material date uncertainty. Human review must defer rather than guess."
        : "Retained model output linked each value to retained OCR evidence. Human review and a separate source check are still required.";

  document.querySelector("#draft-state").className = "state warning";
  document.querySelector("#draft-state").textContent = "Draft · not verified";
  setGate("gate-schema", "pass", item.injection ? "Injection ignored; schema held" : "20/20 schema-valid");
  setGate("gate-review", "pending", item.uncertainty || item.correction ? "Human judgment required" : "Explicit action required");
  setGate("gate-source", "pending", "Separate synthetic check");
  setGate("gate-signature", "pending", "Not created");

  reviewAction.disabled = false;
  reviewAction.textContent = item.uncertainty
    ? "1 · Defer human review"
    : item.correction
      ? "1 · Correct & approve review"
      : "1 · Approve human review";
  sourceAction.disabled = true;
  sourceAction.textContent = "2 · Run synthetic source check";
  claimAction.disabled = true;
  appAAction.disabled = true;
  appBAction.disabled = true;
  appBAction.textContent = "Request App B decision";
  revokeAction.disabled = true;
  reuseState.className = "reuse-state locked";
  reuseState.innerHTML = '<span aria-hidden="true">●</span> Create the signed claim to unlock requests';
  document.querySelector("#revocation-note").textContent =
    "Request both application decisions to enable the revocation demonstration.";
  setReceipt(appAReceipt, "pending", "NOT EVALUATED", "Waiting for an active signed claim");
  setReceipt(appBReceipt, "pending", "NOT EVALUATED", "Waiting for an active signed claim");
  showDecision("pending", "Draft only", "No verified claim exists");
  setStep("draft");
  audit.innerHTML = `
    <li><time>Step 1</time><strong>Synthetic evidence loaded</strong><span>Input hash linked to retained OCR result</span></li>
    <li><time>Step 2</time><strong>Retained OCR replayed</strong><span>Text, confidence, and location preserved</span></li>
    <li><time>Step 3</time><strong>Retained AI draft replayed</strong><span>Unverified output linked to OCR evidence</span></li>`;
}

reviewAction.addEventListener("click", () => {
  const item = scenarios[scenario.value];
  reviewAction.disabled = true;
  setStep("review");

  if (item.uncertainty) {
    setGate("gate-review", "fail", "REVIEW_DEFERRED");
    showDecision("deny", "DEFERRED", "REVIEW_DEFERRED · Better evidence required");
    addAudit("Step 4", "Human review deferred", "Ambiguous dates remain unresolved; no source check started");
    return;
  }

  workflow.humanReviewed = true;
  if (item.correction) {
    document.querySelector("#claim-end").textContent = item.correctedEnd;
    notice.textContent =
      `Human reviewer corrected ${item.normalizedEnd} → ${item.correctedEnd}. ` +
      "The retained model output remains preserved in the audit trail.";
    setGate("gate-review", "pass", "Correction recorded");
    addAudit("Step 4", "Human correction approved", `${item.normalizedEnd} → ${item.correctedEnd}; original retained`);
  } else {
    setGate("gate-review", "pass", "Authorized reviewer approved");
    addAudit("Step 4", "Human review approved", "This action did not run a source check");
  }
  sourceAction.disabled = false;
  showDecision("pending", "Human reviewed", "Synthetic source check has not run");
});

sourceAction.addEventListener("click", () => {
  if (!workflow.humanReviewed || workflow.sourceChecked) return;
  const item = scenarios[scenario.value];
  workflow.sourceChecked = true;
  sourceAction.disabled = true;
  setStep("source");

  if (item.sourceResult === "mismatch") {
    setGate("gate-source", "fail", "SOURCE_MISMATCH");
    showDecision("deny", "BLOCKED", "SOURCE_MISMATCH · No signed claim can be created");
    addAudit("Step 5", "Synthetic source mismatch", "Source gate failed closed; signing remains unavailable");
    return;
  }

  setGate("gate-source", "pass", "Synthetic match retained");
  claimAction.disabled = false;
  showDecision("pending", "Source matched", "No signed claim exists until the next explicit action");
  addAudit("Step 5", "Synthetic source matched", "This action did not create or sign a claim");
});

claimAction.addEventListener("click", () => {
  if (!workflow.humanReviewed || !workflow.sourceChecked || workflow.signed) return;
  const item = scenarios[scenario.value];
  workflow.signed = true;
  claimAction.disabled = true;
  setGate("gate-signature", "pass", "EdDSA prototype seam");
  document.querySelector("#draft-state").className = "state success";
  document.querySelector("#draft-state").textContent = "Active signed claim";
  document.querySelector("#shared-claim-status").textContent = "ACTIVE";
  appAAction.disabled = false;
  appBAction.disabled = false;
  reuseState.className = "reuse-state ready";
  reuseState.innerHTML = '<span aria-hidden="true">●</span> Active claim ready for local policy evaluation';
  showDecision("permit", "Active signed claim", "Applications must still make independent decisions");
  setStep("claim");
  addAudit("Step 6", "Signed claim created", `${claimIdFor(item)} · human and source receipts linked`);
});

appAAction.addEventListener("click", () => {
  if (!workflow.signed || workflow.revoked || workflow.appAPermit) return;
  const item = scenarios[scenario.value];
  workflow.appAPermit = true;
  appAAction.disabled = true;
  setReceipt(
    appAReceipt,
    "permit",
    "PERMIT",
    `${claimIdFor(item)} · audience onboarding · purpose workforce-onboarding · HI-CNA-ACTIVE-v1`
  );
  addAudit("App A", "Workforce onboarding permitted", "Independent local policy receipt: POLICY_REQUIREMENTS_SATISFIED");
  setStep("decision");
  updateRevocationAvailability();
});

appBAction.addEventListener("click", () => {
  const item = scenarios[scenario.value];
  if (!workflow.signed) return;

  if (workflow.revoked) {
    workflow.freshBRequested = true;
    appBAction.disabled = true;
    setReceipt(
      appBReceipt,
      "deny",
      "DENY / TOKEN_REVOKED",
      `${claimIdFor(item)} · fresh request denied before local scheduling policy could permit`
    );
    document.querySelector("#revocation-note").textContent =
      "Fresh App B request denied. Earlier permit receipts remain historical; no existing-session termination is claimed.";
    addAudit("Fresh App B request", "Scheduling denied", "TOKEN_REVOKED · status checked before policy permit");
    setStep("decision");
    return;
  }

  if (workflow.appBPermit) return;
  workflow.appBPermit = true;
  appBAction.disabled = true;
  setReceipt(
    appBReceipt,
    "permit",
    "PERMIT",
    `${claimIdFor(item)} · audience scheduling · purpose shift-assignment · SHIFT-CNA-ELIGIBLE-v2`
  );
  addAudit("App B", "Scheduling permitted", "Independent local policy receipt: POLICY_REQUIREMENTS_SATISFIED");
  setStep("decision");
  updateRevocationAvailability();
});

function updateRevocationAvailability() {
  if (workflow.appAPermit && workflow.appBPermit && !workflow.revoked) {
    revokeAction.disabled = false;
    document.querySelector("#revocation-note").textContent =
      "Both independent permits are recorded. Revoke the shared claim, then make a fresh App B request.";
  }
}

revokeAction.addEventListener("click", () => {
  if (!workflow.appAPermit || !workflow.appBPermit || workflow.revoked) return;
  workflow.revoked = true;
  revokeAction.disabled = true;
  appBAction.disabled = false;
  appBAction.textContent = "Make fresh App B request";
  document.querySelector("#draft-state").className = "state warning";
  document.querySelector("#draft-state").textContent = "Revoked claim";
  document.querySelector("#shared-claim-status").textContent = "REVOKED";
  reuseState.className = "reuse-state locked";
  reuseState.innerHTML = '<span aria-hidden="true">●</span> Revoked · fresh requests must check status';
  document.querySelector("#revocation-note").textContent =
    "Claim revoked. Make a fresh App B request to observe DENY / TOKEN_REVOKED.";
  showDecision("deny", "Claim revoked", "No new application decision has been evaluated yet");
  addAudit("After both permits", "Claim revoked", "Status changed; existing receipts remain historical");
  setStep("claim");
});

evidenceButtons.forEach((button) => {
  button.addEventListener("click", () => {
    evidencePopover.textContent = `Retained Textract line: ${button.dataset.evidence}`;
  });
});

scenario.addEventListener("change", loadScenario);
reset.addEventListener("click", loadScenario);
loadScenario();
