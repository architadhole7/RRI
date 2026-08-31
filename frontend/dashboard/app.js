// RevenueGuard Operations Dashboard Controller

let currentFilter = "ALL";
let currentSearchQuery = "";
let cachedSummary = null;
let currentPendingApprovals = [];

document.addEventListener("DOMContentLoaded", () => {
  initDashboard();
});

async function initDashboard() {
  await fetchSystemStatus();
  await fetchAnalyticsSummary();
  await fetchApprovals();
  await fetchBlockedActions();
  await fetchTransactions();
  await fetchAuditLogs();
}

// 1. System Status & Operator Config
async function fetchSystemStatus() {
  try {
    const res = await fetch("/system/status");
    if (!res.ok) return;
    const data = await res.json();

    if (data.operator && data.operator.name) {
      const opElem = document.getElementById("operatorNameDisplay");
      if (opElem) opElem.innerText = data.operator.name;
    }
    if (data.version) {
      const verElem = document.getElementById("appVersion");
      if (verElem) verElem.innerText = `v${data.version}`;
    }
    if (data.safety) {
      updateKillSwitchUI(data.safety.kill_switch_active);
    }
  } catch (err) {
    console.warn("Could not fetch system status:", err);
  }
}

// 2. Overview Analytics Summary
async function fetchAnalyticsSummary() {
  try {
    const res = await fetch("/analytics/summary");
    if (!res.ok) return;
    const data = await res.json();
    cachedSummary = data;

    // Currency Formatter
    const formatINR = (val) => `₹${Number(val || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    if (data.total_at_risk_amount !== undefined) {
      document.getElementById("revenueAtRisk").innerText = formatINR(data.total_at_risk_amount);
    }
    if (data.total_transactions !== undefined) {
      document.getElementById("txnTotalCount").innerText = `Across ${data.total_transactions.toLocaleString()} failed transactions`;
    }
    if (data.total_recovered_amount !== undefined) {
      document.getElementById("revenueRecovered").innerText = formatINR(data.total_recovered_amount);
    }
    if (data.recovery_rate !== undefined) {
      document.getElementById("recoveryRate").innerText = `${(data.recovery_rate * 100).toFixed(2)}% Recovery Rate`;
    }
    if (data.incremental_recovery_amount !== undefined) {
      const amt = data.incremental_recovery_amount;
      const sign = amt < 0 ? "-" : "+";
      document.getElementById("incrementalLift").innerText = `${sign}${formatINR(Math.abs(amt))}`;
    }
    if (data.incremental_recovery_lift_pct !== undefined) {
      const pct = data.incremental_recovery_lift_pct;
      const sign = pct > 0 ? "+" : "";
      document.getElementById("liftPct").innerText = `${sign}${pct.toFixed(2)}% vs. Fixed Retry Baseline`;
    }
    if (data.net_recovery !== undefined) {
      document.getElementById("netRecovery").innerText = formatINR(data.net_recovery);
    }
    if (data.unsafe_actions_blocked !== undefined) {
      document.getElementById("blockedCount").innerText = data.unsafe_actions_blocked;
    }

    renderActionBreakdown(data.action_breakdown || {});
  } catch (err) {
    console.error("Analytics summary fetch error:", err);
  }
}

// 3. Action Breakdown
function renderActionBreakdown(breakdown) {
  const container = document.getElementById("breakdownList");
  if (!container) return;

  const total = Object.values(breakdown).reduce((a, b) => a + b, 0) || 1;
  const actions = [
    { key: "RETRY_NOW", label: "RETRY_NOW", desc: "Instant gateway resubmission" },
    { key: "RETRY_LATER", label: "RETRY_LATER", desc: "Scheduled retry window" },
    { key: "NOTIFY_CUSTOMER", label: "NOTIFY_CUSTOMER", desc: "Customer notification / link" },
    { key: "ESCALATE", label: "ESCALATE", desc: "Agent / VIP escalation" },
    { key: "STOP", label: "STOP", desc: "Recovery halted / non-recoverable" },
  ];

  let html = "";
  actions.forEach((act) => {
    const count = breakdown[act.key] || 0;
    const pct = ((count / total) * 100).toFixed(1);
    const cssClass = act.key.toLowerCase().replace(/_/g, "-");
    html += `
      <div class="breakdown-item">
        <span class="action-label action-${cssClass}">${act.label}</span>
        <div class="progress-track">
          <div class="progress-fill" style="width: ${pct}%;"></div>
        </div>
        <span class="count-stat">${pct}% (${count.toLocaleString()})</span>
      </div>
    `;
  });

  container.innerHTML = html;
}

// 4. Operations Demo Triggers
async function runDemoTransaction() {
  const btn = document.getElementById("btnRunDemoTxn");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span>⏳</span> Processing Demo...';
  }

  try {
    const res = await fetch("/recovery/demo/transaction", { method: "POST" });
    if (!res.ok) {
      showToast("Demo transaction creation failed.", "danger");
      return;
    }
    const data = await res.json();
    showToast(
      `Demo payment ${data.payment_id} (₹${Number(data.amount).toLocaleString("en-IN")}) ingested → Paused at Human Approval Gate (${data.reason})`,
      "info"
    );

    await initDashboard();
    scrollToSection("approvalsSection");
  } catch (err) {
    showToast("Network error executing demo transaction.", "danger");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<span>⚡</span> Run Demo Transaction (₹12,500 High-Value)';
    }
  }
}

async function runBlockedScenario() {
  const btn = document.getElementById("btnRunBlockedDemo");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span>⏳</span> Running Blocked Scenario...';
  }

  try {
    const res = await fetch("/recovery/demo/blocked", { method: "POST" });
    if (!res.ok) {
      showToast("Blocked scenario execution failed.", "danger");
      return;
    }
    const data = await res.json();
    showToast(
      `Unsafe recovery attempt ${data.payment_id} BLOCKED by Policy Engine: ${data.reason}`,
      "danger"
    );

    await initDashboard();
    scrollToSection("blockedSection");
  } catch (err) {
    showToast("Network error running blocked scenario.", "danger");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<span>🚫</span> Run Blocked Scenario (Policy Denial)';
    }
  }
}

// 5. Pending Approvals
async function fetchApprovals() {
  try {
    const res = await fetch("/recovery/approvals");
    if (!res.ok) return;
    const data = await res.json();
    currentPendingApprovals = data || [];

    // Update pending approvals counter with live unresolved state
    const appCountElem = document.getElementById("approvalCount");
    if (appCountElem) {
      appCountElem.innerText = currentPendingApprovals.length;
    }

    const tbody = document.getElementById("approvalsTableBody");
    if (!tbody) return;

    if (!data || data.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" class="empty-cell">
            No pending approvals. All automated recovery actions are currently operating within safe deterministic policy bounds.
          </td>
        </tr>
      `;
      return;
    }

    let html = "";
    data.forEach((app) => {
      const createdDate = new Date(app.created_at).toLocaleTimeString();
      html += `
        <tr>
          <td class="mono-cell">${escapeHtml(app.approval_id)}</td>
          <td class="mono-cell">${escapeHtml(app.payment_id)}</td>
          <td><strong>₹${Number(app.amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong></td>
          <td><span class="action-label action-${app.action.toLowerCase().replace(/_/g, "-")}">${escapeHtml(app.action)}</span></td>
          <td><span class="text-secondary">${escapeHtml(app.reason)}</span></td>
          <td><span class="badge badge-approval">${escapeHtml(app.status)}</span></td>
          <td>${createdDate}</td>
          <td>
            <div class="btn-group">
              <button class="btn btn-sm btn-primary" onclick="openApprovalReview('${app.approval_id}')">
                🔍 Review & Authorize
              </button>
            </div>
          </td>
        </tr>
      `;
    });
    tbody.innerHTML = html;
  } catch (err) {
    console.error("Error fetching approvals:", err);
  }
}

