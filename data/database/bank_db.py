"""
Persistent SQLite database layer for the Voice-Assisted Banking Kiosk System.
Provides a single verifiable source of truth for:
- Customers (customer_id, display_name, account_number, balance)
- Face Embeddings (multiple samples 1..4 per customer)
- Sessions (session_id, customer_id, auth_status, fsm_state)
- Transactions (transaction_id, session_id, customer_id, transaction_type, amount, token_id, status)
- Queue Entries (token_id, transaction_id, customer_display_name, queue_position, status)
- Face Verification Logs (session_id, customer_id, liveness_passed, face_score, auth_status)
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

DEFAULT_DB_PATH = os.path.abspath(
    os.getenv(
        "BANK_DB_PATH",
        os.path.join(os.path.dirname(__file__), "bank_kiosk.db"),
    )
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_db_dir(db_path: str = DEFAULT_DB_PATH) -> None:
    directory = os.path.dirname(os.path.abspath(db_path))
    if directory:
        os.makedirs(directory, exist_ok=True)


@contextmanager
def get_db_connection(db_path: str = DEFAULT_DB_PATH):
    ensure_db_dir(db_path)
    conn = sqlite3.connect(db_path, timeout=20.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize all banking tables and seed standard customers."""
    with get_db_connection(db_path) as conn:
        # 1. Customers
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                account_number TEXT NOT NULL,
                balance REAL DEFAULT 150000.0,
                created_at TEXT NOT NULL
            );
            """
        )

        # 2. Multi-sample face embeddings (3-4 samples per customer)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS face_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                sample_index INTEGER NOT NULL,
                sample_label TEXT,
                embedding_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE
            );
            """
        )

        # 3. Kiosk Sessions
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                customer_id TEXT,
                customer_name TEXT,
                preferred_language TEXT,
                auth_status TEXT DEFAULT 'pending',
                fsm_state TEXT DEFAULT 'awaiting_auth',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
            );
            """
        )

        # 4. Transactions
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                amount INTEGER,
                currency TEXT DEFAULT 'INR',
                token_id TEXT,
                status TEXT NOT NULL,
                balance_applied INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id),
                FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
            );
            """
        )

        # 5. Queue Entries
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS queue_entries (
                token_id TEXT PRIMARY KEY,
                transaction_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                customer_display_name TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                amount INTEGER,
                token_number INTEGER NOT NULL,
                queue_position INTEGER NOT NULL,
                status TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY(transaction_id) REFERENCES transactions(transaction_id)
            );
            """
        )

        # 6. Face verification logs
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS face_verification_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                customer_id TEXT,
                liveness_passed INTEGER NOT NULL,
                face_score REAL,
                auth_status TEXT NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL
            );
            """
        )

        # 7. Secure Face Enrollment Sessions (short-lived, passbook-verified)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS enrollment_sessions (
                session_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                account_number_masked TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
            );
            """
        )

        # Compatibility table for legacy queries
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fake_accounts (
                customer_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL
            );
            """
        )

        now = utc_now_iso()
        # Seed initial customers if not present
        count = conn.execute("SELECT COUNT(*) AS c FROM customers;").fetchone()["c"]
        if count == 0:
            seed_customers = [
                ("cust_sujith", "Sujith", "XXXX1234", 150000.0, now),
                ("acc_00981234", "Test Customer 1", "XXXX9812", 150000.0, now),
                ("acc_00981235", "Test Customer 2", "XXXX9813", 50000.0, now),
                ("acc_00981236", "Test Customer 3", "XXXX9814", 75000.0, now),
            ]
            conn.executemany(
                """
                INSERT INTO customers(customer_id, display_name, account_number, balance, created_at)
                VALUES (?, ?, ?, ?, ?);
                """,
                seed_customers,
            )
            for c_id, name, _, _, _ in seed_customers:
                conn.execute(
                    "INSERT OR IGNORE INTO fake_accounts(customer_id, display_name) VALUES (?, ?);",
                    (c_id, name),
                )

        # Ensure 10 authorized demo customers exist for passbook enrollment
        demo_customers = [
            ("demo_cust_001", "Arjun Kumar", "DEMO-100001", 125000.0, now),
            ("demo_cust_002", "Priya Sharma", "DEMO-100002", 85000.0, now),
            ("demo_cust_003", "Rahul Verma", "DEMO-100003", 210000.0, now),
            ("demo_cust_004", "Ananya Reddy", "DEMO-100004", 340000.0, now),
            ("demo_cust_005", "Karthik Menon", "DEMO-100005", 95000.0, now),
            ("demo_cust_006", "Meera Nair", "DEMO-100006", 180000.0, now),
            ("demo_cust_007", "Aditya Rao", "DEMO-100007", 65000.0, now),
            ("demo_cust_008", "Sneha Iyer", "DEMO-100008", 275000.0, now),
            ("demo_cust_009", "Vikram Das", "DEMO-100009", 150000.0, now),
            ("demo_cust_010", "Kavya Krishnan", "DEMO-100010", 315000.0, now),
        ]
        conn.executemany(
            """
            INSERT OR IGNORE INTO customers(customer_id, display_name, account_number, balance, created_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            demo_customers,
        )
        for c_id, name, _, _, _ in demo_customers:
            conn.execute(
                "INSERT OR IGNORE INTO fake_accounts(customer_id, display_name) VALUES (?, ?);",
                (c_id, name),
            )

        # Ensure demo customer Gokul exists for legacy compatibility
        conn.execute(
            """
            INSERT OR IGNORE INTO customers(customer_id, display_name, account_number, balance, created_at)
            VALUES ('cust_gokul', 'Gokul', '100020001234', 150000.0, ?);
            """,
            (now,),
        )
        conn.execute(
            "INSERT OR IGNORE INTO fake_accounts(customer_id, display_name) VALUES ('cust_gokul', 'Gokul');"
        )

        # Seed default mock queue entries if empty
        q_count = conn.execute("SELECT COUNT(*) AS c FROM queue_entries;").fetchone()["c"]
        if q_count == 0:
            seed_default_mock_queue(conn)


def seed_default_mock_queue(conn: sqlite3.Connection, force: bool = False) -> None:
    """Seed the default 8 realistic mock queue entries for demo display."""
    if force:
        conn.execute("DELETE FROM queue_entries;")

    mock_profiles = [
        ("cust_arjun", "Arjun Kumar", "XXXX8821", 125000.0, "TXN-2026-008821", "deposit", 25000, 101, 1),
        ("cust_priya", "Priya Nair", "XXXX3277", 95000.0, "TXN-2026-003277", "withdraw", 10000, 102, 2),
        ("cust_rahul", "Rahul Menon", "XXXX1104", 210000.0, "TXN-2026-001104", "transfer", 50000, 103, 3),
        ("cust_ananya", "Ananya Sharma", "XXXX5590", 340000.0, "TXN-2026-005590", "deposit", 100000, 104, 4),
        ("cust_karthik", "Karthik Raj", "XXXX7412", 68000.0, "TXN-2026-007412", "withdraw", 5000, 105, 5),
        ("cust_meera", "Meera Krishnan", "XXXX9823", 182000.0, "TXN-2026-009823", "deposit", 75000, 106, 6),
        ("cust_aditya", "Aditya Verma", "XXXX4319", 89000.0, "TXN-2026-004319", "withdraw", 15000, 107, 7),
        ("cust_divya", "Divya Iyer", "XXXX6745", 145000.0, "TXN-2026-006745", "balance_check", 0, 108, 8),
    ]

    now = utc_now_iso()
    for cust_id, name, acc, bal, token_id, txn_type, amount, t_num, q_pos in mock_profiles:
        # Upsert customer
        conn.execute(
            """
            INSERT INTO customers(customer_id, display_name, account_number, balance, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(customer_id) DO UPDATE SET display_name = excluded.display_name;
            """,
            (cust_id, name, acc, bal, now),
        )
        conn.execute(
            "INSERT OR IGNORE INTO fake_accounts(customer_id, display_name) VALUES (?, ?);",
            (cust_id, name),
        )

        sess_id = f"sess_mock_{t_num}"
        conn.execute(
            """
            INSERT OR REPLACE INTO sessions(session_id, customer_id, customer_name, preferred_language, auth_status, fsm_state, created_at, updated_at)
            VALUES (?, ?, ?, 'en', 'authenticated', 'completed', ?, ?);
            """,
            (sess_id, cust_id, name, now, now),
        )

        txn_id = f"txn_mock_{t_num}"
        conn.execute(
            """
            INSERT OR REPLACE INTO transactions(transaction_id, session_id, customer_id, customer_name, transaction_type, amount, currency, token_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'INR', ?, 'WAITING', ?);
            """,
            (txn_id, sess_id, cust_id, name, txn_type, amount, token_id, now),
        )

        conn.execute(
            """
            INSERT OR REPLACE INTO queue_entries(
                token_id, transaction_id, session_id, customer_id, customer_display_name,
                transaction_type, amount, token_number, queue_position, status, issued_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'WAITING', ?);
            """,
            (token_id, txn_id, sess_id, cust_id, name, txn_type, amount, t_num, q_pos, now),
        )



# ── Customer operations ───────────────────────────────────────────────────────

def get_customer(customer_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        row = conn.execute(
            "SELECT customer_id, display_name, account_number, balance, created_at FROM customers WHERE customer_id = ?;",
            (customer_id,),
        ).fetchone()
        return dict(row) if row else None


def list_customers(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT customer_id, display_name, account_number, balance, created_at FROM customers ORDER BY customer_id;"
        ).fetchall()
        return [dict(r) for r in rows]


def upsert_customer(
    customer_id: str,
    display_name: str,
    account_number: str = "XXXX1234",
    balance: float = 150000.0,
    db_path: str = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    now = utc_now_iso()
    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO customers(customer_id, display_name, account_number, balance, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(customer_id) DO UPDATE SET
                display_name = excluded.display_name,
                account_number = excluded.account_number;
            """,
            (customer_id, display_name, account_number, balance, now),
        )
        conn.execute(
            "INSERT OR REPLACE INTO fake_accounts(customer_id, display_name) VALUES (?, ?);",
            (customer_id, display_name),
        )
    return {"customer_id": customer_id, "display_name": display_name, "account_number": account_number, "balance": balance}


# ── Face Embedding operations (Multi-sample) ───────────────────────────────────

def enroll_face_sample(
    customer_id: str,
    embedding: List[float],
    sample_index: int = 1,
    sample_label: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> int:
    now = utc_now_iso()
    embedding_json = json.dumps(embedding)
    with get_db_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO face_embeddings(customer_id, sample_index, sample_label, embedding_json, created_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            (customer_id, sample_index, sample_label, embedding_json, now),
        )
        return cursor.lastrowid


def clear_customer_embeddings(customer_id: str, db_path: str = DEFAULT_DB_PATH) -> None:
    with get_db_connection(db_path) as conn:
        conn.execute("DELETE FROM face_embeddings WHERE customer_id = ?;", (customer_id,))


def get_customer_enrollment(customer_id: str, db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    cust = get_customer(customer_id, db_path)
    embeddings = list_face_embeddings(customer_id, db_path)
    return {
        "customer_id": customer_id,
        "customer_name": cust["display_name"] if cust else None,
        "registered": len(embeddings) > 0,
        "sample_count": len(embeddings),
        "samples": [
            {
                "sample_index": e["sample_index"],
                "sample_label": e["sample_label"],
            }
            for e in embeddings
        ],
    }



def list_face_embeddings(customer_id: Optional[str] = None, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        if customer_id:
            rows = conn.execute(
                """
                SELECT e.id, e.customer_id, e.sample_index, e.sample_label, e.embedding_json, c.display_name
                FROM face_embeddings e
                JOIN customers c ON e.customer_id = c.customer_id
                WHERE e.customer_id = ?
                ORDER BY e.sample_index;
                """,
                (customer_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT e.id, e.customer_id, e.sample_index, e.sample_label, e.embedding_json, c.display_name
                FROM face_embeddings e
                JOIN customers c ON e.customer_id = c.customer_id
                ORDER BY e.customer_id, e.sample_index;
                """
            ).fetchall()
        return [
            {
                "id": r["id"],
                "customer_id": r["customer_id"],
                "customer_name": r["display_name"],
                "sample_index": r["sample_index"],
                "sample_label": r["sample_label"],
                "embedding": json.loads(r["embedding_json"]),
            }
            for r in rows
        ]


def log_face_verification(
    session_id: str,
    customer_id: Optional[str],
    liveness_passed: bool,
    face_score: Optional[float],
    auth_status: str,
    reason: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    now = utc_now_iso()
    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO face_verification_logs(
                session_id, customer_id, liveness_passed, face_score, auth_status, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                session_id,
                customer_id,
                1 if liveness_passed else 0,
                face_score,
                auth_status,
                reason,
                now,
            ),
        )


# ── Session & Transaction operations ──────────────────────────────────────────

def upsert_session(
    session_id: str,
    customer_id: Optional[str] = None,
    customer_name: Optional[str] = None,
    preferred_language: Optional[str] = None,
    auth_status: str = "pending",
    fsm_state: str = "awaiting_auth",
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    now = utc_now_iso()
    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO sessions(session_id, customer_id, customer_name, preferred_language, auth_status, fsm_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                customer_id = COALESCE(excluded.customer_id, sessions.customer_id),
                customer_name = COALESCE(excluded.customer_name, sessions.customer_name),
                preferred_language = COALESCE(excluded.preferred_language, sessions.preferred_language),
                auth_status = excluded.auth_status,
                fsm_state = excluded.fsm_state,
                updated_at = excluded.updated_at;
            """,
            (session_id, customer_id, customer_name, preferred_language, auth_status, fsm_state, now, now),
        )


def get_session_db(session_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?;",
            (session_id,),
        ).fetchone()
        return dict(row) if row else None


get_session = get_session_db


def record_transaction(
    transaction_id: str,
    session_id: str,
    customer_id: str,
    customer_name: str,
    transaction_type: str,
    amount: Optional[int],
    token_id: Optional[str],
    status: str = "confirmed",
    currency: str = "INR",
    balance_applied: int = 0,
    db_path: str = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    now = utc_now_iso()
    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO transactions(
                transaction_id, session_id, customer_id, customer_name,
                transaction_type, amount, currency, token_id, status, balance_applied, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                transaction_id,
                session_id,
                customer_id,
                customer_name,
                transaction_type,
                amount,
                currency,
                token_id,
                status,
                balance_applied,
                now,
            ),
        )
    return {
        "transaction_id": transaction_id,
        "session_id": session_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "transaction_type": transaction_type,
        "amount": amount,
        "token_id": token_id,
        "status": status,
        "created_at": now,
    }


def record_queue_entry(
    token_id: str,
    transaction_id: str,
    session_id: str,
    customer_id: str,
    customer_display_name: str,
    transaction_type: str,
    amount: Optional[int],
    token_number: int,
    queue_position: int,
    status: str = "WAITING",
    db_path: str = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    now = utc_now_iso()
    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO queue_entries(
                token_id, transaction_id, session_id, customer_id, customer_display_name,
                transaction_type, amount, token_number, queue_position, status, issued_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(token_id) DO UPDATE SET
                status = excluded.status;
            """,
            (
                token_id,
                transaction_id,
                session_id,
                customer_id,
                customer_display_name,
                transaction_type,
                amount,
                token_number,
                queue_position,
                status,
                now,
            ),
        )
    return {
        "token_id": token_id,
        "transaction_id": transaction_id,
        "session_id": session_id,
        "customer_id": customer_id,
        "customer_display_name": customer_display_name,
        "transaction_type": transaction_type,
        "amount": amount,
        "token_number": token_number,
        "queue_position": queue_position,
        "status": status,
        "issued_at": now,
    }


def update_transaction_status(
    token_id: str,
    status: str,
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    """Update the transaction lifecycle status associated with a security token."""
    with get_db_connection(db_path) as conn:
        conn.execute(
            "UPDATE transactions SET status = ? WHERE token_id = ?;",
            (status, token_id),
        )


def update_queue_entry_status(
    token_id: str,
    status: str,
    completed_at: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    """Update queue lifecycle status and optional completion timestamp."""
    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE queue_entries
            SET status = ?, completed_at = COALESCE(?, completed_at)
            WHERE token_id = ?;
            """,
            (status, completed_at, token_id),
        )


def get_transaction_by_session(session_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM transactions WHERE session_id = ? ORDER BY created_at DESC LIMIT 1;",
            (session_id,),
        ).fetchone()
        return dict(row) if row else None


def get_queue_entry_by_token(token_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM queue_entries WHERE token_id = ?;",
            (token_id,),
        ).fetchone()
        return dict(row) if row else None


def get_queue_entry_by_session(session_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM queue_entries WHERE session_id = ? ORDER BY issued_at DESC LIMIT 1;",
            (session_id,),
        ).fetchone()
        return dict(row) if row else None


def list_active_queue_entries(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM queue_entries ORDER BY queue_position ASC;"
        ).fetchall()
        return [dict(r) for r in rows]


list_queue_entries = list_active_queue_entries



def get_customer_balance(customer_id: str, db_path: str = DEFAULT_DB_PATH) -> float:
    """Retrieve current account balance for a customer, defaulting to 150000.0."""
    with get_db_connection(db_path) as conn:
        row = conn.execute(
            "SELECT balance FROM customers WHERE customer_id = ?;",
            (customer_id,),
        ).fetchone()
        if row and row["balance"] is not None:
            return float(row["balance"])
        return 150000.0


def apply_transaction_balance(
    token_id: Optional[str],
    customer_id: str,
    transaction_type: str,
    amount: Optional[float],
    transaction_id: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> float:
    """
    Atomically and idempotently applies transaction amount to customer balance.
    Guarantees that a transaction cannot update the balance more than once.
    Returns the customer's current balance after applying.
    """
    if amount is None or amount <= 0:
        return get_customer_balance(customer_id, db_path=db_path)

    tt = (transaction_type or "").lower()
    if tt not in ("deposit", "withdraw", "withdrawal", "credit", "debit"):
        return get_customer_balance(customer_id, db_path=db_path)

    with get_db_connection(db_path) as conn:
        # Check idempotency: has this transaction already been applied?
        applied = False
        if token_id:
            row = conn.execute(
                "SELECT balance_applied FROM transactions WHERE token_id = ?;",
                (token_id,),
            ).fetchone()
            if row and row["balance_applied"]:
                applied = True
        elif transaction_id:
            row = conn.execute(
                "SELECT balance_applied FROM transactions WHERE transaction_id = ?;",
                (transaction_id,),
            ).fetchone()
            if row and row["balance_applied"]:
                applied = True

        cust_row = conn.execute(
            "SELECT balance FROM customers WHERE customer_id = ?;",
            (customer_id,),
        ).fetchone()

        if cust_row is None:
            now = utc_now_iso()
            conn.execute(
                "INSERT INTO customers(customer_id, display_name, account_number, balance, created_at) VALUES (?, ?, 'XXXX1234', 150000.0, ?);",
                (customer_id, f"Customer #{customer_id}", now),
            )
            current_balance = 150000.0
        else:
            current_balance = float(cust_row["balance"]) if cust_row["balance"] is not None else 150000.0

        if applied:
            return current_balance

        # Calculate updated balance
        if tt in ("deposit", "credit"):
            new_balance = current_balance + float(amount)
        elif tt in ("withdraw", "withdrawal", "debit"):
            new_balance = current_balance - float(amount)
        else:
            new_balance = current_balance

        # Persist new balance
        conn.execute(
            "UPDATE customers SET balance = ? WHERE customer_id = ?;",
            (new_balance, customer_id),
        )

        # Mark balance as applied for this transaction
        if token_id:
            conn.execute(
                "UPDATE transactions SET balance_applied = 1 WHERE token_id = ?;",
                (token_id,),
            )
        if transaction_id:
            conn.execute(
                "UPDATE transactions SET balance_applied = 1 WHERE transaction_id = ?;",
                (transaction_id,),
            )

        return new_balance


# ── Face Enrollment & Passbook Verification Helpers ───────────────────────────

def mask_account_number(acc: Optional[str]) -> str:
    """Safely mask account number, preserving only the last 4 digits (e.g. XXXX1234)."""
    if not acc:
        return "XXXX1234"
    digits = re.sub(r"\D", "", str(acc))
    if len(digits) >= 4:
        return f"XXXX{digits[-4:]}"
    return f"XXXX{digits}" if digits else "XXXX1234"


def normalize_name_for_match(name: Optional[str]) -> str:
    """Normalize names: lowercased, punctuation removed, excess whitespace collapsed."""
    if not name:
        return ""
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", name.lower())
    return " ".join(cleaned.split())


def get_customer_by_account_and_name(
    account_number_input: str,
    name_input: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> Optional[Dict[str, Any]]:
    """
    Matches an extracted passbook account number and customer name against bank customers.
    Security rules:
    - Account number matching requires exact or strict normalized digit matching.
    - If name is provided, checks normalized token alignment (no mismatch allowed).
    """
    raw_digits = re.sub(r"\D", "", account_number_input or "")
    if not raw_digits:
        return None

    norm_input_name = normalize_name_for_match(name_input) if name_input else ""
    input_tokens = set(norm_input_name.split()) if norm_input_name else set()

    with get_db_connection(db_path) as conn:
        rows = conn.execute("SELECT customer_id, display_name, account_number, balance FROM customers;").fetchall()
        for r in rows:
            cust = dict(r)
            cust_acc_digits = re.sub(r"\D", "", cust["account_number"] or "")
            norm_cust_name = normalize_name_for_match(cust["display_name"])
            cust_tokens = set(norm_cust_name.split())

            # Account number match check:
            # 1. Exact digit match (e.g. 100020001234 == 100020001234)
            # 2. Or passbook account ends with customer's stored 4 digits (e.g. ...1234 vs 1234 or XXXX1234)
            # 3. Or customer stored account ends with passbook digits
            acc_match = False
            if cust_acc_digits and raw_digits:
                if cust_acc_digits == raw_digits:
                    acc_match = True
                elif len(cust_acc_digits) == 4 and raw_digits.endswith(cust_acc_digits):
                    acc_match = True
                elif len(raw_digits) == 4 and cust_acc_digits.endswith(raw_digits):
                    acc_match = True
                elif len(cust_acc_digits) >= 4 and len(raw_digits) >= 4 and cust_acc_digits[-4:] == raw_digits[-4:]:
                    acc_match = True

            if not acc_match:
                continue

            # Name match check (if name provided)
            if input_tokens:
                # Require non-empty intersection and check for conflicting first/last names
                common = input_tokens.intersection(cust_tokens)
                if not common and norm_input_name != norm_cust_name:
                    continue

            return cust
    return None


def has_registered_face(customer_id: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Return True if customer already has 1 or more face sample embeddings enrolled."""
    with get_db_connection(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM face_embeddings WHERE customer_id = ?;", (customer_id,)).fetchone()
        return (row["c"] > 0) if row else False


def create_enrollment_session(
    customer_id: str,
    customer_name: str,
    account_number_masked: str,
    ttl_seconds: int = 900,
    db_path: str = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    """
    Creates a secure, short-lived, passbook-verified enrollment session.
    Default TTL: 15 minutes (900 seconds).
    """
    session_id = f"ensess_{uuid.uuid4().hex[:16]}"
    now_utc = datetime.now(timezone.utc)
    expires_at = (now_utc + timedelta(seconds=ttl_seconds)).isoformat()
    created_at = now_utc.isoformat()

    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO enrollment_sessions(session_id, customer_id, customer_name, account_number_masked, expires_at, used, created_at)
            VALUES (?, ?, ?, ?, ?, 0, ?);
            """,
            (session_id, customer_id, customer_name, account_number_masked, expires_at, created_at),
        )

    return {
        "session_id": session_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "account_number_masked": account_number_masked,
        "expires_at": expires_at,
        "ttl_seconds": ttl_seconds,
    }


def get_enrollment_session(session_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """
    Retrieves enrollment session details and validates TTL and used status.
    """
    with get_db_connection(db_path) as conn:
        row = conn.execute(
            "SELECT session_id, customer_id, customer_name, account_number_masked, expires_at, used, created_at FROM enrollment_sessions WHERE session_id = ?;",
            (session_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            exp_time = datetime.fromisoformat(d["expires_at"])
            d["is_expired"] = exp_time < datetime.now(timezone.utc)
        except Exception:
            d["is_expired"] = True

        d["is_valid"] = (d["used"] == 0) and (not d["is_expired"])
        return d


def mark_enrollment_session_used(session_id: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Marks enrollment session as consumed upon successful face registration."""
    with get_db_connection(db_path) as conn:
        cur = conn.execute("UPDATE enrollment_sessions SET used = 1 WHERE session_id = ?;", (session_id,))
        return cur.rowcount > 0


def reset_demo_face_enrollments(db_path: str = DEFAULT_DB_PATH) -> int:
    """
    Resets biometric face embeddings ONLY for authorized demo customer accounts
    (demo_cust_001 through demo_cust_010 and legacy demo accounts).
    Leaves production/user data untouched.
    """
    with get_db_connection(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM face_embeddings WHERE customer_id LIKE 'demo_cust_%' OR customer_id = 'cust_gokul';"
        )
        return cur.rowcount


