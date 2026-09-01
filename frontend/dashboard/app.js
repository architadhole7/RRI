// ============================================================
// RevenueGuard — Multi-Page Operations Controller
// Hash-based client-side routing over FastAPI StaticFiles
// ============================================================

"use strict";

// ── App State ─────────────────────────────────────────────────
let currentFilter       = "ALL";
let currentSearchQuery  = "";
let cachedSummary       = null;
let currentApprovals    = [];  // live approval queue

// ── Page Routing ──────────────────────────────────────────────

const PAGES = ["overview", "transactions", "approvals", "safety", "audit", "simulator"];

/**
 * Navigate to a page by name. Updates hash, sidebar, and loads page data.
 */
function navigate(pageName) {
  if (!PAGES.includes(pageName)) pageName = "overview";

  // Update hash without triggering hashchange listener loop
  if (window.location.hash !== "#" + pageName) {
    history.pushState(null, "", "#" + pageName);
  }

  // Hide all pages, show target
  PAGES.forEach(p => {
    const el = document.getElementById("page-" + p);
    if (el) el.classList.toggle("hidden", p !== pageName);
  });

  // Update sidebar active state
  PAGES.forEach(p => {
    const nav = document.getElementById("nav-" + p);
    if (nav) {
      nav.classList.toggle("active", p === pageName);
      nav.setAttribute("aria-current", p === pageName ? "page" : "false");
    }
  });

  // Load page-specific data
  switch (pageName) {
    case "overview":     initOverviewPage();     break;
    case "transactions": initTransactionsPage(); break;
    case "approvals":    initApprovalsPage();    break;
    case "safety":       initSafetyPage();       break;
    case "audit":        initAuditPage();        break;
    case "simulator":    /* no auto-load */      break;
  }

  // On mobile, close sidebar after navigation
  closeMobileSidebar();
}

/**
 * Resolve hash on initial load and listen for back/forward navigation.
 */
function initRouter() {
  window.addEventListener("popstate", () => {
    const hash = (window.location.hash || "#overview").replace("#", "");
    navigate(hash);
  });

  const initial = (window.location.hash || "#overview").replace("#", "");
  navigate(initial);
}

// ── Global Init ───────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  fetchSystemStatus();
  initRouter();
});

// ── System Status ─────────────────────────────────────────────

async function fetchSystemStatus() {
  try {
    const res = await fetch("/system/status");
    if (!res.ok) return;
    const data = await res.json();

    if (data.operator && data.operator.name) {
      const el = document.getElementById("operatorNameDisplay");
      if (el) el.innerText = data.operator.name;
    }
    if (data.safety) {
      updateKillSwitchUI(data.safety.kill_switch_active);
    }
  } catch {
    // Silently handle unavailable backend on load
  }
}

// ── Sidebar Toggle ────────────────────────────────────────────

function toggleSidebar() {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;
  if (window.innerWidth <= 768) {
    sidebar.classList.toggle("mobile-open");
  } else {
    sidebar.classList.toggle("collapsed");
  }
}

function closeMobileSidebar() {
  const sidebar = document.getElementById("sidebar");
  if (sidebar && window.innerWidth <= 768) {
    sidebar.classList.remove("mobile-open");
  }
}

// ── Currency Formatting ───────────────────────────────────────

function formatINR(val) {
  return "₹" + Number(val || 0).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

// ============================================================
// PAGE 1 — OVERVIEW
// ============================================================

async function initOverviewPage() {
  await fetchAnalyticsSummary();
  await fetchRecentTransactions();
}

async function fetchAnalyticsSummary() {
  try {
    const res = await fetch("/analytics/summary");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    cachedSummary = data;
    renderSummaryKPIs(data);
    renderActionBreakdown(data.action_breakdown || {});
  } catch {
    setKpiError();
  }
}

function renderSummaryKPIs(data) {
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };

  set("ovRevenueAtRisk",    formatINR(data.total_at_risk_amount));
  set("ovTxnCount",         `Across ${(data.total_transactions || 0).toLocaleString()} failed transactions`);
  set("ovRecovered",        formatINR(data.total_recovered_amount));
  set("ovRecoveryRate",     `${((data.recovery_rate || 0) * 100).toFixed(2)}% Recovery Rate`);
  set("ovNetRecovery",      formatINR(data.net_recovery));

  // Incremental lift
  const lift = data.incremental_recovery_amount || 0;
  const sign = lift < 0 ? "−" : "+";
  set("ovIncrementalLift",  sign + formatINR(Math.abs(lift)));
  const liftPct = data.incremental_recovery_lift_pct || 0;
  const liftSign = liftPct >= 0 ? "+" : "";
  set("ovLiftPct",          liftSign + liftPct.toFixed(2) + "% vs. fixed retry baseline");

  // Blocked count
  if (data.unsafe_actions_blocked !== undefined) {
    set("ovBlocked", data.unsafe_actions_blocked);
  }

  // Update sidebar approval badge separately after approvals load
}

function setKpiError() {
  const ids = ["ovRevenueAtRisk","ovRecovered","ovNetRecovery","ovIncrementalLift","ovApprovals","ovBlocked"];
  ids.forEach(id => { const el = document.getElementById(id); if (el) el.innerText = "—"; });
  showToast("Could not load summary metrics. Check backend connection.", "danger");
}

