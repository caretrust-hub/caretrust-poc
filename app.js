const scenario = document.querySelector("#scenario");
const reset = document.querySelector("#reset");
const reviewAction = document.querySelector("#review-action");
const requestAction = document.querySelector("#request-action");
const revokeAction = document.querySelector("#revoke-action");
const decision = document.querySelector("#decision");
const notice = document.querySelector("#notice");
const uncertainty = document.querySelector("#uncertainty");
const instruction = document.querySelector("#embedded-instruction");
const audit = document.querySelector("#audit-events");
const stepButtons = [...document.querySelectorAll("[data-step]")];

const scenarios = {
  clean: {
    name: "Leilani Kealoha",
    id: "HI-CNA-SYN-1001",
    start: "04/15/2024",
    end: "04/15/2028",
    normalizedEnd: "2028-04-15",
    source: "Prometric CNA Registry simulator",
    uncertainty: false,
    sourceResult: "match",
    injection: false
  },
  corrected: {
    name: "Noelani Aki",
    id: "HI-CNA-SYN-1007",
    start: "04/15/2024",
    end: "04/15/2828",
    normalizedEnd: "2828-04-15",
    correctedEnd: "2028-04-15",
    source: "Prometric CNA Registry simulator",
    uncertainty: false,
    correction: true,
    sourceResult: "match",
    injection: false
  },
  ambiguous: {
    name: "Malia Kanoa",
    id: "HI-CNA-SYN-1002",
    start: "03/04/2025 or 04/03/2025",
    end: "Unknown",
    normalizedEnd: "Not extracted",
    source: "Prometric CNA Registry simulator",
    uncertainty: true,
    sourceResult: "match",
    injection: false
  },
  mismatch: {
    name: "Kimo Nalu",
    id: "HI-CNA-SYN-MISMATCH",
    start: "02/12/2024",
    end: "02/12/2028",
    normalizedEnd: "2028-02-12",
    source: "Prometric CNA Registry simulator",
    uncertainty: false,
    sourceResult: "mismatch",
    injection: false
  },
  injection: {
    name: "Pua Kaleo",
    id: "HI-CNA-SYN-1009",
    start: "08/20/2024",
    end: "08/20/2028",
    normalizedEnd: "2028-08-20",
    source: "Prometric CNA Registry simulator",
    uncertainty: false,
    sourceResult: "match",
    injection: true
  }
};

function setStep(name) {
  stepButtons.forEach((button) => {
    if (button.dataset.step === name) {
      button.setAttribute("aria-current", "step");
    } else {
      button.removeAttribute("aria-current");
    }
  });
}

