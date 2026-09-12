"""
Session router:
- GET /api/v1/session/{session_id}/state — debug / Frontend introspection
- POST /api/v1/session/start — initialize a new kiosk session
- POST /api/v1/session/{session_id}/reset — reset transaction state and require face authentication again
"""
import logging
import os
import sys

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.session_store import session_store

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data"))
if DATA_DIR not in sys.path:
    sys.path.insert(0, DATA_DIR)

import bank_db

router = APIRouter()
logger = logging.getLogger(__name__)


class SessionStartRequest(BaseModel):
    session_id: str
    preferred_language: str = "en"


@router.post("/session/start")
async def start_session(body: SessionStartRequest):
    """Initializes or updates a kiosk session in bank_db and session_store without wiping existing authentication."""
    existing = session_store.get_session(body.session_id)
    db_sess = bank_db.get_session(body.session_id)

    if existing:
        context, machine = existing
        context.language = body.preferred_language
    else:
        context, machine = session_store.create_session(body.session_id)
        context.language = body.preferred_language
        context.auth_status = "pending"

    # If already authenticated (e.g. from upfront biometric check), preserve identity
    if db_sess and db_sess.get("auth_status") == "pass":
        context.auth_status = "pass"
        if db_sess.get("customer_id"):
            context.customer_id = db_sess.get("customer_id")
        if db_sess.get("customer_name"):
            context.customer_name = db_sess.get("customer_name")

    bank_db.upsert_session(
        session_id=body.session_id,
        customer_id=context.customer_id,
        customer_name=context.customer_name,
        preferred_language=body.preferred_language,
        auth_status=context.auth_status,
        fsm_state=machine.state,
    )

    logger.info(
        "[%s] Session initialized: language=%s auth_status=%s customer_id=%s",
        body.session_id,
        body.preferred_language,
        context.auth_status,
        context.customer_id,
    )
    return {
        "status": "ok",
        "session_id": body.session_id,
        "state": machine.state,
        "auth_status": context.auth_status,
        "customer_id": context.customer_id,
        "customer_name": context.customer_name,
    }


@router.get("/session/{session_id}/state")
async def get_session_state(session_id: str):
    """Returns the current FSM state and a safe subset of the session context."""
    session = session_store.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "error_code": "SESSION_NOT_FOUND",
                "error_message": f"No active session for session_id '{session_id}'.",
            },
        )
    context, machine = session
    safe_ctx = context.safe_subset()
    eff_cust = context.customer_id or "cust_sujith"
    current_balance = bank_db.get_customer_balance(eff_cust)
    return {
        "status": "ok",
        "session_id": session_id,
        "state": machine.state,
        "fsm_state": machine.state,
        "auth_status": context.auth_status,
        "customer_id": context.customer_id,
        "customer_name": context.customer_name,
        "transaction_type": context.intent,
        "amount": context.entities.get("amount") if context.entities else None,
        "account_balance": current_balance,
        "context": safe_ctx,
        "active_sessions": session_store.count(),
    }


@router.post("/session/{session_id}/reset")
async def reset_session(session_id: str):
    """
    Clears all transaction data and resets authentication to 'pending',
    enforcing that the customer must pass face authentication again.
    """
    context, machine = session_store.create_session(session_id)
    context.auth_status = "pending"
    context.customer_id = None
    context.customer_name = None
    context.intent = None
    context.entities = {}
    context.token_id = None
    context.token_number = None
    context.queue_position = None

    bank_db.upsert_session(
        session_id=session_id,
        auth_status="pending",
        fsm_state="idle",
    )

    logger.info("[%s] Session state reset for New Transaction. Authentication required again.", session_id)
    return {
        "status": "ok",
        "session_id": session_id,
        "state": machine.state,
        "auth_status": context.auth_status,
        "message": "Session reset successfully. Face authentication required before new transaction.",
    }


@router.get("/session/{session_id}/debug")
async def debug_session(session_id: str):
    """
    End-to-end debug inspection for one session:
    Customer, Authentication, Voice Intent, Amount, Transaction, Token, Queue, and Staff event.
    """
    session = session_store.get_session(session_id)
    context, machine = session if session else (None, None)
    db_session = bank_db.get_session(session_id)
    db_txn = bank_db.get_transaction_by_session(session_id)
    db_queue = bank_db.get_queue_entry_by_session(session_id)

    customer_id = (context.customer_id if context else None) or (db_session.get("customer_id") if db_session else None)
    customer_name = (context.customer_name if context else None) or (db_session.get("customer_name") if db_session else None)
    auth_status = (context.auth_status if context else None) or (db_session.get("auth_status") if db_session else "pending")
    intent = (context.intent if context else None) or (db_txn.get("transaction_type") if db_txn else None)
    amount = (context.entities.get("amount") if context and context.entities else None) or (db_txn.get("amount") if db_txn else None)

    return {
        "status": "ok",
        "session_id": session_id,
        "fsm_state": machine.state if machine else (db_session.get("fsm_state") if db_session else "not_found"),
        "customer": {
            "customer_id": customer_id,
            "customer_name": customer_name,
        },
        "authentication": {
            "auth_status": auth_status,
            "liveness_passed": auth_status == "pass",
            "method": "face_yunet_blink",
        },
        "voice_intent": {
            "intent": intent,
            "raw_transcript": context.raw_transcript if context else None,
            "confidence": context.confidence if context else None,
        },
        "amount": amount,
        "transaction": db_txn,
        "token": {
            "token_id": db_txn.get("token_id") if db_txn else (context.token_id if context else None),
            "token_number": db_queue.get("token_number") if db_queue else (context.token_number if context else None),
        },
        "queue": db_queue,
        "staff_event": {
            "event": "new_queue_entry",
            "token_id": db_queue.get("token_id") if db_queue else None,
            "customer_display_name": customer_name,
            "transaction_type": intent,
            "amount": amount,
            "queue_position": db_queue.get("queue_position") if db_queue else None,
        } if db_queue else None,
    }



@router.get("/customer/{customer_id}/balance")
async def get_customer_balance_endpoint(customer_id: str):
    """Retrieve the current persisted account balance for a customer."""
    balance = bank_db.get_customer_balance(customer_id)
    cust = bank_db.get_customer(customer_id)
    return {
        "status": "ok",
        "customer_id": customer_id,
        "customer_name": cust.get("display_name") if cust else f"Customer #{customer_id}",
        "account_number": cust.get("account_number") if cust else "XXXX1234",
        "balance": balance,
    }