function renderActionBreakdown(breakdown) {
  const container = document.getElementById("ovBreakdownList");
  if (!container) return;

  const total = Object.values(breakdown).reduce((a, b) => a + b, 0) || 1;
  const actions = [
    { key: "RETRY_NOW",        label: "RETRY_NOW",         css: "action-retry-now" },
    { key: "RETRY_LATER",      label: "RETRY_LATER",       css: "action-retry-later" },
    { key: "NOTIFY_CUSTOMER",  label: "NOTIFY_CUSTOMER",   css: "action-notify-customer" },
    { key: "ESCALATE",         label: "ESCALATE",          css: "action-escalate" },
    { key: "STOP",             label: "STOP",              css: "action-stop" },
  ];

  let html = "";
  actions.forEach(act => {
    const count = breakdown[act.key] || 0;
    const pct   = ((count / total) * 100).toFixed(1);
    html += `
      <div class="breakdown-row">
        <span class="breakdown-label ${act.css}">${act.label}</span>
        <div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div>
        <span class="breakdown-stat">${pct}% (${count.toLocaleString()})</span>
      </div>`;
  });

  container.innerHTML = html || '<div class="loading-row">No breakdown data available.</div>';
}

async function fetchRecentTransactions() {
  try {
    const res = await fetch("/recovery/transactions?status=ALL&search=&limit=5");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    renderRecentOpsTable(data.transactions || []);
  } catch {
    const tbody = document.getElementById("ovRecentTableBody");
    if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="empty-cell">Could not load recent operations.</td></tr>';
  }
}

function renderRecentOpsTable(txns) {
  const tbody = document.getElementById("ovRecentTableBody");
  if (!tbody) return;

  if (!txns.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-cell">No recent operations.</td></tr>';
    return;
  }

  tbody.innerHTML = txns.map(t => `
    <tr>
      <td class="cell-mono">${escapeHtml(t.payment_id)}</td>
      <td>${formatINR(t.amount)}</td>
      <td><span class="action-label badge-slate">${escapeHtml(t.failure_category || "—")}</span></td>
      <td>${getStatusBadge(t.status)}</td>
      <td class="text-muted">${formatTime(t.created_at)}</td>
      <td>
        <button class="btn btn-secondary btn-sm"
                onclick="inspectTransactionJourney('${escapeHtml(t.payment_id)}')">
          Inspect Journey
        </button>
      </td>
    </tr>`).join("");
}

// ============================================================
// PAGE 2 — TRANSACTIONS
// ============================================================

function initTransactionsPage() {
  fetchTransactions();
}

async function fetchTransactions() {
  const tbody = document.getElementById("transactionsTableBody");
  if (tbody) tbody.innerHTML = '<tr><td colspan="8" class="empty-cell">Loading...</td></tr>';

  try {
    const url = `/recovery/transactions?status=${encodeURIComponent(currentFilter)}&search=${encodeURIComponent(currentSearchQuery)}&limit=100`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    renderTransactionsTable(data.transactions || []);
  } catch {
    if (tbody) tbody.innerHTML = '<tr><td colspan="8" class="empty-cell">Could not load transactions. Please check backend connection.</td></tr>';
  }
}

function renderTransactionsTable(txns) {
  const tbody = document.getElementById("transactionsTableBody");
  if (!tbody) return;

  if (!txns.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-cell">No transactions matching filter criteria.</td></tr>';
    return;
  }

  tbody.innerHTML = txns.map(t => `
    <tr>
      <td class="cell-mono">${escapeHtml(t.payment_id)}</td>
      <td class="cell-mono" style="color:var(--text-secondary)">${escapeHtml(t.customer_id)}</td>
      <td><strong>${formatINR(t.amount)}</strong></td>
      <td>${escapeHtml(t.payment_method || "—")}</td>
      <td><span class="action-label badge-slate">${escapeHtml(t.failure_category || "—")}</span></td>
      <td>${getStatusBadge(t.status)}</td>
      <td class="text-muted">${formatTime(t.created_at)}</td>
      <td>
        <button class="btn btn-secondary btn-sm"
                onclick="inspectTransactionJourney('${escapeHtml(t.payment_id)}')">
          Inspect Journey
        </button>
      </td>
    </tr>`).join("");
}

function setFilter(filter) {
  currentFilter = filter;
  document.querySelectorAll(".filter-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.filter === filter);
  });
  fetchTransactions();
}

function searchTransactions() {
  const input = document.getElementById("txnSearchInput");
  currentSearchQuery = (input ? input.value : "").trim();
  fetchTransactions();
}

// ============================================================
// PAGE 3 — APPROVALS
// ============================================================

async function initApprovalsPage() {
  await fetchApprovals();
}

async function fetchApprovals() {
  const tbody = document.getElementById("approvalsTableBody");
  if (tbody) tbody.innerHTML = '<tr><td colspan="9" class="empty-cell">Loading...</td></tr>';

  try {
    const res = await fetch("/recovery/approvals");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    currentApprovals = data || [];
    renderApprovalsTable(currentApprovals);
    updateApprovalSummary(currentApprovals);
    updateSidebarApprovalBadge(currentApprovals.length);
  } catch {
    if (tbody) tbody.innerHTML = '<tr><td colspan="9" class="empty-cell">Could not load approvals. Please check backend connection.</td></tr>';
  }
}