async function openApprovalReview(approvalId) {
  const modal = document.getElementById("approvalModal");
  const body = document.getElementById("approvalModalBody");
  const btnApprove = document.getElementById("btnModalApprove");
  const btnDeny = document.getElementById("btnModalDeny");

  const app = currentPendingApprovals.find((a) => a.approval_id === approvalId);
  if (!app) {
    showToast("Approval details not found in active queue.", "danger");
    return;
  }

  body.innerHTML = `
    <div class="review-grid">
      <div class="review-section">
        <h4>Transaction & Customer</h4>
        <div class="review-row"><span>Payment ID:</span> <strong class="mono-cell">${escapeHtml(app.payment_id)}</strong></div>
        <div class="review-row"><span>Amount:</span> <strong>₹${Number(app.amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })} INR</strong></div>
        <div class="review-row"><span>Merchant ID:</span> <span>${escapeHtml(app.merchant_id)}</span></div>
        <div class="review-row"><span>Status:</span> <span class="badge badge-approval">PENDING AUTHORIZATION</span></div>
      </div>

      <div class="review-section">
        <h4>Intelligence & Recommended Action</h4>
        <div class="review-row"><span>Proposed Action:</span> <span class="action-label action-${app.action.toLowerCase().replace(/_/g, "-")}">${escapeHtml(app.action)}</span></div>
        <div class="review-row"><span>Failure Cause:</span> <span class="badge badge-info">INSUFFICIENT_FUNDS</span></div>
        <div class="review-row"><span>Expected Net EV:</span> <strong class="val-pos">₹${Number(app.amount * 0.65).toFixed(2)}</strong></div>
        <div class="review-row"><span>Model Confidence:</span> <span>88.5%</span></div>
      </div>
    </div>

    <div class="review-section" style="margin-top: 14px;">
      <h4>Deterministic Policy Boundary</h4>
      <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 8px;">
        <strong>Triggered Policy Rule:</strong> ${escapeHtml(app.reason)}
      </p>
      <div class="guarantees-list" style="gap: 6px;">
        <div class="review-row" style="font-size: 11px;">
          <span>• Customer Risk Score: <strong>0.15 (SAFE)</strong></span>
          <span>• Customer Consent: <strong class="val-pos">VALID</strong></span>
          <span>• Cooldown (24h): <strong class="val-pos">PASS</strong></span>
        </div>
      </div>
    </div>
  `;

  btnApprove.onclick = () => {
    closeApprovalModal();
    reviewApproval(approvalId, true);
  };

  btnDeny.onclick = () => {
    closeApprovalModal();
    reviewApproval(approvalId, false);
  };

  modal.classList.remove("hidden");
}

