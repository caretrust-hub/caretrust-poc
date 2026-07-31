const API_ROOT = "./api/v1";
const STORAGE_KEY = "caretrust.provider-session.v1";

const stageOrder = [
  "intake",
  "review_draft",
  "patient_approval",
  "worker_assignment",
  "app_routing",
];

const stageCopy = {
  intake: {
    title: "Compile the referral",
    description: "AI can locate coordination facts and gaps. It cannot approve, assign, or grant app access.",
    badge: "New referral",
    queue: "New referral",
  },
  review_draft: {
    title: "Review one exception and one missing detail",
    description: "Confirm the cited draft and correct only what the source could not establish.",
    badge: "Coordinator review",
    queue: "1 exception · 1 follow-up",
  },
  patient_approval: {
    title: "Wait for Malia’s explicit sharing approval",
    description: "The coordinator has prepared the scope. The patient decides in a separate confirmation flow.",
    badge: "Patient action",
    queue: "Waiting for patient",
  },
  worker_assignment: {
    title: "Assign an eligible direct-care worker",
    description: "Deterministic gates narrow the roster. AI explains fit; a supervisor makes the assignment.",
    badge: "Supervisor action",
    queue: "Ready to assign",
  },
  app_routing: {
    title: "Route minimum data to each independent app",
    description: "Each fresh request is evaluated against the approved purpose, active assignment, and app policy.",
    badge: "App routing",
    queue: "Ready for apps",
  },
  active: {
    title: "Case is access-ready",
    description: "Both apps received different, purpose-limited projections. Fresh requests remain revocable.",
    badge: "Active",
    queue: "Active · no action",
  },
  revoked: {
    title: "Verify denial after revocation",
    description: "History remains, but every fresh app request must fail closed without disclosing case data.",
    badge: "Revoked",
    queue: "Revocation follow-up",
  },
};

const aiFacts = [
  ["patient.display_name", "Care recipient", "Malia K.", 0.99, "Malia K.", false],
  ["service.type", "Requested service", "In-home respite support", 0.97, "in-home respite support", false],
  ["service.start_date", "Requested start", "2026-08-05", 0.93, "beginning August 5, 2026", false],
  ["service.schedule", "Preferred schedule", "Wednesday afternoons", 0.74, "preferably Wednesday afternoons", true],
  ["service.area", "Service area", "East Honolulu", 0.98, "in East Honolulu", false],
  ["care_team.coordinator", "Family coordinator", "Leilani · daughter", 0.95, "Her daughter Leilani is helping coordinate", false],
  ["preferences.cultural", "Caregiver preference", "Local cultural knowledge preferred", 0.91, "a caregiver with local cultural knowledge is preferred", false],
  ["visit.preparation", "First-visit preparation", "Bring printed transition packet", 0.98, "bring the printed transition packet to the first visit", false],
].map(([field_path, label, proposed_value, confidence, quote, needs_review]) => ({
  field_path,
  label,
  proposed_value,
  confidence,
  quote,
  needs_review,
  source_ref: "referral:synthetic-transition-note",
  reviewed_value: null,
  reviewed_by: null,
}));

const workerCandidates = [
  {
    worker_id: "worker:synthetic-kai-n",
    display_name: "Kai N.",
    role: "Certified nurse aide",
    qualifications: ["Hawaiʻi CNA active (simulated)", "CPR current (simulated)"],
    availability: "Wednesday 1:00–5:00 PM",
    eligible: true,
    deterministic_checks: ["required role satisfied", "simulated registry status active", "requested window available", "service area covered"],
    ai_explanation: "Strongest reviewed fit because the requested window, service area, and cultural preference align. A supervisor still decides.",
  },
  {
    worker_id: "worker:synthetic-noa-p",
    display_name: "Noa P.",
    role: "Home care aide",
    qualifications: ["Home care aide profile (simulated)"],
    availability: "Wednesday 1:00–3:00 PM",
    eligible: false,
    deterministic_checks: ["required role not satisfied", "requested four-hour window not covered"],
    ai_explanation: "Potential relationship fit, but deterministic qualification and availability gates exclude this worker.",
  },
  {
    worker_id: "worker:synthetic-liko-r",
    display_name: "Liko R.",
    role: "Certified nurse aide",
    qualifications: ["Hawaiʻi CNA active (simulated)", "CPR current (simulated)"],
    availability: "Friday mornings",
    eligible: false,
    deterministic_checks: ["required role satisfied", "simulated registry status active", "requested window unavailable"],
    ai_explanation: "Qualified, but the authoritative availability check does not match the approved schedule.",
  },
];

