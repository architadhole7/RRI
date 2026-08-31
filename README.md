# RevenueGuard — AI Revenue Recovery Decision & Orchestration Agent

RevenueGuard is an **AI Revenue Recovery Decision & Orchestration Agent** designed to systematically diagnose failed payment events, evaluate candidate interventions based on net expected economic value, enforce strict deterministic safety/compliance policies, and orchestrate optimal recovery workflows.

---

## 1. Project Overview

In subscription, SaaS, e-commerce, and digital finance platforms, payment failures account for substantial revenue churn. Standard retry mechanisms are rigid and inefficient—retrying randomly or spamming customers leads to high bank fees, account blocks, customer friction, and permanent customer churn.

RevenueGuard replaces ad-hoc retries with a bounded, economically driven intelligence pipeline governed by the central architectural principle:

> **LLM recommends → deterministic policy validates → orchestrator executes.**

The system ensures that artificial intelligence optimizes strategy ranking, while deterministic rules guarantee financial safety, consent compliance, rate limits, and auditability.

---

## 2. Problem Statement

Merchants face critical decision challenges whenever a payment fails:
1. **Which failed or at-risk payment events are worth recovering?**
2. **What intervention is most economically valuable?** (e.g. `RETRY_NOW`, `RETRY_LATER`, `NOTIFY_CUSTOMER`, `ESCALATE`, `STOP`)
3. **When should automated recovery stop?**
4. **When should human approval be required?**
5. **How much incremental revenue does the AI strategy generate compared with a fixed-policy baseline?**

---

## 3. Why Existing Approaches Are Insufficient

- **Generic Payment Retries**: Standard payment gateways use dumb linear retries (e.g., retry 3 times every 24h). They fail to distinguish temporary network timeouts from expired cards or hard bank blocks.
- **Unchecked AI Chatbots / Agents**: Placing LLMs directly in control of payment retries or financial transactions invites prompt injection attacks, infinite retry loops, unauthorized charges, and severe compliance violations.
- **Lack of Baseline Evaluation**: Existing recovery vendors report raw recovery numbers without benchmarking against standard fixed rules on identical held-out test data.

---

## 4. RevenueGuard Architecture

```text
Payment / Customer Events
        ↓
Data Ingestion & Integrity Validation
        ↓
Failure Diagnosis (RRI Engine)
        ↓
Recoverability Prediction (ML Model)
        ↓
Candidate Action Generation & Expected-Value Decision Engine
        ↓
Deterministic Policy & Safety Engine (Max Retries, Cooldown, Consent, High-Value Approval)
        ↓
AI Decision Layer (Structured Reasoning & Recommendations)
        ↓
Action Orchestrator (Idempotency, Queue, Execution)
        ↓
Recovery Simulator (Ground-Truth Controlled Environment)
        ↓
Outcome & Audit Trail (PII-Masked Tamper-Evident Logs)
        ↓
Analytics & Merchant Dashboard
```

---

## 5. Core System Flow

1. **Failure Ingestion**: Failed transaction context is ingested and validated against Pydantic domain schemas.
2. **Diagnosis**: Mapped into standardized categories (`INSUFFICIENT_FUNDS`, `NETWORK_ERROR`, `EXPIRED_PAYMENT_METHOD`, `BANK_DECLINED`, `LIMIT_EXCEEDED`, `TEMPORARY_FAILURE`, `UNKNOWN`).
3. **ML Recoverability Scoring**: Predicts $P(\text{recovery} \mid \text{action})$ for candidate actions without outcome feature leakage.
4. **Expected-Value Calculation**: Evaluates net economic value:
   $$\text{EV}(a) = P(\text{recovery} \mid a) \times \text{amount} - \text{cost}(a) - \text{friction}(a) - \text{risk}(a)$$
5. **Deterministic Policy Check**: Hard policy guard evaluates rules (`ALLOW`, `DENY`, `NEEDS_HUMAN_APPROVAL`).
6. **Agent Recommendation**: AI layer synthesizes reasoning while bound strictly to policy decisions.
7. **Orchestrated Execution & Audit**: Action executed through simulator/gateway with idempotency tracking and immutable audit logging.

---

## 6. System Components

- `backend/ingestion`: Pydantic domain models, integrity validators, and loaders.
- `backend/simulator`: Reproducible synthetic payment world generator and outcome simulator.
- `backend/intelligence`: RRI failure diagnoser, leakage-free feature extractor, and ML recoverability models.
- `backend/decisioning`: Expected-value decision engine and fixed-policy baseline strategy.
- `backend/policy`: Deterministic policy rules, policy engine, and human approval queue.
- `backend/agent`: Bounded AI recommendation layer with deterministic fallbacks.
- `backend/orchestrator`: Action executor, idempotency manager, and execution queue.
- `backend/security`: Threat detection (prompt injection, replays), input sanitizer, RBAC authorization, and emergency Kill Switch.
- `backend/audit`: Tamper-evident audit logger with PII masking.
- `backend/analytics`: Baseline vs. RevenueGuard evaluation pipeline and report generators.
- `frontend/dashboard`: Responsive dark-mode single-page merchant dashboard with live metrics, transaction explorer, and interactive policy simulator.

---

## 7. Synthetic Environment

