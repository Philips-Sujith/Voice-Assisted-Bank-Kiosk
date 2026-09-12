"""
POST /api/v1/session/{session_id}/confirm
Customer verbal / UI reconfirmation step.
On confirmed=true:
  1. Auth gate enforcement (must have passed auth if auth needed)
  2. FSM → confirmed
  3. Backend → Security (async HTTP sign request)
  4. Security → Backend (signed token)
  5. FSM → queued
  6. Assign token number + queue position
  7. Persist transaction and queue entry to SQLite database
  8. Publish new_queue_entry with real customer name to Staff Portal via Redis
  9. Launch background expiry task
  Returns: { status, state, token_id, token_number, queue_position, qr_payload, expires_at, customer_name, transaction_type, amount }
"""
import logging
import os
import sys
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.models.confirmation import ConfirmationBody
from app.models.events import NewQueueEntryEvent
from app.models.security import SecuritySignRequest
from app.services.queue_manager import queue_manager
from app.services.redis_publisher import publish_event
from app.services.security_client import request_token_signing
from app.session_store import session_store

_candidate_data_dirs = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data", "database")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "database")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "database")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")),
]
for _d in _candidate_data_dirs:
    if os.path.exists(_d) and _d not in sys.path:
        sys.path.insert(0, _d)

import bank_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/confirmation")
async def confirm_transaction_alias(body: ConfirmationBody):
    return await confirm_transaction(body.session_id, body)


