import sys
import urllib.request
import urllib.error
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000"

def test_get(endpoint):
    req = urllib.request.Request(f"{BASE_URL}{endpoint}")
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def test_post(endpoint, data=None):
    payload = json.dumps(data or {}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}{endpoint}",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

print("=" * 70)
print("REVENUEGUARD END-TO-END AUTOMATED INTEGRATION & DASHBOARD VERIFICATION")
print("=" * 70)

# 1. System Status
status, data = test_get("/system/status")
print(f"[✓] /system/status -> HTTP {status} | Operator: {data['operator']['name']} | Policy Engine: {data['safety']['policy_engine']}")
assert data['operator']['name'] == "Merchant Operations Admin"
assert data['safety']['policy_engine'] == "ACTIVE"

# 2. Analytics Summary
status, data = test_get("/analytics/summary")
print(f"[✓] /analytics/summary -> HTTP {status} | Revenue at Risk: INR {data['total_at_risk_amount']:,.2f} | Recovered: INR {data['total_recovered_amount']:,.2f} ({data['recovery_rate']*100:.2f}%)")
assert data['total_at_risk_amount'] > 0
assert data['total_recovered_amount'] > 0

# 3. Transaction List
status, data = test_get("/recovery/transactions?limit=5")
print(f"[✓] /recovery/transactions -> HTTP {status} | Total Available: {data['total']} transactions")
assert data['total'] > 0
first_tx_id = data['transactions'][0]['payment_id']

# 4. Decision Journey
status, data = test_get(f"/recovery/transaction/{first_tx_id}/journey")
print(f"[✓] /recovery/transaction/{first_tx_id}/journey -> HTTP {status} | Recommended: {data['recommended_action']} | Diagnosis: {data['diagnosis']['human_readable']}")
assert "diagnosis" in data
assert "candidate_actions" in data
assert len(data['candidate_actions']) > 0

# 5. Policy Simulation
sim_payload = {"max_retries": 2, "approval_threshold_inr": 8000.0, "contact_limit": 1}
status, data = test_post("/analytics/simulate-policy", sim_payload)
print(f"[✓] /analytics/simulate-policy -> HTTP {status} | Simulated Recovered: INR {data['total_recovered_amount']:,.2f} ({data['recovery_rate']*100:.2f}%)")
assert data['total_recovered_amount'] > 0

# 6. Audit Verification
status, data = test_get("/audit/verify")
print(f"[✓] /audit/verify -> HTTP {status} | Hash Chain Status: {data['status']} (Verified: {data['verified']})")
assert data['verified'] is True

# 7. Kill Switch Toggle
status, data = test_post("/security/kill-switch/toggle?enable=true")
print(f"[✓] /security/kill-switch/toggle (ON) -> HTTP {status} | Active: {data['active']}")
assert data['active'] is True

# Verify Fail-Closed with Kill Switch Active
status, data = test_post("/recovery/evaluate", {"payment_id": "pay_test_kill"})
print(f"[✓] Recovery under Kill Switch -> Status: {data['status']} (Action: {data['recommended_action']})")
assert data['status'] == "BLOCKED"
assert data['recommended_action'] == "STOP"

# Toggle Kill Switch back OFF
status, data = test_post("/security/kill-switch/toggle?enable=false")
print(f"[✓] /security/kill-switch/toggle (OFF) -> HTTP {status} | Active: {data['active']}")
assert data['active'] is False

# 8. Dashboard HTML & Static Files
req = urllib.request.Request(f"{BASE_URL}/dashboard/")
with urllib.request.urlopen(req) as resp:
    html = resp.read().decode("utf-8")
    print(f"[✓] /dashboard/ -> HTTP {resp.status} | HTML Size: {len(html)} bytes | Contains 'RevenueGuard': {'RevenueGuard' in html}")
    assert resp.status == 200
    assert "RevenueGuard" in html

req_css = urllib.request.Request(f"{BASE_URL}/dashboard/styles.css")
with urllib.request.urlopen(req_css) as resp:
    print(f"[✓] /dashboard/styles.css -> HTTP {resp.status} | CSS Loaded")
    assert resp.status == 200

req_js = urllib.request.Request(f"{BASE_URL}/dashboard/app.js")
with urllib.request.urlopen(req_js) as resp:
    print(f"[✓] /dashboard/app.js -> HTTP {resp.status} | JS Loaded")
    assert resp.status == 200

print("=" * 70)
print("ALL END-TO-END PRODUCT WORKFLOWS VERIFIED SUCCESSFULLY!")
print("=" * 70)