function now() {
  return new Date().toISOString();
}

function event(actor_type, action, summary, stage) {
  return {
    event_id: `event:${crypto.randomUUID()}`,
    occurred_at: now(),
    actor_type,
    actor_ref: actor_type === "ai" ? "caretrust-intake-compiler" : `synthetic:${actor_type}`,
    action,
    summary,
    stage,
  };
}

function createBrowserSession() {
  const timestamp = now();
  return {
    session_id: `provider-session:${crypto.randomUUID()}`,
    version: 1,
    stage: "intake",
    case_id: "case:synthetic-malia-k",
    case_display: "Malia K. · respite support referral",
    organization: "Kūpuna Care Coordination Network (synthetic)",
    referral_source: "Synthetic hospital transition note",
    referral_text: "Malia K. needs in-home respite support beginning August 5, 2026, preferably Wednesday afternoons in East Honolulu. Her daughter Leilani is helping coordinate. English is spoken; a caregiver with local cultural knowledge is preferred. Please bring the printed transition packet to the first visit. The note does not state the visit end time or include Malia's approval to share.",
    facts: [],
    missing_items: [],
    patient_approval: "not_requested",
    patient_approval_scope: [],
    worker_candidates: [],
    assignment: null,
    app_projections: [
      { app_id: "app:synthetic-scheduler", app_name: "OpenShift Scheduler", purpose: "Schedule the approved respite visit", decision: "not_requested", reason: "Awaiting a fresh access request.", data: {}, excluded: [] },
      { app_id: "app:synthetic-field-client", app_name: "Care Tasks Mobile", purpose: "Show the assigned worker approved visit preparation", decision: "not_requested", reason: "Awaiting a fresh access request.", data: {}, excluded: [] },
    ],
    events: [event("system", "referral_received", "Synthetic referral entered the provider work queue.", "intake")],
    metrics: { source_fields_detected: 0, fields_prefilled: 0, fields_requiring_correction: 0, fields_corrected: 0, follow_up_items_open: 0, duplicate_app_entries_avoided: 0, app_packages_generated: 0, human_approvals_remaining: 3 },
    created_at: timestamp,
    updated_at: timestamp,
  };
}

class ApiBackend {
  async health() {
    const response = await fetch(`${API_ROOT}/health`, { headers: { Accept: "application/json" } });
    if (!response.ok || !(response.headers.get("content-type") || "").includes("application/json")) throw new Error("API unavailable");
    return response.json();
  }

  async create() {
    return this.request(`${API_ROOT}/provider-sessions`, {});
  }

  async command(session, command, fields = {}) {
    return this.request(`${API_ROOT}/provider-sessions/${session.session_id}/commands`, {
      command,
      expected_version: session.version,
      ...fields,
    });
  }

  async request(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
    const value = await response.json();
    if (!response.ok) throw new Error(value.detail || "Workflow request failed");
    return value;
  }
}

class BrowserReferenceBackend {
  async health() {
    return { status: "ok", mode: "browser-reference" };
  }

  async create() {
    return createBrowserSession();
  }

