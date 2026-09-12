"""
Database module for Face Authentication service.
Backed by the unified bank_db SQLite layer.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

# Add unified data directory to path to access bank_db
_candidate_data_dirs = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "database")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "database")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data")),
]
for _d in _candidate_data_dirs:
    if os.path.exists(_d) and _d not in sys.path:
        sys.path.insert(0, _d)

import bank_db


def init_db() -> None:
    bank_db.init_db()


def get_fake_accounts() -> list[dict]:
    customers = bank_db.list_customers()
    return [{"customer_id": c["customer_id"], "display_name": c["display_name"]} for c in customers]


def get_fake_account(customer_id: str) -> dict | None:
    c = bank_db.get_customer(customer_id)
    if c:
        return {"customer_id": c["customer_id"], "display_name": c["display_name"]}
    return None


def upsert_face_embedding(customer_id: str, embedding: list[float], sample_index: int = 1, sample_label: str = "sample_1") -> None:
    bank_db.enroll_face_sample(customer_id, embedding, sample_index, sample_label)


def enroll_face_sample(customer_id: str, embedding: list[float], sample_index: int = 1, sample_label: Optional[str] = None) -> int:
    return bank_db.enroll_face_sample(customer_id, embedding, sample_index, sample_label)


def clear_customer_embeddings(customer_id: str) -> None:
    bank_db.clear_customer_embeddings(customer_id)


def list_face_embeddings(customer_id: Optional[str] = None) -> list[dict]:
    return bank_db.list_face_embeddings(customer_id)


def get_customer_enrollment(customer_id: str) -> dict:
    return bank_db.get_customer_enrollment(customer_id)



def log_face_verification(
    session_id: str,
    customer_id: str | None,
    liveness_passed: bool,
    face_score: float | None,
    auth_status: str,
    reason: str | None,
) -> None:
    bank_db.log_face_verification(
        session_id=session_id,
        customer_id=customer_id,
        liveness_passed=liveness_passed,
        face_score=face_score,
        auth_status=auth_status,
        reason=reason,
    )


def upsert_customer(customer_id: str, display_name: str) -> dict:
    return bank_db.upsert_customer(customer_id, display_name)


def get_customer(customer_id: str) -> dict | None:
    return bank_db.get_customer(customer_id)