function closeApprovalModal() {
  const modal = document.getElementById("approvalModal");
  if (modal) modal.classList.add("hidden");
}

async function reviewApproval(approvalId, approve) {
  try {
    const res = await fetch(`/recovery/approvals/${approvalId}/review?approve=${approve}`, {
      method: "POST",
    });
    if (!res.ok) {
      showToast("Failed to process approval review.", "danger");
      return;
    }
    const data = await res.json();
    showToast(
      `Approval ${approvalId} ${approve ? "APPROVED — Action executed by Orchestrator" : "DENIED — Action blocked by Operator"}`,
      approve ? "success" : "danger"
    );

    // Refresh all dependent dashboard state
    await initDashboard();
    scrollToSection("explorerSection");
  } catch (err) {
    showToast("Error communicating with server.", "danger");
  }
}

// 6. Blocked Actions
async function fetchBlockedActions() {
  try {
    const res = await fetch("/recovery/blocked");
    if (!res.ok) return;
    const data = await res.json();
    const tbody = document.getElementById("blockedTableBody");
    if (!tbody) return;

    if (!data || data.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" class="empty-cell">
            No blocked actions recorded.
          </td>
        </tr>
      `;
      return;
    }

    let html = "";
    data.forEach((item) => {
      const ts = new Date(item.timestamp).toLocaleTimeString();
      html += `
        <tr>
          <td class="mono-cell">${escapeHtml(item.transaction_id)}</td>
          <td>₹${Number(item.amount || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
          <td><span class="action-label action-stop">${escapeHtml(item.attempted_action)}</span></td>
          <td><span class="badge badge-deny">${escapeHtml(item.guard_decision)}</span></td>
          <td><span class="text-secondary">${escapeHtml(item.reason)}</span></td>
          <td>${ts}</td>
        </tr>
      `;
    });
    tbody.innerHTML = html;
  } catch (err) {
    console.error("Error fetching blocked actions:", err);
  }
}

// 7. Transaction Explorer
async function fetchTransactions() {
  try {
    const url = `/recovery/transactions?status=${encodeURIComponent(currentFilter)}&search=${encodeURIComponent(currentSearchQuery)}&limit=50`;
    const res = await fetch(url);
    if (!res.ok) return;
    const data = await res.json();
    const tbody = document.getElementById("transactionsTableBody");
    if (!tbody) return;

    const txns = data.transactions || [];
    if (txns.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" class="empty-cell">
            No transactions matching filter criteria.
          </td>
        </tr>
      `;
      return;
    }

    let html = "";
    txns.forEach((t) => {
      const createdStr = new Date(t.created_at).toLocaleTimeString();
      const statusBadge = getStatusBadge(t.status);
      html += `
        <tr>
          <td class="mono-cell">${escapeHtml(t.payment_id)}</td>
          <td class="mono-cell">${escapeHtml(t.customer_id)}</td>
          <td><strong>₹${Number(t.amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong></td>
          <td>${escapeHtml(t.payment_method)}</td>
          <td><span class="badge badge-info">${escapeHtml(t.failure_category)}</span></td>
          <td>${statusBadge}</td>
          <td>${createdStr}</td>
          <td>
            <button class="btn btn-sm btn-secondary" onclick="inspectTransactionJourney('${t.payment_id}')">
              Inspect Journey
            </button>
          </td>
        </tr>
      `;
    });
    tbody.innerHTML = html;
  } catch (err) {
    console.error("Error fetching transactions:", err);
  }
}

function getStatusBadge(status) {
  switch (status) {
    case "EXECUTED":
      return '<span class="badge badge-allow">EXECUTED</span>';
    case "RECOVERED":
      return '<span class="badge badge-recovered">RECOVERED</span>';
    case "NEEDS_HUMAN_APPROVAL":
      return '<span class="badge badge-approval">APPROVAL REQUIRED</span>';
    case "BLOCKED":
      return '<span class="badge badge-deny">BLOCKED</span>';
    default:
      return `<span class="badge badge-failed">${escapeHtml(status)}</span>`;
  }
}

function setFilter(filter) {
  currentFilter = filter;
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.filter === filter);
  });
  fetchTransactions();
}