function updateApprovalSummary(approvals) {
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
  const pending = approvals.filter(a => a.status === "PENDING" || a.status === "PENDING_REVIEW").length;
  set("appPendingCount",   pending);
  set("appHighValueCount", approvals.filter(a => (a.amount || 0) >= 5000).length);
  set("appTotalCount",     approvals.length);

  // Also update overview KPI
  const ovEl = document.getElementById("ovApprovals");
  if (ovEl) ovEl.innerText = pending || approvals.length;
}

function updateSidebarApprovalBadge(count) {
  const badge = document.getElementById("sidebarApprovalBadge");
  if (!badge) return;
  if (count > 0) {
    badge.innerText = count;
    badge.style.display = "inline-block";
  } else {
    badge.style.display = "none";
  }
}

function renderApprovalsTable(approvals) {
  const tbody = document.getElementById("approvalsTableBody");
  if (!tbody) return;

  if (!approvals.length) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty-cell">No pending approvals. All automated recovery actions are operating within policy bounds.</td></tr>';
    return;
  }

  tbody.innerHTML = approvals.map(app => `
    <tr>
      <td class="cell-mono">${escapeHtml(app.approval_id)}</td>
      <td class="cell-mono">${escapeHtml(app.payment_id)}</td>
      <td><strong>${formatINR(app.amount)}</strong></td>
      <td><span class="action-label badge-slate">${escapeHtml(app.failure_category || app.failure_cause || "—")}</span></td>
      <td><span class="action-label ${getActionCss(app.action)}">${escapeHtml(app.action)}</span></td>
      <td class="text-secondary" style="max-width:200px; white-space:normal">${escapeHtml(app.reason || "—")}</td>
      <td><span class="status-badge badge-warning">${escapeHtml(app.status)}</span></td>
      <td class="text-muted">${formatTime(app.created_at)}</td>
      <td>
        <button class="btn btn-primary btn-sm"
                onclick="openApprovalReview('${escapeHtml(app.approval_id)}')">
          Review
        </button>
      </td>
    </tr>`).join("");
}

// ── Approval Review Modal ─────────────────────────────────────

function openApprovalReview(approvalId) {
  const app = currentApprovals.find(a => a.approval_id === approvalId);
  if (!app) {
    showToast("Approval record not found in current queue.", "danger");
    return;
  }

  const title = document.getElementById("approvalModalTitle");
  if (title) title.innerText = `Review Intervention — ${app.payment_id}`;

  const body = document.getElementById("approvalModalBody");
  if (body) {
    body.innerHTML = `
      <div class="review-grid">
        <div class="review-section">
          <div class="review-section-title">Transaction &amp; Context</div>
          <div class="review-row">
            <span class="review-row-label">Payment ID</span>
            <span class="review-row-value cell-mono">${escapeHtml(app.payment_id)}</span>
          </div>
          <div class="review-row">
            <span class="review-row-label">Amount</span>
            <span class="review-row-value"><strong>${formatINR(app.amount)}</strong></span>
          </div>
          <div class="review-row">
            <span class="review-row-label">Merchant</span>
            <span class="review-row-value">${escapeHtml(app.merchant_id || "—")}</span>
          </div>
          <div class="review-row">
            <span class="review-row-label">Status</span>
            <span class="review-row-value"><span class="status-badge badge-warning">PENDING AUTHORIZATION</span></span>
          </div>
        </div>

        <div class="review-section">
          <div class="review-section-title">Intelligence &amp; Recommendation</div>
          <div class="review-row">
            <span class="review-row-label">Failure Cause</span>
            <span class="review-row-value">
              <span class="action-label badge-slate">${escapeHtml(app.failure_category || app.failure_cause || "—")}</span>
            </span>
          </div>
          <div class="review-row">
            <span class="review-row-label">Proposed Action</span>
            <span class="review-row-value">
              <span class="action-label ${getActionCss(app.action)}">${escapeHtml(app.action)}</span>
            </span>
          </div>
          <div class="review-row">
            <span class="review-row-label">Expected Net EV</span>
            <span class="review-row-value text-green">${app.expected_value !== undefined ? formatINR(app.expected_value) : "Calculated"}</span>
          </div>
          <div class="review-row">
            <span class="review-row-label">Model Confidence</span>
            <span class="review-row-value">${app.model_confidence !== undefined ? (app.model_confidence * 100).toFixed(1) + "%" : "—"}</span>
          </div>
        </div>
      </div>

      <div class="review-section">
        <div class="review-section-title">Deterministic Policy Boundary</div>
        <div class="review-row">
          <span class="review-row-label">Policy Gate Reason</span>
          <span class="review-row-value" style="max-width:320px; text-align:right; white-space:normal">${escapeHtml(app.reason || "High-value threshold exceeded")}</span>
        </div>
        <div class="review-row">
          <span class="review-row-label">Customer Consent</span>
          <span class="review-row-value ${app.customer_consent === false ? 'text-red' : 'text-green'}">${app.customer_consent === false ? "WITHHELD" : "VALID"}</span>
        </div>
        <div class="review-row">
          <span class="review-row-label">Retry Cooldown</span>
          <span class="review-row-value text-green">${app.cooldown_passed === false ? "BLOCKED" : "PASS"}</span>
        </div>
        <div class="review-row">
          <span class="review-row-label">Customer Risk Score</span>
          <span class="review-row-value">${app.customer_risk_score !== undefined ? app.customer_risk_score.toFixed(2) : "—"}</span>
        </div>
      </div>

      <div class="review-section" style="background:var(--amber-dim); border-color:var(--amber-border)">
        <div class="review-section-title" style="color:var(--amber)">Authorization Required</div>
        <p style="font-size:12px; color:var(--text-secondary); line-height:1.5">
          The AI engine has produced a recommendation. The deterministic policy engine has paused execution pending operator authorization.
          Approving will dispatch the action to the orchestrator. Denying will block execution and record the decision in the audit trail.
        </p>
      </div>`;
  }

  const btnApprove = document.getElementById("btnModalApprove");
  const btnDeny    = document.getElementById("btnModalDeny");

  if (btnApprove) btnApprove.onclick = () => { closeApprovalModal(); reviewApproval(approvalId, true); };
  if (btnDeny)    btnDeny.onclick    = () => { closeApprovalModal(); reviewApproval(approvalId, false); };

  const modal = document.getElementById("approvalModal");
  if (modal) modal.classList.remove("hidden");
}