  async command(session, command, fields = {}) {
    const next = structuredClone(session);
    next.version += 1;
    next.updated_at = now();
    if (command === "compile_referral") {
      next.stage = "review_draft";
      next.facts = structuredClone(aiFacts);
      next.missing_items = [
        { item_id: "visit_end", label: "Confirm requested visit end time", resolution: null, resolved_by: null },
        { item_id: "patient_approval", label: "Obtain Malia's approval for the proposed sharing scope", resolution: null, resolved_by: null },
      ];
      Object.assign(next.metrics, { source_fields_detected: 8, fields_prefilled: 8, fields_requiring_correction: 1, follow_up_items_open: 2 });
      next.events.push(event("ai", "draft_compiled", "Proposed 8 cited fields and routed 2 exceptions to a person.", next.stage));
    } else if (command === "review_draft") {
      const corrections = fields.corrections || {};
      if (!fields.resolved_items?.visit_end) throw new Error("Confirm a visit end time before continuing.");
      next.stage = "patient_approval";
      next.patient_approval = "pending";
      next.facts = next.facts.map((fact) => ({ ...fact, reviewed_value: corrections[fact.field_path] || fact.proposed_value, reviewed_by: "user:demo-coordinator" }));
      next.missing_items[0] = { ...next.missing_items[0], resolution: fields.resolved_items.visit_end, resolved_by: "user:demo-coordinator" };
      next.metrics.fields_corrected = next.facts.filter((fact) => corrections[fact.field_path] && corrections[fact.field_path] !== fact.proposed_value).length;
      next.metrics.follow_up_items_open = 1;
      next.metrics.human_approvals_remaining = 2;
      next.events.push(event("human", "draft_reviewed", `Coordinator reviewed 8 fields, changed ${next.metrics.fields_corrected}, and requested patient approval.`, next.stage));
    } else if (command === "record_patient_approval") {
      if (!fields.approved) {
        next.patient_approval = "declined";
        next.events.push(event("patient", "sharing_declined", "Patient declined the proposed sharing scope.", next.stage));
      } else {
        next.stage = "worker_assignment";
        next.patient_approval = "approved";
        next.patient_approval_scope = ["coordinate-respite-visit", "share-schedule-with-assigned-worker", "share-approved-preparation-tasks"];
        next.worker_candidates = structuredClone(workerCandidates);
        next.missing_items[1] = { ...next.missing_items[1], resolution: "Approved in patient confirmation flow", resolved_by: "patient:synthetic-malia" };
        next.metrics.follow_up_items_open = 0;
        next.metrics.human_approvals_remaining = 1;
        next.events.push(event("patient", "sharing_approved", "Patient approved three bounded purposes; policy generated an eligible worker shortlist.", next.stage));
      }
    } else if (command === "assign_worker") {
      const candidate = next.worker_candidates.find((item) => item.worker_id === fields.worker_id);
      if (!candidate?.eligible) throw new Error("Worker failed deterministic eligibility checks.");
      next.stage = "app_routing";
      next.assignment = { worker_id: candidate.worker_id, worker_name: candidate.display_name, assigned_by: "user:demo-supervisor", assigned_at: now(), status: "active" };
      next.metrics.human_approvals_remaining = 0;
      next.events.push(event("human", "worker_assigned", `Supervisor assigned ${candidate.display_name}; AI explanation did not control eligibility or assignment.`, next.stage));
    } else if (command === "request_app_access") {
      const app = next.app_projections.find((item) => item.app_id === fields.app_id);
      if (!app) throw new Error("Unknown application.");
      if (next.stage === "revoked") {
        Object.assign(app, { decision: "deny", reason: "Fresh request denied: the assignment is revoked.", data: {}, decided_at: now() });
        next.events.push(event("policy", "app_access_denied", `${app.app_name} received deny after revocation.`, next.stage));
      } else {
        const fact = (path) => next.facts.find((item) => item.field_path === path)?.reviewed_value || next.facts.find((item) => item.field_path === path)?.proposed_value;
        const common = { case_id: next.case_id, care_recipient: fact("patient.display_name"), assigned_worker: next.assignment.worker_name };
        if (app.app_id === "app:synthetic-scheduler") {
          app.data = { ...common, service: fact("service.type"), start_date: fact("service.start_date"), visit_window: fact("service.schedule"), service_area: fact("service.area") };
          app.excluded = ["source document", "family relationship details", "clinical record", "credential evidence"];
        } else {
          app.data = { ...common, visit_window: fact("service.schedule"), first_visit_task: fact("visit.preparation") };
          app.excluded = ["source document", "family relationship details", "exact home address", "clinical record", "credential evidence"];
        }
        Object.assign(app, { decision: "allow", reason: "Allowed by approved purpose, active assignment, and app policy.", decided_at: now() });
        next.events.push(event("policy", "app_access_allowed", `${app.app_name} received ${Object.keys(app.data).length} purpose-limited fields; ${app.excluded.length} sensitive categories were excluded.`, next.stage));
        if (next.app_projections.every((item) => item.decision === "allow")) next.stage = "active";
      }
      next.metrics.app_packages_generated = next.app_projections.filter((item) => item.decision === "allow").length;
      next.metrics.duplicate_app_entries_avoided = next.app_projections.filter((item) => item.decision === "allow").reduce((sum, item) => sum + Object.keys(item.data).length, 0);
    } else if (command === "revoke_assignment") {
      next.stage = "revoked";
      next.assignment.status = "revoked";
      next.app_projections = next.app_projections.map((app) => ({ ...app, decision: "not_requested", reason: "Assignment revoked; a fresh request will be denied.", data: {}, decided_at: null }));
      next.metrics.app_packages_generated = 0;
      next.metrics.duplicate_app_entries_avoided = 0;
      next.events.push(event("human", "assignment_revoked", `Assignment revoked once for all apps: ${fields.reason}`, next.stage));
    } else {
      throw new Error(`Unknown command: ${command}`);
    }
    return next;
  }
}