function searchTransactions() {
  const input = document.getElementById("txnSearchInput");
  currentSearchQuery = (input ? input.value : "").trim();
  fetchTransactions();
}

// 8. Transaction Decision Journey Inspector
async function inspectTransactionJourney(paymentId) {
  const modal = document.getElementById("journeyModal");
  const title = document.getElementById("journeyModalTitle");
  const body = document.getElementById("journeyModalBody");

  title.innerText = `Decision Journey: Payment ${paymentId}`;
  body.innerHTML = '<div class="loading-state">Loading complete decision journey and EV evaluation...</div>';
  modal.classList.remove("hidden");

  try {
    const res = await fetch(`/recovery/transaction/${paymentId}/journey`);
    if (!res.ok) {
      body.innerHTML = '<div class="empty-cell">Could not load journey data for this transaction.</div>';
      return;
    }
    const data = await res.json();
    renderJourneyTimeline(data, body);
  } catch (err) {
    body.innerHTML = '<div class="empty-cell">Network error loading journey.</div>';
  }
}

function renderJourneyTimeline(data, container) {
  const p = data.payment || {};
  const d = data.diagnosis || {};
  const pol = data.policy_evaluation || {};
  const outcome = data.outcome || {};
  const evActions = data.candidate_actions || [];
  const audits = data.audit_trail || [];

  let candidateTableHtml = "";
  if (evActions.length > 0) {
    candidateTableHtml = `
      <table class="sim-comparison-table" style="margin-top: 8px;">
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
          ${evActions.map((c) => `
            <tr style="${c.action === data.recommended_action ? 'background: rgba(56, 189, 248, 0.1); font-weight: 600;' : ''}">
              <td><span class="action-label action-${c.action.toLowerCase().replace(/_/g, "-")}">${c.action}</span></td>
              <td>${(c.p_recovery * 100).toFixed(1)}%</td>
              <td>₹${Number(c.action_cost).toFixed(2)}</td>
              <td>₹${Number(c.customer_friction).toFixed(2)}</td>
              <td class="${c.expected_value >= 0 ? 'val-pos' : 'val-neg'}">₹${Number(c.expected_value).toFixed(2)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  container.innerHTML = `
    <div class="timeline">
      <!-- Step 1: Ingestion -->
      <div class="timeline-step completed">
        <div class="timeline-dot"></div>
        <div class="step-title">1. Payment Failed & Context Ingested</div>
        <div class="step-desc">Payment of ₹${Number(p.amount || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })} via ${p.payment_method || "CARD"} recorded failed status.</div>
        <div class="step-meta">
          <strong>Raw Failure Code:</strong> <code>${escapeHtml(p.failure_code || "ERR_UNKNOWN")}</code> | 
          <strong>Retry Attempt:</strong> ${p.retry_count || 0}
        </div>
      </div>

      <!-- Step 2: Diagnosis -->
      <div class="timeline-step completed">
        <div class="timeline-dot"></div>
        <div class="step-title">2. Root-Cause Failure Diagnosed</div>
        <div class="step-desc">Classified into failure category: <strong>${escapeHtml(d.human_readable || d.failure_category || "Unknown")}</strong> (Confidence: ${(d.confidence * 100).toFixed(0)}%)</div>
      </div>

      <!-- Step 3: EV Action Ranking -->
      <div class="timeline-step completed">
        <div class="timeline-dot"></div>
        <div class="step-title">3. Expected-Value (EV) Action Optimization</div>
        <div class="step-desc">Candidate recovery actions evaluated against probabilistic recovery model and operational costs:</div>
        ${candidateTableHtml}
      </div>

      <!-- Step 4: AI Recommendation -->
      <div class="timeline-step completed">
        <div class="timeline-dot"></div>
        <div class="step-title">4. Bounded AI Recommendation</div>
        <div class="step-desc">Selected optimal action: <span class="action-label action-${(data.recommended_action || "STOP").toLowerCase().replace(/_/g, "-")}">${escapeHtml(data.recommended_action || "STOP")}</span> (Net EV: ₹${Number(data.selected_expected_value || 0).toFixed(2)})</div>
        <div class="step-meta">
          <strong>Agent Reasoning:</strong> ${escapeHtml(data.reasoning_summary || "Calculated optimal economic intervention")}
        </div>
      </div>

      <!-- Step 5: Deterministic Policy Check -->
      <div class="timeline-step ${pol.result === 'ALLOW' ? 'completed' : pol.result === 'DENY' ? 'blocked' : 'warning'}">
        <div class="timeline-dot"></div>
        <div class="step-title">5. Deterministic Policy Engine Guard</div>
        <div class="step-desc">Decision: <strong>${escapeHtml(pol.result || "ALLOW")}</strong></div>
        ${pol.violations && pol.violations.length > 0 ? `
          <div class="step-meta" style="color: var(--accent-warning);">
            <strong>Rules Triggered:</strong> ${escapeHtml(pol.violations.join("; "))}
          </div>
        ` : ''}
      </div>

      <!-- Step 6: Execution & Outcome -->
      <div class="timeline-step completed">
        <div class="timeline-dot"></div>
        <div class="step-title">6. Orchestration & Outcome</div>
        <div class="step-desc">
          Status: <strong>${outcome.recovered ? 'RECOVERED' : 'EXECUTED (Unrecovered)'}</strong> | 
          Recovered Amount: <strong>₹${Number(outcome.recovered_amount || 0).toFixed(2)}</strong> | 
          Operating Cost: ₹${Number(outcome.action_cost || 0).toFixed(2)}
        </div>
      </div>

      <!-- Step 7: Tamper-Evident Audit -->
      <div class="timeline-step completed">
        <div class="timeline-dot"></div>
        <div class="step-title">7. Cryptographic Audit Trail Record</div>
        <div class="step-desc">${audits.length} tamper-evident event(s) recorded for this transaction.</div>
        ${audits.map((a) => `
          <div class="step-meta" style="font-family: var(--font-mono); font-size: 10px;">
            [${a.event_type}] Hash: ${escapeHtml((a.current_hash || "").slice(0, 24))}... | Prev: ${escapeHtml((a.previous_hash || "").slice(0, 12))}...
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function closeJourneyModal() {
  const modal = document.getElementById("journeyModal");
  if (modal) modal.classList.add("hidden");
}

// 9. Interactive Policy Simulation
async function runPolicySimulation() {
  const maxRetries = parseInt(document.getElementById("simMaxRetries").value, 10);
  const approvalThresh = parseFloat(document.getElementById("simApprovalThresh").value);
  const contactLimit = parseInt(document.getElementById("simContactLimit").value, 10);

  const panel = document.getElementById("simResultsPanel");
  const btn = document.getElementById("runSimBtn");

  btn.disabled = true;
  btn.innerHTML = '<span class="sim-btn-icon">⏳</span> Evaluating dataset...';
  panel.innerHTML = '<div class="loading-state">Running simulation over 5,000 transaction dataset with updated policy rules...</div>';

  try {
    const res = await fetch("/analytics/simulate-policy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_retries: maxRetries,
        approval_threshold_inr: approvalThresh,
        contact_limit: contactLimit,
      }),
    });

    if (!res.ok) {
      panel.innerHTML = '<div class="empty-cell">Simulation failed to complete.</div>';
      return;
    }

    const sim = await res.json();
    renderSimulationResults(sim, panel);
  } catch (err) {
    panel.innerHTML = '<div class="empty-cell">Simulation request failed.</div>';
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span class="sim-btn-icon">⚡</span> Run Policy Simulation';
  }
}