function closeApprovalModal() {
  const modal = document.getElementById("approvalModal");
  if (modal) modal.classList.add("hidden");
}

async function reviewApproval(approvalId, approve) {
  try {
    const res = await fetch(
      `/recovery/approvals/${encodeURIComponent(approvalId)}/review?approve=${approve}`,
      { method: "POST" }
    );
    if (!res.ok) {
      const err = await safeParseError(res);
      showToast(`Approval action failed: ${err}`, "danger");
      return;
    }

    showToast(
      approve
        ? `Approved — action dispatched to orchestrator.`
        : `Denied — action blocked and recorded in audit trail.`,
      approve ? "success" : "info"
    );

    // Refresh all dependent data
    await fetchApprovals();
    if (cachedSummary !== null) await fetchAnalyticsSummary();
  } catch {
    showToast("Network error processing approval decision.", "danger");
  }
}

// ============================================================
// PAGE 4 — SAFETY CENTER
// ============================================================

async function initSafetyPage() {
  await fetchBlockedActions();
}

async function fetchBlockedActions() {
  const tbody = document.getElementById("blockedTableBody");
  if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="empty-cell">Loading...</td></tr>';

  try {
    const res = await fetch("/recovery/blocked");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    renderBlockedTable(data || []);
    updateSafetyCounters(data || []);
  } catch {
    if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="empty-cell">Could not load blocked actions. Please check backend connection.</td></tr>';
  }
}

function renderBlockedTable(items) {
  const tbody = document.getElementById("blockedTableBody");
  if (!tbody) return;

  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-cell">No blocked actions recorded.</td></tr>';
    return;
  }

  tbody.innerHTML = items.map(item => `
    <tr>
      <td class="cell-mono">${escapeHtml(item.transaction_id)}</td>
      <td><strong>${formatINR(item.amount)}</strong></td>
      <td><span class="action-label action-stop">${escapeHtml(item.attempted_action || "—")}</span></td>
      <td><span class="status-badge badge-blocked">${escapeHtml(item.guard_decision || "BLOCKED")}</span></td>
      <td class="text-secondary" style="max-width:240px; white-space:normal">${escapeHtml(item.reason || "—")}</td>
      <td class="text-muted">${formatTime(item.timestamp)}</td>
    </tr>`).join("");
}

function updateSafetyCounters(items) {
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
  set("safetyBlockedCount",     items.length);
  set("safetyViolationsCount",  items.length);
  set("safetyUnsafeCount",      0);

  // Update overview blocked KPI
  const ovEl = document.getElementById("ovBlocked");
  if (ovEl) ovEl.innerText = items.length;
}

// ============================================================
// PAGE 5 — AUDIT & GOVERNANCE
// ============================================================

function initAuditPage() {
  fetchAuditLogs();
}

async function fetchAuditLogs() {
  const tbody = document.getElementById("auditTableBody");
  if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="empty-cell">Loading...</td></tr>';

  try {
    const res = await fetch("/audit/logs?limit=100");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const logs = await res.json();
    renderAuditTable(logs || []);

    // Update record count
    const countEl = document.getElementById("auditRecordCount");
    if (countEl) countEl.innerText = (logs || []).length;
  } catch {
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="empty-cell">Could not load audit records. Please check backend connection.</td></tr>';
  }
}

function renderAuditTable(logs) {
  const tbody = document.getElementById("auditTableBody");
  if (!tbody) return;

  if (!logs.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-cell">No audit events recorded yet.</td></tr>';
    return;
  }

  tbody.innerHTML = logs.map(log => {
    const hashShort = log.current_hash ? log.current_hash.slice(0, 16) + "…" : "GENESIS";
    const hashFull  = escapeHtml(log.current_hash || "");
    return `
    <tr>
      <td class="text-muted">${formatTime(log.timestamp)}</td>
      <td><span class="cell-mono">${escapeHtml(log.event_type || "—")}</span></td>
      <td class="cell-mono">${escapeHtml(log.transaction_id || "—")}</td>
      <td><span class="action-label ${getActionCss(log.selected_action)}">${escapeHtml(log.selected_action || "—")}</span></td>
      <td>${getPolicyBadge(log.policy_result)}</td>
      <td class="text-secondary">${escapeHtml(log.execution_result || "—")}</td>
      <td><span class="cell-hash" title="${hashFull}">${hashShort}</span></td>
    </tr>`;
  }).join("");
}