let backend;
let session;

const workflowPanel = document.querySelector("#workflow-panel");
const messageInspector = document.querySelector("#message-inspector");
const alertRegion = document.querySelector("#alert-region");
const statusRegion = document.querySelector("#action-status");

async function initialize(reset = false) {
  setBusy(true);
  try {
    const api = new ApiBackend();
    try {
      await api.health();
      backend = api;
      document.querySelector("#backend-status").textContent = "Python API · local";
      document.querySelector("#backend-status").classList.add("connected");
    } catch {
      backend = new BrowserReferenceBackend();
      document.querySelector("#backend-status").textContent = "Browser reference adapter";
      document.querySelector("#backend-status").classList.add("connected");
    }
    if (!reset && backend instanceof BrowserReferenceBackend) {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) session = JSON.parse(stored);
    }
    if (!session || reset) session = await backend.create();
    persist();
    render();
    announce("Synthetic provider case ready.");
  } catch (error) {
    showError(error);
  } finally {
    setBusy(false);
  }
}

async function runCommand(command, fields = {}) {
  setBusy(true);
  clearError();
  try {
    session = await backend.command(session, command, fields);
    persist();
    render();
    messageInspector.textContent = JSON.stringify({ command, expected_version: session.version - 1, result: session.events.at(-1), metrics: session.metrics }, null, 2);
    announce(session.events.at(-1).summary);
  } catch (error) {
    showError(error);
  } finally {
    setBusy(false);
  }
}

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

function render() {
  const copy = stageCopy[session.stage];
  document.querySelector("#next-action-title").textContent = copy.title;
  document.querySelector("#next-action-description").textContent = copy.description;
  document.querySelector("#stage-badge").textContent = copy.badge;
  document.querySelector("#queue-stage").textContent = copy.queue;
  document.querySelector("#metric-prefilled").textContent = session.metrics.fields_prefilled;
  document.querySelector("#metric-exceptions").textContent = session.metrics.fields_requiring_correction;
  document.querySelector("#metric-followups").textContent = session.metrics.follow_up_items_open;
  document.querySelector("#metric-duplicates").textContent = session.metrics.duplicate_app_entries_avoided;
  document.querySelector("#metric-approvals").textContent = session.metrics.human_approvals_remaining;
  renderProgress();
  renderWorkflow();
  renderTeam();
  renderApplications();
  renderHistory();
}

