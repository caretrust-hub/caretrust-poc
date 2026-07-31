const STORAGE_KEY = "caretrust.provider-session.v1";
const status = document.querySelector("#client-status");
const shiftCard = document.querySelector("#shift-card");
const emptyState = document.querySelector("#empty-state");

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[character]);
}

function renderDecision() {
  let session;
  try {
    session = JSON.parse(localStorage.getItem(STORAGE_KEY));
  } catch {
    session = null;
  }
  const app = session?.app_projections?.find((item) => item.app_id === "app:synthetic-field-client");
  if (!app || app.decision === "not_requested") {
    status.textContent = session?.stage === "revoked"
      ? "Assignment revoked. Ask CareTrust for a fresh decision in the organization console."
      : "No current CareTrust permit is available.";
    shiftCard.hidden = true;
    emptyState.hidden = false;
    return;
  }
  emptyState.hidden = true;
  shiftCard.hidden = false;
  if (app.decision === "deny") {
    status.textContent = "Fresh access request denied by CareTrust.";
    shiftCard.innerHTML = `
      <header><h2>No task disclosed</h2><span class="decision deny">DENY</span></header>
      <p>${escapeHtml(app.reason)}</p>
      <div class="receipt">decision=deny · audience=app:synthetic-field-client · disclosed_fields=0 · reason=ASSIGNMENT_REVOKED</div>`;
    return;
  }
  status.textContent = "Fresh CareTrust permit loaded from the shared synthetic case.";
  shiftCard.innerHTML = `
    <header><div><small>WED · APPROVED SHIFT</small><h2>${escapeHtml(app.data.care_recipient)}</h2></div><span class="decision allow">PERMIT</span></header>
    <p>${escapeHtml(app.data.visit_window)} · Assigned to ${escapeHtml(app.data.assigned_worker)}</p>
    <div class="task"><small>FIRST-VISIT PREPARATION</small><strong>${escapeHtml(app.data.first_visit_task)}</strong></div>
    <p><strong>Not received:</strong> ${escapeHtml(app.excluded.join(", "))}</p>
    <div class="receipt">aud=app:synthetic-field-client · purpose=direct-care-service-delivery · case=${escapeHtml(app.data.case_id)} · decision=permit · synthetic=true</div>`;
}

document.querySelector("#refresh-decision").addEventListener("click", renderDecision);
window.addEventListener("storage", renderDecision);
renderDecision();