async function verifyAuditChain() {
  const banner = document.getElementById("auditVerifyBanner");
  const btn    = document.getElementById("verifyChainBtn");
  const status = document.getElementById("auditVerifyStatus");

  if (btn) { btn.disabled = true; btn.innerText = "Verifying…"; }
  if (banner) { banner.className = "audit-verify-banner"; banner.innerHTML = "Verifying SHA-256 hash chain integrity…"; banner.classList.remove("hidden"); }

  try {
    const res = await fetch("/audit/verify");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();

    if (data.verified) {
      if (banner) {
        banner.className = "audit-verify-banner valid";
        banner.innerHTML = `<strong>VALID — Audit chain intact.</strong> All ${data.total_records || "—"} records verified with intact SHA-256 hash links. Latest: <span class="cell-mono">${escapeHtml((data.latest_hash || "").slice(0, 24))}…</span>`;
      }
      if (status) { status.innerText = "VERIFIED"; status.className = "summary-value summary-green"; }

      const latestEl = document.getElementById("auditLatestHash");
      if (latestEl) latestEl.innerText = (data.latest_hash || "—").slice(0, 32) + "…";

      showToast("Hash chain integrity verified — audit trail is tamper-free.", "success");
    } else {
      if (banner) {
        banner.className = "audit-verify-banner tampered";
        banner.innerHTML = `<strong>INVALID — Audit integrity violation detected.</strong> ${escapeHtml(data.detail || "Hash chain broken.")}`;
      }
      if (status) { status.innerText = "INVALID"; status.className = "summary-value summary-red"; }
      showToast("Audit integrity check failed — tampering detected.", "danger");
    }
  } catch {
    if (banner) {
      banner.className = "audit-verify-banner tampered";
      banner.innerHTML = "Verification request failed. Please check backend connection.";
    }
    showToast("Could not reach audit verification endpoint.", "danger");
  } finally {
    if (btn) { btn.disabled = false; btn.innerText = "Verify Hash Chain Integrity"; }
  }
}

// ============================================================
// PAGE 6 — POLICY SIMULATOR
// ============================================================

async function runPolicySimulation() {
  const btn   = document.getElementById("runSimBtn");
  const panel = document.getElementById("simResultsPanel");

  const maxRetries      = parseInt(document.getElementById("simMaxRetries")?.value || "3", 10);
  const approvalThresh  = parseFloat(document.getElementById("simApprovalThresh")?.value || "5000");
  const contactLimit    = parseInt(document.getElementById("simContactLimit")?.value || "2", 10);

  if (btn)   { btn.disabled = true; btn.innerText = "Running simulation…"; }
  if (panel) { panel.innerHTML = '<div class="loading-state">Evaluating 5,000 transaction dataset with updated policy parameters…</div>'; }

  try {
    const res = await fetch("/analytics/simulate-policy", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({
        max_retries:              maxRetries,
        approval_threshold_inr:  approvalThresh,
        contact_limit:           contactLimit,
      }),
    });

    if (!res.ok) {
      const err = await safeParseError(res);
      if (panel) panel.innerHTML = `<div class="empty-cell">Simulation failed: ${escapeHtml(err)}</div>`;
      showToast("Policy simulation failed to complete.", "danger");
      return;
    }

    const sim = await res.json();
    renderSimulationResults(sim, panel);
  } catch {
    if (panel) panel.innerHTML = '<div class="empty-cell">Simulation request failed. Please check backend connection.</div>';
    showToast("Network error running simulation.", "danger");
  } finally {
    if (btn) { btn.disabled = false; btn.innerText = "Run Policy Simulation"; }
  }
}