function renderProgress() {
  const currentIndex = session.stage === "active" || session.stage === "revoked" ? stageOrder.length : stageOrder.indexOf(session.stage);
  document.querySelectorAll("#progress li").forEach((item, index) => {
    item.classList.toggle("complete", index < currentIndex);
    item.classList.toggle("current", index === currentIndex);
  });
}

function renderWorkflow() {
  if (session.stage === "intake") {
    workflowPanel.replaceChildren(document.querySelector("#intake-template").content.cloneNode(true));
    document.querySelector("#referral-text").textContent = session.referral_text;
    document.querySelector("#compile-action").addEventListener("click", () => runCommand("compile_referral"));
    return;
  }
  if (session.stage === "review_draft") {
    workflowPanel.innerHTML = reviewMarkup();
    workflowPanel.querySelectorAll("[data-evidence]").forEach((button) => button.addEventListener("click", () => {
      const fact = session.facts.find((item) => item.field_path === button.dataset.evidence);
      messageInspector.textContent = JSON.stringify({ type: "caretrust.evidence-binding.v0.1", field_path: fact.field_path, source_ref: fact.source_ref, exact_quote: fact.quote, confidence: fact.confidence, authority_effect: "none" }, null, 2);
      document.querySelector(".evidence-drawer").open = true;
    }));
    document.querySelector("#review-action").addEventListener("click", () => {
      const corrections = {};
      document.querySelectorAll("[data-fact-input]").forEach((input) => { corrections[input.dataset.factInput] = input.value.trim(); });
      runCommand("review_draft", { reviewer_ref: "user:demo-coordinator", corrections, resolved_items: { visit_end: document.querySelector("#visit-end").value.trim() } });
    });
    return;
  }
  if (session.stage === "patient_approval") {
    workflowPanel.innerHTML = approvalMarkup();
    document.querySelector("#patient-approve").addEventListener("click", () => runCommand("record_patient_approval", { patient_ref: "patient:synthetic-malia", approved: true }));
    document.querySelector("#patient-decline").addEventListener("click", () => runCommand("record_patient_approval", { patient_ref: "patient:synthetic-malia", approved: false }));
    return;
  }
  if (session.stage === "worker_assignment") {
    workflowPanel.innerHTML = assignmentMarkup();
    workflowPanel.querySelectorAll("[data-assign-worker]").forEach((button) => button.addEventListener("click", () => runCommand("assign_worker", { worker_id: button.dataset.assignWorker, supervisor_ref: "user:demo-supervisor" })));
    return;
  }
  workflowPanel.innerHTML = routingMarkup();
  bindAppActions(workflowPanel);
}