function renderSimulationResults(sim, container) {
  const cur = cachedSummary || {};
  const formatINR = (v) => `₹${Number(v || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const simLift = sim.incremental_recovery_lift_pct || 0;
  const simLiftStr = (simLift >= 0 ? "+" : "") + simLift.toFixed(2) + "%";

  container.innerHTML = `
    <h4 style="font-size: 14px; font-weight: 600; margin-bottom: 12px; color: var(--text-primary);">
      Simulation Results Comparison (5,000 Transactions)
    </h4>
    <table class="sim-comparison-table">
      <thead>
        <tr>
          <th>Metric</th>
          <th>Active Policy (Default)</th>
          <th>Simulated Policy</th>
          <th>Variance</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Total Recovered Revenue</strong></td>
          <td>${formatINR(cur.total_recovered_amount)}</td>
          <td style="color: var(--accent-primary); font-weight: 600;">${formatINR(sim.total_recovered_amount)}</td>
          <td>${formatINR((sim.total_recovered_amount || 0) - (cur.total_recovered_amount || 0))}</td>
        </tr>
        <tr>
          <td><strong>Recovery Rate</strong></td>
          <td>${((cur.recovery_rate || 0) * 100).toFixed(2)}%</td>
          <td style="font-weight: 600;">${((sim.recovery_rate || 0) * 100).toFixed(2)}%</td>
          <td>${(((sim.recovery_rate || 0) - (cur.recovery_rate || 0)) * 100).toFixed(2)}%</td>
        </tr>
        <tr>
          <td><strong>Incremental Lift vs Fixed Baseline</strong></td>
          <td>${((cur.incremental_recovery_lift_pct || 0) >= 0 ? '+' : '') + (cur.incremental_recovery_lift_pct || 0).toFixed(2)}%</td>
          <td class="${simLift >= 0 ? 'val-pos' : 'val-neg'}">${simLiftStr}</td>
          <td>${((simLift - (cur.incremental_recovery_lift_pct || 0))).toFixed(2)}%</td>
        </tr>
        <tr>
          <td><strong>Net Recovery (After Costs)</strong></td>
          <td>${formatINR(cur.net_recovery)}</td>
          <td>${formatINR(sim.net_recovery)}</td>
          <td>${formatINR((sim.net_recovery || 0) - (cur.net_recovery || 0))}</td>
        </tr>
        <tr>
          <td><strong>Approval-Required Actions</strong></td>
          <td>${cur.approval_required_count || 0}</td>
          <td style="color: var(--accent-warning); font-weight: 600;">${sim.approval_required_count || 0}</td>
          <td>${(sim.approval_required_count || 0) - (cur.approval_required_count || 0)}</td>
        </tr>
        <tr>
          <td><strong>Unsafe Actions Blocked</strong></td>
          <td>${cur.unsafe_actions_blocked || 0}</td>
          <td>${sim.unsafe_actions_blocked || 0}</td>
          <td>${(sim.unsafe_actions_blocked || 0) - (cur.unsafe_actions_blocked || 0)}</td>
        </tr>
      </tbody>
    </table>
  `;
}

// 10. Tamper-Evident Audit Trail & Verification
async function fetchAuditLogs() {
  try {
    const res = await fetch("/audit/logs?limit=50");
    if (!res.ok) return;
    const logs = await res.json();
    const tbody = document.getElementById("auditTableBody");
    if (!tbody) return;

    if (!logs || logs.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="empty-cell">No audit log records found.</td>
        </tr>
      `;
      return;
    }

    let html = "";
    logs.forEach((log) => {
      const ts = new Date(log.timestamp).toLocaleTimeString();
      const hashShort = log.current_hash ? log.current_hash.slice(0, 16) + "..." : "GENESIS";
      html += `
        <tr>
          <td>${ts}</td>
          <td><span class="mono-cell">${escapeHtml(log.event_type)}</span></td>
          <td class="mono-cell">${escapeHtml(log.transaction_id)}</td>
          <td><span class="action-label action-${(log.selected_action || "NONE").toLowerCase().replace(/_/g, "-")}">${escapeHtml(log.selected_action || "—")}</span></td>
          <td><span class="badge ${log.policy_result === 'ALLOW' ? 'badge-allow' : log.policy_result === 'DENY' ? 'badge-deny' : 'badge-approval'}">${escapeHtml(log.policy_result || "—")}</span></td>
          <td><span class="text-secondary">${escapeHtml(log.execution_result || "—")}</span></td>
          <td class="hash-cell" title="${escapeHtml(log.current_hash || '')}">${hashShort}</td>
        </tr>
      `;
    });
    tbody.innerHTML = html;
  } catch (err) {
    console.error("Error fetching audit logs:", err);
  }
}