function renderSimulationResults(sim, panel) {
  const cur = cachedSummary || {};

  const d = (simVal, curVal) => {
    const diff = (simVal || 0) - (curVal || 0);
    const cls  = diff > 0 ? "val-pos" : diff < 0 ? "val-neg" : "";
    const sign = diff >= 0 ? "+" : "";
    return `<span class="${cls}">${sign}${typeof simVal === "number" && Math.abs(diff) > 0.5 ? diff.toFixed(2) : "—"}</span>`;
  };

  const simLift    = sim.incremental_recovery_lift_pct || 0;
  const simLiftStr = (simLift >= 0 ? "+" : "") + simLift.toFixed(2) + "%";

  panel.innerHTML = `
    <div style="margin-bottom:14px;">
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
        <h3 style="font-size:14px; font-weight:600; color:var(--text-primary)">Simulation Results</h3>
        <span class="status-badge badge-warning">SIMULATION</span>
      </div>
      <p style="font-size:11px; color:var(--text-muted)">5,000 transaction benchmark dataset. No real transactions executed.</p>
    </div>
    <table class="sim-comparison-table">
      <thead>
        <tr>
          <th>Metric</th>
          <th>Current Policy</th>
          <th>Simulated Policy</th>
          <th>Variance</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Total Recovered Revenue</strong></td>
          <td>${formatINR(cur.total_recovered_amount)}</td>
          <td style="color:var(--blue);font-weight:600">${formatINR(sim.total_recovered_amount)}</td>
          <td>${formatINR((sim.total_recovered_amount||0)-(cur.total_recovered_amount||0))}</td>
        </tr>
        <tr>
          <td><strong>Recovery Rate</strong></td>
          <td>${((cur.recovery_rate||0)*100).toFixed(2)}%</td>
          <td style="font-weight:600">${((sim.recovery_rate||0)*100).toFixed(2)}%</td>
          <td>${(((sim.recovery_rate||0)-(cur.recovery_rate||0))*100).toFixed(2)}%</td>
        </tr>
        <tr>
          <td><strong>Incremental Lift vs Baseline</strong></td>
          <td>${((cur.incremental_recovery_lift_pct||0)>=0?"+":"")+(cur.incremental_recovery_lift_pct||0).toFixed(2)}%</td>
          <td class="${simLift>=0?'val-pos':'val-neg'}">${simLiftStr}</td>
          <td>${((simLift-(cur.incremental_recovery_lift_pct||0)).toFixed(2))}%</td>
        </tr>
        <tr>
          <td><strong>Net Recovery (After Costs)</strong></td>
          <td>${formatINR(cur.net_recovery)}</td>
          <td>${formatINR(sim.net_recovery)}</td>
          <td>${formatINR((sim.net_recovery||0)-(cur.net_recovery||0))}</td>
        </tr>
        <tr>
          <td><strong>Approval-Required Actions</strong></td>
          <td>${cur.approval_required_count || 0}</td>
          <td style="color:var(--amber);font-weight:600">${sim.approval_required_count || 0}</td>
          <td>${(sim.approval_required_count||0)-(cur.approval_required_count||0)}</td>
        </tr>
        <tr>
          <td><strong>Unsafe Actions Blocked</strong></td>
          <td>${cur.unsafe_actions_blocked || 0}</td>
          <td>${sim.unsafe_actions_blocked || 0}</td>
          <td>${(sim.unsafe_actions_blocked||0)-(cur.unsafe_actions_blocked||0)}</td>
        </tr>
      </tbody>
    </table>`;
}

// ============================================================
// DEMO OPERATIONS
// ============================================================

async function runDemoTransaction() {
  const btn = document.getElementById("btnRunDemoTxn");
  const msg = document.getElementById("demoStatusMsg");

  if (btn) { btn.disabled = true; btn.innerText = "Processing…"; }
  if (msg) { msg.className = "demo-status-msg"; msg.innerText = "Submitting demo transaction…"; msg.classList.remove("hidden"); }

  try {
    const res = await fetch("/recovery/demo/transaction", { method: "POST" });
    if (!res.ok) {
      const err = await safeParseError(res);
      showToast(`Demo transaction failed: ${err}`, "danger");
      if (msg) { msg.className = "demo-status-msg msg-danger"; msg.innerText = `Failed: ${err}`; }
      return;
    }
    const data = await res.json();
    const info = `Demo payment ${data.payment_id} (${formatINR(data.amount)}) ingested — paused at Human Approval Gate (${data.reason}).`;
    showToast(info, "info");
    if (msg) { msg.className = "demo-status-msg"; msg.innerText = info + " → Navigate to Approvals to review."; }

    // Refresh overview metrics and navigate hint
    await fetchAnalyticsSummary();
    await fetchRecentTransactions();
    await fetchApprovals();
  } catch {
    showToast("Network error executing demo transaction.", "danger");
    if (msg) { msg.className = "demo-status-msg msg-danger"; msg.innerText = "Network error. Check backend connection."; }
  } finally {
    if (btn) { btn.disabled = false; btn.innerText = "Run Demo Transaction"; }
  }
}

async function runBlockedScenario() {
  const btn1 = document.getElementById("btnRunBlockedDemo");
  const btn2 = document.getElementById("btnRunBlockedDemo2");
  const msg  = document.getElementById("demoStatusMsg");

  [btn1, btn2].forEach(b => { if (b) { b.disabled = true; b.innerText = "Running…"; } });
  if (msg) { msg.className = "demo-status-msg"; msg.innerText = "Running blocked scenario…"; msg.classList.remove("hidden"); }

  try {
    const res = await fetch("/recovery/demo/blocked", { method: "POST" });
    if (!res.ok) {
      const err = await safeParseError(res);
      showToast(`Blocked scenario failed: ${err}`, "danger");
      if (msg) { msg.className = "demo-status-msg msg-danger"; msg.innerText = `Failed: ${err}`; }
      return;
    }
    const data = await res.json();
    const info = `Payment ${data.payment_id} BLOCKED by Policy Engine: ${data.reason}`;
    showToast(info, "danger");
    if (msg) { msg.className = "demo-status-msg msg-danger"; msg.innerText = info + " → Navigate to Safety Center to inspect."; }

    await fetchAnalyticsSummary();
    await fetchRecentTransactions();
  } catch {
    showToast("Network error running blocked scenario.", "danger");
    if (msg) { msg.className = "demo-status-msg msg-danger"; msg.innerText = "Network error. Check backend connection."; }
  } finally {
    [btn1, btn2].forEach(b => {
      if (b) {
        b.disabled = false;
        if (b.id === "btnRunBlockedDemo") b.innerText = "Run Blocked Scenario";
        if (b.id === "btnRunBlockedDemo2") b.innerText = "Run Blocked Scenario";
      }
    });
  }
}