function setGate(id, status, detail) {
  const gate = document.querySelector(`#${id}`);
  gate.dataset.status = status;
  gate.querySelector(":scope > span").textContent = status === "pass" ? "✓" : status === "fail" ? "×" : "○";
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

function loadScenario() {
  const item = scenarios[scenario.value];
  document.querySelector("#doc-name").textContent = item.name;
  document.querySelector("#doc-id").textContent = item.id;
  document.querySelector("#doc-start").textContent = item.start;
  document.querySelector("#doc-end").textContent = item.end;
  document.querySelector("#doc-source").textContent = item.source;
  document.querySelector("#claim-name").textContent = item.name;
  document.querySelector("#claim-id").textContent = item.id;
  document.querySelector("#claim-end").textContent = item.normalizedEnd;
  uncertainty.hidden = !item.uncertainty;
  instruction.hidden = !item.injection;
  notice.textContent = item.injection
    ? "Embedded instructions were treated as untrusted document text. Output remains a draft."
    : item.correction
      ? "AI normalized the expiration year incorrectly. A human correction is required before activation."
    : item.uncertainty
      ? "AI found an unresolved ambiguity. Material uncertainty blocks activation until corrected."
      : "AI linked each value to synthetic source text. A human decision and source match are still required.";
  document.querySelector("#draft-state").className = "state warning";
  document.querySelector("#draft-state").textContent = "Draft · not verified";
  setGate("gate-schema", "pass", item.injection ? "Injection ignored; draft contract held" : "Draft-only contract");
  setGate(
    "gate-review",
    "pending",
    item.uncertainty || item.correction
      ? "Correction required"
      : "Explicit action required"
  );
  setGate("gate-source", "pending", "Synthetic simulator only");
  setGate("gate-policy", "pending", "Audience + purpose + status");
  reviewAction.disabled = false;
  reviewAction.textContent = item.uncertainty
    ? "Defer for better evidence"
    : item.correction
      ? "Correct date & check source"
      : "Approve & check source";
  requestAction.disabled = true;
  revokeAction.disabled = true;
  showDecision("pending", "Not evaluated", "Waiting for trust gates");
  setStep("draft");
  audit.innerHTML = `
    <li><time>Step 1</time><strong>Evidence received</strong><span>Synthetic artifact hash recorded</span></li>
    <li><time>Step 2</time><strong>AI extraction completed</strong><span>Output retained as an unverified draft</span></li>`;
}

reviewAction.addEventListener("click", () => {
  const item = scenarios[scenario.value];
  reviewAction.disabled = true;
  setStep("review");
  if (item.uncertainty) {
    setGate("gate-review", "fail", "REVIEW_DEFERRED");
    setGate("gate-source", "pending", "Not used to override uncertainty");
    showDecision("deny", "DENY", "REVIEW_DEFERRED · Better evidence required");
    addAudit("Step 3", "Human review deferred", "Ambiguous dates remain unresolved");
    return;
  }

  if (item.correction) {
    document.querySelector("#claim-end").textContent = item.correctedEnd;
    notice.textContent =
      `Human reviewer corrected expiration ${item.normalizedEnd} → ${item.correctedEnd}. ` +
      "The original AI draft remains preserved in the audit trail.";
    setGate("gate-review", "pass", "Authorized correction recorded");
    addAudit(
      "Step 3",
      "Human review corrected",
      `${item.normalizedEnd} → ${item.correctedEnd}; original draft preserved`
    );
  } else {
    setGate("gate-review", "pass", "Authorized reviewer approved");
    addAudit("Step 3", "Human review approved", "Original draft preserved");
  }
  setStep("source");
  if (item.sourceResult === "mismatch") {
    setGate("gate-source", "fail", "SOURCE_MISMATCH");
    showDecision("deny", "DENY", "SOURCE_MISMATCH · No claim created");
    addAudit("Step 4", "Source mismatch", "Activation failed closed");
    return;
  }

  setGate("gate-source", "pass", "Synthetic source match");
  document.querySelector("#draft-state").className = "state success";
  document.querySelector("#draft-state").textContent = "Active signed claim";
  requestAction.disabled = false;
  revokeAction.disabled = false;
  addAudit("Step 4", "Synthetic source matched", "Separate source record retained");
  addAudit("Step 5", "Active claim created", "Human + source gates satisfied");
  setStep("claim");
  showDecision("pending", "Ready for request", "Claim is active; local policy still decides");
});

requestAction.addEventListener("click", () => {
  setGate("gate-policy", "pass", "POLICY_REQUIREMENTS_SATISFIED");
  showDecision("permit", "PERMIT", "Active CNA claim · credentialing purpose");
  addAudit("Step 6", "Application request permitted", "Audience, purpose, status, and signature passed");
  setStep("decision");
});

revokeAction.addEventListener("click", () => {
  revokeAction.disabled = true;
  requestAction.disabled = true;
  setGate("gate-policy", "fail", "TOKEN_REVOKED");
  document.querySelector("#draft-state").className = "state warning";
  document.querySelector("#draft-state").textContent = "Revoked claim";
  showDecision("deny", "DENY", "TOKEN_REVOKED · Subsequent request blocked");
  addAudit("After Step 6", "Claim revoked", "Next application request denied");
  setStep("decision");
});

document.querySelectorAll(".evidence-link").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelector("#evidence-popover").textContent = `Supporting text — “${button.dataset.evidence}”`;
  });
});

stepButtons.forEach((button) => button.addEventListener("click", () => setStep(button.dataset.step)));
scenario.addEventListener("change", loadScenario);
reset.addEventListener("click", loadScenario);
loadScenario();
