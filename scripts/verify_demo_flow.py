import json
import sys
import urllib.request
import urllib.error

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8001"

def test_post(endpoint, payload=None):
    url = f"{BASE_URL}{endpoint}"
    data = json.dumps(payload).encode("utf-8") if payload else b""
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))

def test_get(endpoint):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
            if "application/json" in content_type:
                return resp.status, json.loads(raw.decode("utf-8"))
            return resp.status, raw.decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="ignore")

def run_demo_verification():
    print("=" * 70)
    print("REVENUEGUARD LIVE DEMO WORKFLOW VERIFICATION (PORT 8001)")
    print("=" * 70)

    # Step A: Check Dashboard
    code, html = test_get("/dashboard/")
    assert code == 200, f"Dashboard failed with code {code}"
    print(f"[✓] Step A: Dashboard HTML loaded ({len(html)} bytes)")

    # Step B & C: Run Demo Transaction
    code, demo_res = test_post("/recovery/demo/transaction")
    assert code == 200
    payment_id = demo_res["payment_id"]
    approval_id = demo_res["approval_id"]
    assert demo_res["amount"] == 12500.0
    assert demo_res["status"] == "NEEDS_HUMAN_APPROVAL"
    print(f"[✓] Steps B & C: Demo Transaction {payment_id} (INR {demo_res['amount']}) -> Status: {demo_res['status']}")

    # Step D: Confirm in Pending Approvals
    code, approvals = test_get("/recovery/approvals")
    assert code == 200
    assert any(a["approval_id"] == approval_id for a in approvals)
    print(f"[✓] Step D: Approval {approval_id} confirmed in Pending Approvals queue")

    # Step E & F: Review Context Verification
    code, journey = test_get(f"/recovery/transaction/{payment_id}/journey")
    assert code == 200
    print(f"[✓] Steps E & F: Review explanation verified -> Diagnosis: {journey['diagnosis']['human_readable']}, Gate: {demo_res['reason']}")

    # Step G & H & I: Operator Approves & Executes
    code, review_res = test_post(f"/recovery/approvals/{approval_id}/review?approve=true")
    assert code == 200
    assert review_res["status"] == "APPROVED"
    print(f"[✓] Steps G, H, I: Operator Approved & Executed -> Action: {review_res['action']}, Reviewer: {review_res['reviewer']}")

    # Step J: Inspect Decision Journey
    code, journey_post = test_get(f"/recovery/transaction/{payment_id}/journey")
    assert code == 200
    assert len(journey_post["candidate_actions"]) >= 4
    assert len(journey_post["audit_trail"]) >= 2
    print(f"[✓] Step J: Full 10-step Decision Journey inspected ({len(journey_post['candidate_actions'])} EV candidates scored)")

    # Step K & L: Run Blocked Scenario
    code, blocked_res = test_post("/recovery/demo/blocked")
    assert code == 200
    assert blocked_res["status"] == "BLOCKED"
    print(f"[✓] Steps K & L: Blocked scenario executed -> Status: {blocked_res['status']}, Reason: {blocked_res['reason']}")

    # Step M: Confirm in Blocked Actions
    code, blocked_list = test_get("/recovery/blocked")
    assert code == 200
    assert len(blocked_list) >= 1
    print(f"[✓] Step M: Blocked Actions list confirmed ({len(blocked_list)} blocked entries recorded)")

    # Step N & O & P: Verify Audit Trail & Cryptographic Hash Chain
    code, audit_logs = test_get("/audit/logs?limit=10")
    assert code == 200
    assert len(audit_logs) >= 5

    code, verify_res = test_get("/audit/verify")
    assert code == 200
    assert verify_res["verified"] is True
    print(f"[✓] Steps N, O, P: Audit Trail verified -> Status: {verify_res['status']}, Total Records: {verify_res['total_records']}, Latest Hash: {verify_res['latest_hash'][:24]}...")

    print("=" * 70)
    print("ALL LIVE DEMO WORKFLOW STEPS VERIFIED 100% SUCCESSFULLY ON PORT 8001!")
    print("=" * 70)

if __name__ == "__main__":
    run_demo_verification()
