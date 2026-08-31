import urllib.request
import urllib.error
import json

endpoints = [
    "/.env",
    "/.git",
    "/.git/config",
    "/backend/app.py",
    "/backend/config.py",
    "/data/audit_trail.jsonl",
    "/health",
    "/system/status",
    "/audit/verify",
    "/recovery/blocked",
    "/recovery/transactions",
    "/analytics/summary",
    "/dashboard/",
]

print("=" * 60)
print("LIVE HTTP ENDPOINT SECURITY & STATUS AUDIT")
print("=" * 60)

allowed_prefixes = ("/health", "/system", "/audit", "/recovery", "/analytics", "/dashboard", "/")

for ep in endpoints:
    url = f"http://127.0.0.1:8000{ep}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            is_sensitive = ep in ("/.env", "/.git", "/.git/config", "/backend/app.py", "/backend/config.py", "/data/audit_trail.jsonl")
            if is_sensitive and status == 200:
                print(f"[SECURITY BREACH] {ep:<25} returned HTTP 200!")
            else:
                print(f"[OK] {ep:<25} -> HTTP {status} ({content_type})")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"[PROTECTED] {ep:<25} -> HTTP 404 (Not Found - Safe)")
        else:
            print(f"[HTTP ERROR] {ep:<25} -> HTTP {e.code}")
    except Exception as e:
        print(f"[ERROR] {ep:<25} -> {e}")

print("=" * 60)