function reviewMarkup() {
  const facts = session.facts.map((fact) => `
    <div class="fact-row ${fact.needs_review ? "needs-review" : ""}">
      <label for="fact-${cssSafe(fact.field_path)}">${escapeHtml(fact.label)}${fact.needs_review ? " · example correction" : ""}</label>
      <input id="fact-${cssSafe(fact.field_path)}" data-fact-input="${escapeHtml(fact.field_path)}" value="${escapeHtml(fact.needs_review && fact.field_path === "service.schedule" ? "Wednesdays, 1:00–5:00 PM" : fact.proposed_value)}">
      <span class="confidence">${Math.round(fact.confidence * 100)}% <button class="evidence-button" type="button" data-evidence="${escapeHtml(fact.field_path)}">source</button></span>
    </div>`).join("");
  return `
    <div class="review-layout">
      <article class="card">
        <div class="card-heading"><div><p class="eyebrow">8 fields prefilled</p><h3>Review the cited intake draft</h3></div><span class="file-pill">AI draft · not authority</span></div>
        <div class="ai-proof-strip" role="note">
          <strong>What AI contributes</strong>
          <span>ordinary-language referral → eight structured candidates + exact source quotes + two focused exceptions</span>
          <small>This screen is the deterministic reference workflow. Separate retained AWS evidence: 40/40 schema-valid, 22 accepted semantically exact drafts, 18 safe fallbacks, 40/40 correct human-review routing, and zero authority effects.</small>
        </div>
        <div class="fact-list">${facts}</div>
        <div class="review-footer"><p>Green fields were copied with strong evidence. Amber needs judgment.</p><button id="review-action" class="primary-action" type="button">Complete coordinator review →</button></div>
      </article>
      <aside class="card">
        <p class="eyebrow">Exception queue</p><h3>Ask only what is missing</h3>
        <div class="exception-list">
          <div class="exception"><label for="visit-end">Confirm requested visit end time</label><input id="visit-end" value="5:00 PM" required></div>
          <div class="exception"><strong>Patient approval</strong><p>Not in the referral. CareTrust will create a separate patient confirmation, not infer consent.</p></div>
        </div>
        <blockquote class="evidence-quote">“The note does not state the visit end time or include Malia’s approval to share.”</blockquote>
      </aside>
    </div>`;
}

function approvalMarkup() {
  return `
    <div class="approval-shell">
      <article class="card">
        <p class="eyebrow">Coordinator work complete</p><h3>Proposed sharing scope</h3>
        <p>The staff member has reviewed the referral. This is still not consent.</p>
        <ul class="scope-list">
          <li>Coordinate one in-home respite service</li>
          <li>Share the approved schedule with the assigned worker</li>
          <li>Share first-visit preparation with the worker task app</li>
        </ul>
        <div class="not-shared"><strong>Never included:</strong> source document, clinical record, credential evidence, billing, mental-health information, or unrelated case history.</div>
      </article>
      <article class="card patient-preview">
        <p class="eyebrow">Separate patient-facing gate · simulated</p>
        <div class="phone">
          <small>CareTrust confirmation</small><h4>Malia, share this plan?</h4>
          <p>Your care organization wants to schedule respite support with an assigned, qualified worker. You can change or stop future sharing.</p>
          <button id="patient-approve" class="primary-action" type="button">Approve this scope</button>
          <button id="patient-decline" class="text-button" type="button">Not now</button>
        </div>
      </article>
    </div>`;
}

function assignmentMarkup() {
  const candidates = session.worker_candidates.map((worker) => `
    <article class="candidate ${worker.eligible ? "eligible" : ""}">
      <div>
        <span class="eligibility">${worker.eligible ? "Eligible" : "Not eligible"}</span>
        <h4>${escapeHtml(worker.display_name)} · ${escapeHtml(worker.role)}</h4>
        <p>${escapeHtml(worker.availability)} · ${escapeHtml(worker.qualifications.join(" · "))}</p>
        <div class="checks">${worker.deterministic_checks.map((check) => `<span>${escapeHtml(check)}</span>`).join("")}</div>
        <p><strong>AI explanation:</strong> ${escapeHtml(worker.ai_explanation)}</p>
      </div>
      <button class="${worker.eligible ? "primary-action" : "secondary-action"}" type="button" data-assign-worker="${escapeHtml(worker.worker_id)}" ${worker.eligible ? "" : "disabled"}>${worker.eligible ? "Assign worker" : "Blocked"}</button>
    </article>`).join("");
  return `
    <article class="card">
      <div class="card-heading"><div><p class="eyebrow">Workforce activation</p><h3>Choose from the policy-filtered roster</h3></div><span class="file-pill">Human assignment required</span></div>
      <p>Eligibility uses reviewed credentials, active status, service requirements, area, and availability. The model may explain the fit but cannot change a failed gate.</p>
      <div class="candidate-list">${candidates}</div>
    </article>`;
}