@router.post("/session/{session_id}/confirm")
async def confirm_transaction(session_id: str, body: ConfirmationBody):
    """
    Customer reconfirmation. Valid only when FSM is in awaiting_confirmation.
    """
    if body.session_id != session_id:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "error_code": "SESSION_ID_MISMATCH",
                "error_message": "Path session_id and body session_id do not match.",
            },
        )

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

    if machine.state != "awaiting_confirmation":
        raise HTTPException(
            status_code=409,
            detail={
                "status": "error",
                "error_code": "INVALID_STATE",
                "error_message": (
                    f"Session is in state '{machine.state}', "
                    "expected 'awaiting_confirmation'."
                ),
            },
        )

    # ── Auth gate enforcement ──────────────────────────────────────────────
    if context.backend_auth_needed and context.auth_status != "pass":
        logger.error("[%s] Auth gate violation: attempted confirmation with auth_status='%s'", session_id, context.auth_status)
        raise HTTPException(
            status_code=403,
            detail={
                "status": "error",
                "error_code": "AUTH_REQUIRED",
                "error_message": "Biometric authentication required before transaction can be confirmed.",
            },
        )

    # ── Customer rejected ──────────────────────────────────────────────────
    if not body.confirmed:
        machine.customer_rejected()
        logger.info("[%s] Customer rejected. FSM → idle.", session_id)
        bank_db.upsert_session(session_id=session_id, auth_status="rejected", fsm_state="idle")
        return {"status": "ok", "state": "idle"}

    # ── Customer confirmed ─────────────────────────────────────────────────
    machine.customer_confirmed()
    logger.info("[%s] Customer confirmed. FSM → confirmed. Calling Security.", session_id)

    # ── Single Source of Truth for confirmed transaction ──────────────────
    if body.amount is not None:
        context.entities["amount"] = body.amount
    if body.transaction_type:
        context.intent = body.transaction_type
    if body.customer_id and not context.customer_id:
        context.customer_id = body.customer_id

    amount_val = context.entities.get("amount") if context.entities else None
    if amount_val is None and (context.intent in ("withdraw", "deposit", "send_money") or context.intent is None):
        logger.error("[%s] Transaction amount is missing from confirmation request and session context", session_id)
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "error_code": "AMOUNT_MISSING",
                "error_message": "Transaction amount is required and missing.",
            },
        )

    # Build the signing request
    sign_request = SecuritySignRequest(
        session_id=session_id,
        customer_id=context.customer_id,
        transaction_type=context.intent or "deposit",
        amount=amount_val,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    # ── Security round-trip ────────────────────────────────────────────────
    try:
        signed = await request_token_signing(sign_request)
        logger.info(
            "[TRANSACTION] session_id=%s customer_id=%s transaction_type=%s amount=%s token_id=%s STEP 7: security token generated",
            session_id,
            context.customer_id,
            context.intent,
            amount_val,
            signed.token_id,
        )
    except Exception as exc:
        machine.error_occurred()
        logger.error("[%s] Security service failed: %s", session_id, exc)
        raise HTTPException(
            status_code=502,
            detail={
                "status": "error",
                "error_code": "SECURITY_SERVICE_ERROR",
                "error_message": str(exc),
            },
        )

    # Store signed token data in context
    context.token_id = signed.token_id
    context.qr_payload = signed.qr_payload
    context.hmac_signature = signed.hmac_signature
    context.expires_at = signed.expires_at

    # FSM → queued
    machine.token_signed()

    # Assign token number and queue position
    context.token_number = queue_manager.next_token_number()
    context.queue_position = queue_manager.current_queue_size()
    logger.info(
        "[TRANSACTION] session_id=%s customer_id=%s STEP 8: queue entry created: token_number=%s position=%s",
        session_id,
        context.customer_id,
        context.token_number,
        context.queue_position,
    )

    # Real customer display name
    cust_display = context.customer_name or f"Customer #{context.customer_id or context.token_number}"

    # ── Database persistence ───────────────────────────────────────────────
    try:
        effective_cust_id = context.customer_id or "unauthenticated"
        if not bank_db.get_customer(effective_cust_id):
            bank_db.upsert_customer(
                customer_id=effective_cust_id,
                display_name=cust_display,
                account_number="XXXX0000",
                balance=150000.0,
            )

        # 1. Update session FIRST so transactions FK(session_id) is satisfied
        bank_db.upsert_session(
            session_id=session_id,
            customer_id=effective_cust_id,
            customer_name=cust_display,
            auth_status="pass",
            fsm_state="queued",
        )

        # 2. Transactions record
        bank_db.record_transaction(
            transaction_id=f"txn_{signed.token_id[:12]}",
            session_id=session_id,
            customer_id=effective_cust_id,
            customer_name=cust_display,
            transaction_type=context.intent or "deposit",
            amount=amount_val,
            token_id=signed.token_id,
            status="confirmed",
        )

        # 2b. Atomically and idempotently update account balance
        updated_balance = bank_db.apply_transaction_balance(
            token_id=signed.token_id,
            transaction_id=f"txn_{signed.token_id[:12]}",
            customer_id=effective_cust_id,
            transaction_type=context.intent or "deposit",
            amount=amount_val,
        )
        logger.info(
            "[BALANCE] Customer %s balance updated: %s (txn=%s amount=%s)",
            effective_cust_id,
            updated_balance,
            context.intent,
            amount_val,
        )

        # 3. Queue entry record
        bank_db.record_queue_entry(
            token_id=signed.token_id,
            transaction_id=f"txn_{signed.token_id[:12]}",
            session_id=session_id,
            customer_id=effective_cust_id,
            customer_display_name=cust_display,
            transaction_type=context.intent or "deposit",
            amount=amount_val,
            token_number=context.token_number,
            queue_position=context.queue_position,
            status="WAITING",
        )
        logger.info(
            "[TRANSACTION] session_id=%s customer_id=%s STEP 6: database persisted",
            session_id,
            context.customer_id,
        )
    except Exception as db_exc:
        logger.error("[%s] Database insertion failed: %s", session_id, db_exc)
        machine.error_occurred()
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "error_code": "DATABASE_ERROR",
                "error_message": f"Failed to persist transaction to database: {db_exc}",
            },
        )

    # ── Publish new_queue_entry to Staff Portal via Redis Pub/Sub ──────────
    # Capture the issuance timestamp once so the event and customer/staff
    # receipts refer to the same transaction issuance time.
    issued_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    event = NewQueueEntryEvent(
        token_id=signed.token_id,
        customer_display_name=cust_display,
        transaction_type=context.intent or "deposit",
        amount=amount_val,
        queue_position=context.queue_position,
        issued_at=issued_at,
    )
    await publish_event(event.model_dump())
    logger.info(
        "[TRANSACTION] session_id=%s customer_id=%s STEP 9: staff event published",
        session_id,
        context.customer_id,
    )

    # Launch background expiry task
    context.expiry_task = queue_manager.launch_expiry_task(
        session_id=session_id,
        token_id=signed.token_id,
        expires_at=signed.expires_at,
    )

    logger.info(
        "[%s] Queued successfully. token_id=%s customer=%s type=%s amount=%s position=%d",
        session_id,
        signed.token_id,
        cust_display,
        context.intent,
        amount_val,
        context.queue_position,
    )

    return {
        "status": "ok",
        "state": machine.state,          # queued
        "token_id": signed.token_id,
        "token_number": context.token_number,
        "queue_position": context.queue_position,
        "qr_payload": signed.qr_payload,
        "expires_at": signed.expires_at,
        "customer_name": cust_display,
        "transaction_type": context.intent,
        "amount": amount_val,
        "account_balance": updated_balance,
        "issued_at": issued_at,
    }