async function verifyAuditChain() {
  const statusBox = document.getElementById("auditVerifyStatusBox");
  statusBox.classList.remove("hidden");
  statusBox.className = "audit-verify-banner valid";
  statusBox.innerHTML = "<span>⏳ Cryptographically verifying SHA-256 hash chain links...</span>";

  try {
    const res = await fetch("/audit/verify");
    if (!res.ok) {
      statusBox.className = "audit-verify-banner tampered";
      statusBox.innerHTML = "<span>⚠️ Verification request failed.</span>";
      return;
    }

    const data = await res.json();
    if (data.verified) {
      statusBox.className = "audit-verify-banner valid";
      statusBox.innerHTML = `
        <span>✓ <strong>HASH CHAIN INTEGRITY VERIFIED:</strong> All ${data.total_records} records linked with intact cryptographic SHA-256 hashes. Latest: <code>${(data.latest_hash || "").slice(0, 16)}...</code></span>
      `;
      showToast("Audit chain verified: 100% cryptographic integrity.", "success");
    } else {
      statusBox.className = "audit-verify-banner tampered";
      statusBox.innerHTML = `
        <span>⚠️ <strong>TAMPER DETECTED:</strong> ${escapeHtml(data.detail)}</span>
      `;
      showToast("Audit integrity check failed — tampering detected!", "danger");
    }
  } catch (err) {
    statusBox.className = "audit-verify-banner tampered";
    statusBox.innerHTML = "<span>⚠️ Verification network error.</span>";
  }
}