function routingMarkup() {
  const complete = session.stage === "active";
  const revoked = session.stage === "revoked";
  return `
    <div class="section-heading"><div><p class="eyebrow">${revoked ? "Fail-closed proof" : "App routing"}</p><h3>${revoked ? "Request again after revocation" : complete ? "Two apps are ready" : "Generate each minimum-data package"}</h3></div><p>${revoked ? "Use either fresh-request button to prove no case fields are released." : "This replaces repeated app-by-app setup. It does not make CareTrust a scheduler or task manager."}</p></div>
    <div class="application-grid">${session.app_projections.map(appMarkup).join("")}</div>
    ${complete ? `<div class="review-footer"><p>Earlier permit receipts remain historical after revocation; existing-session termination is not claimed.</p><button id="revoke-action" class="danger-action" type="button">Revoke assignment across apps</button></div>` : ""}`;
}

function appMarkup(app) {
  const rows = Object.entries(app.data || {}).map(([key, value]) => `<tr><th>${escapeHtml(key.replaceAll("_", " "))}</th><td>${escapeHtml(String(value))}</td></tr>`).join("");
  return `
    <article class="app-card">
      <header><div><p class="eyebrow">Independent test consumer</p><h4>${escapeHtml(app.app_name)}</h4></div><span class="decision ${app.decision}">${escapeHtml(app.decision.replaceAll("_", " "))}</span></header>
      <p>${escapeHtml(app.purpose)}</p>
      ${rows ? `<table class="projection"><tbody>${rows}</tbody></table>` : `<p class="excluded">${escapeHtml(app.reason)}</p>`}
      ${app.excluded?.length ? `<p class="excluded"><strong>Excluded:</strong> ${escapeHtml(app.excluded.join(", "))}</p>` : ""}
      <div class="app-actions">
        <button class="secondary-action" type="button" data-app-request="${escapeHtml(app.app_id)}">${session.stage === "revoked" ? "Make fresh request" : app.decision === "allow" ? "Refresh decision" : "Request access"}</button>
        <button class="text-button" type="button" data-inspect-app="${escapeHtml(app.app_id)}">Inspect message</button>
      </div>
    </article>`;
}

function bindAppActions(root) {
  root.querySelectorAll("[data-app-request]").forEach((button) => button.addEventListener("click", () => runCommand("request_app_access", { app_id: button.dataset.appRequest })));
  root.querySelectorAll("[data-inspect-app]").forEach((button) => button.addEventListener("click", () => {
    const app = session.app_projections.find((item) => item.app_id === button.dataset.inspectApp);
    messageInspector.textContent = JSON.stringify({ type: "caretrust.authorization-decision.v0.1", subject: session.assignment?.worker_id, audience: app.app_id, purpose: app.purpose, decision: app.decision, disclosed: app.data, excluded: app.excluded, reason: app.reason }, null, 2);
    document.querySelector(".evidence-drawer").open = true;
  }));
  root.querySelector("#revoke-action")?.addEventListener("click", () => runCommand("revoke_assignment", { actor_ref: "user:demo-supervisor", reason: "Worker removed from this service assignment" }));
}

function renderApplications() {
  const root = document.querySelector("#application-grid");
  root.innerHTML = session.app_projections.map(appMarkup).join("");
  bindAppActions(root);
}

