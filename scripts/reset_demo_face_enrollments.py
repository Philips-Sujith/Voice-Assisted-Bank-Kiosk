"""
Demo Face Enrollment Reset Tool.
Cleans up enrolled face biometrics strictly for the 10 authorized demo accounts
(demo_cust_001 through demo_cust_010), leaving all core customer accounts and balances intact.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
candidates = [
    ROOT.parent / "data" / "database",
    ROOT / "data" / "database",
    ROOT.parent / "data",
    ROOT / "data",
]
DATA_DIR = next((p for p in candidates if (p / "bank_db.py").exists()), candidates[0])

if str(DATA_DIR) not in sys.path:
    sys.path.insert(0, str(DATA_DIR))
import bank_db

def main():
    print("=" * 65)
    print("  RESETTING DEMO BIOMETRIC FACE ENROLLMENTS")
    print("=" * 65)

    # 1. Reset demo embeddings
    count = bank_db.reset_demo_face_enrollments()
    print(f"[RESET] Cleared {count} biometric sample records for demo accounts.")

    # 2. Verify / re-seed customer balances
    bank_db.init_db()

    # 3. List status of all 10 demo accounts
    demo_customers = [c for c in bank_db.list_customers() if c["customer_id"].startswith("demo_cust_")]
    demo_customers.sort(key=lambda c: c["customer_id"])

    print(f"\n[DEMO ACCOUNTS READY] ({len(demo_customers)} accounts):")
    for c in demo_customers:
        has_face = bank_db.has_registered_face(c["customer_id"])
        face_status = "ENROLLED" if has_face else "NOT ENROLLED (READY)"
        print(f"  - {c['customer_id']}: {c['display_name']:<18} | Acc: {c['account_number']:<12} | Bal: INR {c['balance']:>10,.2f} | Face: {face_status}")

    print("\n[SUCCESS] Demo accounts are reset and ready for passbook verification & face enrollment testing.")

if __name__ == "__main__":
    main()