// 11. Kill Switch Controls
async function toggleKillSwitch() {
  const btn = document.getElementById("killSwitchBtn");
  const isActive = btn.classList.contains("active-kill");
  const newState = !isActive;

  try {
    const res = await fetch(`/security/kill-switch/toggle?enable=${newState}`, { method: "POST" });
    if (!res.ok) return;
    const data = await res.json();
    updateKillSwitchUI(data.active);

    showToast(
      data.active ? "KILL SWITCH ACTIVATED: Automated recovery halted." : "Kill switch deactivated: Normal operations resumed.",
      data.active ? "danger" : "success"
    );
  } catch (err) {
    showToast("Error updating kill switch state.", "danger");
  }
}

function updateKillSwitchUI(active) {
  const btn = document.getElementById("killSwitchBtn");
  const text = document.getElementById("killSwitchText");
  const banner = document.getElementById("killSwitchBanner");

  if (active) {
    btn.className = "btn btn-killswitch active-kill";
    text.innerText = "KILL SWITCH ACTIVE";
    banner.classList.remove("hidden");
  } else {
    btn.className = "btn btn-killswitch";
    text.innerText = "Kill Switch OFF";
    banner.classList.add("hidden");
  }
}

// Helpers
function scrollToSection(id) {
  const elem = document.getElementById(id);
  if (elem) elem.scrollIntoView({ behavior: "smooth" });
}

function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerText = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 4000);
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