function renderTeam() {
  const assignmentStatus = session.assignment ? `${session.assignment.status} assignment` : "not assigned";
  const approval = session.patient_approval;
  document.querySelector("#team-grid").innerHTML = `
    <article class="team-card"><header><div><p class="eyebrow">Care recipient</p><h4>Malia K.</h4></div><span class="decision ${approval === "approved" ? "allow" : ""}">${escapeHtml(approval.replaceAll("_", " "))}</span></header><p>Controls the patient sharing scope in this synthetic flow.</p><ul class="authority-list"><li><strong>Relationship:</strong> self</li><li><strong>Authority:</strong> patient approval record</li><li><strong>Apps:</strong> purpose-limited projections only</li></ul></article>
    <article class="team-card"><header><div><p class="eyebrow">Family coordinator</p><h4>Leilani · daughter</h4></div><span class="decision">relationship only</span></header><p>Named in the referral as helping coordinate. That fact alone creates no permission.</p><ul class="authority-list"><li><strong>Relationship:</strong> asserted daughter</li><li><strong>Delegation:</strong> not established in this workforce flow</li><li><strong>App access:</strong> none</li></ul></article>
    <article class="team-card"><header><div><p class="eyebrow">Direct-care worker</p><h4>${escapeHtml(session.assignment?.worker_name || "Not assigned")}</h4></div><span class="decision ${session.assignment?.status === "active" ? "allow" : session.assignment?.status === "revoked" ? "deny" : ""}">${escapeHtml(assignmentStatus)}</span></header><p>Workforce relationship is separate from patient approval and application access.</p><ul class="authority-list"><li><strong>Qualification:</strong> reviewed simulated evidence</li><li><strong>Assignment:</strong> supervisor-controlled</li><li><strong>Access:</strong> re-evaluated for each app and purpose</li></ul></article>
    <article class="team-card"><header><div><p class="eyebrow">Community respite worker</p><h4>Pua · future pathway</h4></div><span class="decision">not assigned</span></header><p>Illustrates that a second caregiver can have a distinct role, validity window, and app scope without inheriting the CNA’s access.</p><ul class="authority-list"><li><strong>Relationship:</strong> program participant</li><li><strong>Assignment:</strong> none for this case</li><li><strong>App access:</strong> none</li></ul></article>`;
}

function renderHistory() {
  document.querySelector("#case-history").innerHTML = [...session.events].reverse().map((item) => `
    <li><time>${new Date(item.occurred_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</time><span class="actor-pill">${escapeHtml(item.actor_type)}</span><strong>${escapeHtml(item.action.replaceAll("_", " "))}</strong><p>${escapeHtml(item.summary)}</p></li>`).join("");
}

function setBusy(busy) {
  document.body.setAttribute("aria-busy", String(busy));
  document.querySelectorAll("button").forEach((button) => {
    if (busy) {
      button.dataset.wasDisabled = String(button.disabled);
      button.disabled = true;
    } else if (button.dataset.wasDisabled !== undefined) {
      button.disabled = button.dataset.wasDisabled === "true";
      delete button.dataset.wasDisabled;
    }
  });
}

function announce(message) {
  statusRegion.textContent = message;
}

function showError(error) {
  alertRegion.textContent = error instanceof Error ? error.message : String(error);
  alertRegion.classList.remove("hidden");
  announce(alertRegion.textContent);
}

function clearError() {
  alertRegion.classList.add("hidden");
  alertRegion.textContent = "";
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[character]);
}

function cssSafe(value) {
  return value.replaceAll(".", "-");
}

document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((item) => {
    const selected = item === tab;
    item.classList.toggle("active", selected);
    item.setAttribute("aria-selected", String(selected));
  });
  document.querySelectorAll("[data-view-panel]").forEach((panel) => {
    const selected = panel.dataset.viewPanel === tab.dataset.view;
    panel.classList.toggle("active", selected);
    panel.hidden = !selected;
  });
}));

document.querySelector("#new-demo").addEventListener("click", () => {
  session = null;
  localStorage.removeItem(STORAGE_KEY);
  initialize(true);
});

document.querySelector("#case-search").addEventListener("input", (event) => {
  const query = event.target.value.toLowerCase();
  document.querySelectorAll("#case-list li").forEach((item) => {
    item.hidden = !item.textContent.toLowerCase().includes(query);
  });
});

document.querySelectorAll(".case-row:not(.selected)").forEach((row) => row.addEventListener("click", () => {
  showError(`${row.querySelector("strong").textContent} is an illustrative queue row. Malia’s synthetic workflow is the executable case.`);
}));

document.querySelectorAll("[data-open-dialog]").forEach((button) => button.addEventListener("click", () => document.querySelector(`#${button.dataset.openDialog}`).showModal()));

initialize();