// ============================================================
// TRANSACTION DECISION JOURNEY
// ============================================================

async function inspectTransactionJourney(paymentId) {
  const modal = document.getElementById("journeyModal");
  const title = document.getElementById("journeyModalTitle");
  const body  = document.getElementById("journeyModalBody");

  if (!modal) return;

  if (title) title.innerText = `Decision Journey — ${paymentId}`;
  if (body)  body.innerHTML  = '<div class="loading-state">Loading complete decision journey and EV evaluation…</div>';
  modal.classList.remove("hidden");

  try {
    const res = await fetch(`/recovery/transaction/${encodeURIComponent(paymentId)}/journey`);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    if (body) renderJourneyTimeline(data, body);
  } catch {
    if (body) body.innerHTML = '<div class="empty-cell">Could not load decision journey for this transaction.</div>';
  }
}

function renderJourneyTimeline(data, container) {
  const p       = data.payment           || {};
  const d       = data.diagnosis         || {};
  const pol     = data.policy_evaluation || {};
  const outcome = data.outcome           || {};
  const evList  = data.candidate_actions || [];
  const audits  = data.audit_trail       || [];

  // EV table
  let evTable = "";
  if (evList.length) {
    evTable = `
      <div class="step-detail" style="margin-top:8px">
        <table class="sim-comparison-table" style="margin-top:4px">
          <thead>
            <tr>
              <th>Candidate Action</th>
              <th>P(Recovery)</th>
              <th>Action Cost</th>
              <th>Friction</th>
              <th>Net EV</th>
            </tr>
          </thead>
          <tbody>
            ${evList.map(c => `
              <tr style="${c.action === data.recommended_action ? 'background:var(--blue-dim);' : ''}">
                <td><span class="action-label ${getActionCss(c.action)}">${escapeHtml(c.action)}</span>
                  ${c.action === data.recommended_action ? ' <strong style="font-size:10px;color:var(--blue)">← SELECTED</strong>' : ''}
                </td>
                <td>${(c.p_recovery * 100).toFixed(1)}%</td>
                <td>${formatINR(c.action_cost)}</td>
                <td>${formatINR(c.customer_friction)}</td>
                <td class="${c.expected_value >= 0 ? 'val-pos' : 'val-neg'}">${formatINR(c.expected_value)}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
  }

  // Audit hashes
  const auditHtml = audits.map(a => `
    <div class="step-detail" style="font-family:var(--font-mono); font-size:10px">
      [${escapeHtml(a.event_type)}] Hash: ${escapeHtml((a.current_hash || "").slice(0, 24))}…
    </div>`).join("");

  container.innerHTML = `
    <div class="timeline">

      <div class="timeline-step completed">
        <div class="timeline-dot"></div>
        <div class="step-label">1. Payment Failure Ingested</div>
        <div class="step-desc">₹${Number(p.amount||0).toLocaleString("en-IN",{minimumFractionDigits:2})} via ${escapeHtml(p.payment_method||"CARD")} recorded as failed.</div>
        <div class="step-detail">Failure code: <code>${escapeHtml(p.failure_code||"UNKNOWN")}</code> | Retry attempt: ${p.retry_count||0}</div>
      </div>

      <div class="timeline-step completed">
        <div class="timeline-dot"></div>
        <div class="step-label">2. Root-Cause Diagnosed</div>
        <div class="step-desc">Classified as: <strong>${escapeHtml(d.human_readable||d.failure_category||"Unknown")}</strong> (Confidence: ${((d.confidence||0)*100).toFixed(0)}%)</div>
      </div>

      <div class="timeline-step completed">
        <div class="timeline-dot"></div>
        <div class="step-label">3. Candidate Actions &amp; Expected-Value Ranking</div>
        <div class="step-desc">All recovery candidates evaluated against the recoverability model and operational costs.</div>
        ${evTable}
      </div>

      <div class="timeline-step completed">
        <div class="timeline-dot"></div>
        <div class="step-label">4. AI Recommendation Produced</div>
        <div class="step-desc">Optimal action selected: <span class="action-label ${getActionCss(data.recommended_action)}">${escapeHtml(data.recommended_action||"STOP")}</span>
          (Net EV: ${formatINR(data.selected_expected_value)})</div>
        ${data.reasoning_summary ? `<div class="step-detail"><strong>Reasoning:</strong> ${escapeHtml(data.reasoning_summary)}</div>` : ""}
      </div>

      <div class="timeline-step ${pol.result==='ALLOW'?'completed':pol.result==='DENY'?'blocked':'pending'}">
        <div class="timeline-dot"></div>
        <div class="step-label">5. Deterministic Policy Validation</div>
        <div class="step-desc">Policy engine decision: <strong>${escapeHtml(pol.result||"—")}</strong></div>
        ${pol.violations && pol.violations.length ? `<div class="step-detail" style="color:var(--amber)"><strong>Rules triggered:</strong> ${escapeHtml(pol.violations.join("; "))}</div>` : ""}
      </div>

      ${pol.result === "NEEDS_HUMAN_APPROVAL" || pol.result === "PENDING_APPROVAL" ? `
      <div class="timeline-step pending">
        <div class="timeline-dot"></div>
        <div class="step-label">6. Human Approval Required</div>
        <div class="step-desc">Payment exceeds the ₹5,000 high-value threshold. Paused for operator authorization.</div>
      </div>` : ""}

      <div class="timeline-step ${outcome.recovered ? 'completed' : 'completed'}">
        <div class="timeline-dot"></div>
        <div class="step-label">${pol.result === "NEEDS_HUMAN_APPROVAL" ? "7" : "6"}. Orchestration &amp; Outcome</div>
        <div class="step-desc">
          Status: <strong>${outcome.recovered ? "RECOVERED" : "EXECUTED"}</strong> |
          Recovered: <strong>${formatINR(outcome.recovered_amount)}</strong> |
          Action cost: ${formatINR(outcome.action_cost)}
        </div>
      </div>

      <div class="timeline-step completed">
        <div class="timeline-dot"></div>
        <div class="step-label">${pol.result === "NEEDS_HUMAN_APPROVAL" ? "8" : "7"}. Cryptographic Audit Record</div>
        <div class="step-desc">${audits.length} tamper-evident event(s) recorded for this transaction.</div>
        ${auditHtml}
      </div>

    </div>`;
}