Generates reproducible payment ecosystems with realistic correlations:
- **Merchants**: Categories, risk profiles.
- **Customers**: Payment method preferences, subscription status, consent states (`consent_to_contact`), risk indicators.
- **Transactions & Failures**: Amounts, timestamps, error codes, retry counts.
- **Ground Truth**: Hidden true recovery probabilities $P_{\text{true}}(\text{recovery} \mid \text{action})$ kept strictly separate from observable model features.

---

## 8. Recovery Simulator

Simulates 5 candidate actions deterministically via seedable pseudo-random rolls:
- `RETRY_NOW`: Immediate gateway retry (low cost, high friction if repeated).
- `RETRY_LATER`: Scheduled retry after optimal 24h cooldown.
- `NOTIFY_CUSTOMER`: SMS/Email notification (high friction if customer opted out).
- `ESCALATE`: Human merchant operator intervention (higher cost ₹50, high success on bank blocks).
- `STOP`: Terminate recovery to eliminate costs.

---

## 9. Decision Engine

Evaluates all candidate actions and ranks them by Net Expected Value (EV). If top non-STOP candidate has $\text{EV} \le 0$, the engine automatically falls back to `STOP`.

---

## 10. Deterministic Policy Engine

Hard safety rules that can **NEVER** be overridden by LLMs:
- **Max Retries**: Max 3 retries per transaction.
- **Cooldown**: 24-hour mandatory retry cooldown.
- **Consent Checks**: Do not contact customers who opted out.
- **High-Value Threshold**: Transactions $\ge ₹5,000$ require explicit human merchant approval.
- **Customer Risk Limit**: Risk scores $> 0.8$ trigger human review.
- **Emergency Kill Switch**: Immediately halts all automated recovery actions globally.

---

## 11. AI Agent Layer

Receives structured quantitative context and outputs `AgentRecommendation`. If API keys are unconfigured or calls fail, a deterministic fallback seamlessly synthesizes reasoning directly from EV scores and policy rules.

---

## 12. Security & Threat Controls

- **Prompt Injection Defense**: Detects and blocks malicious prompt override patterns.
- **Replay & Idempotency Safeguards**: Prevents re-executing duplicate actions.
- **Financial Safety Gating**: High-value actions queued for human review.
- **RBAC**: Role-based permissions (`admin`, `merchant_operator`, `read_only`).
- **Emergency Kill Switch**: Instant global shut-off switch.

---

## 13. Auditability & Observability

Captures an end-to-end audit trail for every transaction:
```text
INPUT → DIAGNOSIS → MODEL OUTPUT → CANDIDATE EVS → DECISION → POLICY RESULT → APPROVAL RESULT → EXECUTION → OUTCOME
```
Masks sensitive fields (`card_number`, `cvv`, `phone`) automatically before persisting.

---

## 14. Evaluation Methodology

Evaluates RevenueGuard strategy against a Fixed-Policy Baseline on identical held-out test datasets.
Measures:
- Total revenue recovered
- Incremental revenue lift (%)
- Net recovery (after costs & friction)
- Intervention counts & customer contact friction
- Unsafe actions blocked

---

## 15. Merchant Dashboard

Accessible at `http://127.0.0.1:8000/dashboard`:
- **KPI Metrics**: Real-time revenue at risk, recovered revenue, net recovery, and incremental lift.
- **Action Breakdown**: Interactive visual distribution of recovery actions.
- **Security Control Center**: Toggle emergency Kill Switch and view blocked actions.
- **Transaction Explorer**: Search transactions to inspect full decision details and audit logs.
- **Interactive Policy Simulator**: Tweak policy sliders (max retries, approval threshold) to simulate lift.

---

## 16. Installation

### 1. Prerequisites
- Python 3.10+
- Virtual Environment (`.venv`)

### 2. Setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 17. Configuration

Configured via `backend/config.py` and `.env`:
```env
APP_NAME=RevenueGuard
ENVIRONMENT=development
LOG_LEVEL=INFO
MAX_RETRIES=3
COOLDOWN_HOURS=24
HUMAN_APPROVAL_THRESHOLD_INR=5000.0
KILL_SWITCH_ENABLED=false
```

---

## 18. Dataset Generation

Generate a seedable synthetic dataset:
```powershell
.\.venv\Scripts\python.exe scripts/generate_dataset.py --customers 1000 --transactions 5000 --seed 42
```

---

## 19. Running the Demo

Execute the complete end-to-end scenario demo:
```powershell
.\.venv\Scripts\python.exe scripts/run_demo.py
```

---

## 20. Running Tests

Run the comprehensive test suite (Unit, Integration, Security, Evaluation):
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

---

## 21. Running Simulation & Evaluation

### Train Recoverability Model
```powershell
.\.venv\Scripts\python.exe scripts/train_models.py
```

### Run Recovery Simulation
```powershell
.\.venv\Scripts\python.exe scripts/run_simulation.py
```

### Run Rigorous Baseline vs. RevenueGuard Evaluation
```powershell
.\.venv\Scripts\python.exe scripts/run_evaluation.py
```

### Start API Server & Dashboard
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --reload
```
- API Documentation: `http://127.0.0.1:8000/docs`
- Merchant Dashboard: `http://127.0.0.1:8000/dashboard`

---

## 22. Limitations & Future Improvements

### Limitations
- Simulator relies on synthetic ground-truth probability distributions.
- In-memory database storage used for development prototype.

### Future Improvements
- Production integration with live payment gateways (Stripe, Razorpay).
- Persistent SQL storage (PostgreSQL/SQLAlchemy) for historical audit logs.
- Reinforcement learning (Contextual Bandits) for continuous policy optimization.