function closeJourneyModal() {
  const modal = document.getElementById("journeyModal");
  if (modal) modal.classList.add("hidden");
}

// ============================================================
// KILL SWITCH
// ============================================================

async function toggleKillSwitch() {
  const btn = document.getElementById("killSwitchBtn");
  const isActive = btn && btn.classList.contains("active");
  const newState = !isActive;

  try {
    const res = await fetch(`/security/kill-switch/toggle?enable=${newState}`, { method: "POST" });
    if (!res.ok) {
      showToast("Failed to update kill switch state.", "danger");
      return;
    }
    const data = await res.json();
    updateKillSwitchUI(data.active);
    showToast(
      data.active
        ? "KILL SWITCH ACTIVATED — All automated recovery suspended."
        : "Kill switch deactivated — normal operations resumed.",
      data.active ? "danger" : "success"
    );
  } catch {
    showToast("Error communicating with kill switch endpoint.", "danger");
  }
}

function updateKillSwitchUI(active) {
  const btn    = document.getElementById("killSwitchBtn");
  const text   = document.getElementById("killSwitchText");
  const banner = document.getElementById("killSwitchBanner");

  if (active) {
    if (btn)    btn.classList.add("active");
    if (text)   text.innerText = "Kill Switch: ACTIVE";
    if (banner) banner.classList.remove("hidden");
  } else {
    if (btn)    btn.classList.remove("active");
    if (text)   text.innerText = "Kill Switch: OFF";
    if (banner) banner.classList.add("hidden");
  }
}

// ============================================================
// HELPERS
// ============================================================

function getStatusBadge(status) {
  switch (status) {
    case "EXECUTED":             return '<span class="status-badge badge-active">EXECUTED</span>';
    case "RECOVERED":            return '<span class="status-badge badge-active">RECOVERED</span>';
    case "NEEDS_HUMAN_APPROVAL": return '<span class="status-badge badge-warning">NEEDS APPROVAL</span>';
    case "BLOCKED":              return '<span class="status-badge badge-blocked">BLOCKED</span>';
    default:                     return `<span class="status-badge badge-slate">${escapeHtml(status||"FAILED")}</span>`;
  }
}

function getPolicyBadge(result) {
  switch (result) {
    case "ALLOW": return '<span class="status-badge badge-active">ALLOW</span>';
    case "DENY":  return '<span class="status-badge badge-blocked">DENY</span>';
    default:      return result ? `<span class="status-badge badge-warning">${escapeHtml(result)}</span>` : '<span class="text-muted">—</span>';
  }
}

function getActionCss(action) {
  if (!action) return "action-stop";
  switch (action.toUpperCase()) {
    case "RETRY_NOW":       return "action-retry-now";
    case "RETRY_LATER":     return "action-retry-later";
    case "NOTIFY_CUSTOMER": return "action-notify-customer";
    case "ESCALATE":        return "action-escalate";
    default:                return "action-stop";
  }
}

function formatTime(isoStr) {
  if (!isoStr) return "—";
  try {
    return new Date(isoStr).toLocaleString("en-IN", {
      hour: "2-digit", minute: "2-digit", second: "2-digit",
      hour12: false
    });
  } catch {
    return isoStr;
  }
}

async function safeParseError(res) {
  try {
    const data = await res.json();
    return data.message || data.detail || "Unknown error";
  } catch {
    return `HTTP ${res.status}`;
  }
}

function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerText = message;
  container.appendChild(toast);

  setTimeout(() => toast.remove(), 5000);
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g,  "&amp;")
    .replace(/</g,  "&lt;")
    .replace(/>/g,  "&gt;")
    .replace(/"/g,  "&quot;")
    .replace(/'/g,  "&#039;");
}
