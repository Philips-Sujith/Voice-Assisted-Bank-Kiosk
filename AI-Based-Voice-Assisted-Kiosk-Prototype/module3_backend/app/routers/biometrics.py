"""
POST /api/v1/biometrics
Receives the biometrics auth result from the Biometrics module.
Valid when session is in awaiting_auth or idle state (upfront authentication).

Retry logic:
  - can_retry_auth() is evaluated BEFORE calling the trigger.
  - auth_failed_retry trigger carries a `before` action that increments retry_count.
  - After MAX_AUTH_RETRIES failures the session resets to idle.
"""
import logging
import os
import sys

from fastapi import APIRouter, HTTPException

from app.models.biometrics import BiometricsPayload
from app.session_store import session_store

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data"))
if DATA_DIR not in sys.path:
    sys.path.insert(0, DATA_DIR)

import bank_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/biometrics")
async def receive_biometrics(payload: BiometricsPayload):
    """
    Called by the Biometrics module after face auth resolves.
    Supports both upfront authentication and reactive authentication.
    """
    if payload.status != "ok":
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "error_code": payload.error_code or "BIOMETRICS_ERROR",
                "error_message": payload.error_message or "Biometrics reported an error.",
            },
        )

    context, machine = session_store.get_or_create(payload.session_id)

    if machine.state not in ("awaiting_auth", "idle"):
        raise HTTPException(
            status_code=409,
            detail={
                "status": "error",
                "error_code": "INVALID_STATE",
                "error_message": (
                    f"Session is in state '{machine.state}', expected 'awaiting_auth' or 'idle'. "
                    "Biometrics result arrived out of order."
                ),
            },
        )

    # Store biometrics data in session context
    context.auth_status = payload.auth_status
    context.customer_name = payload.customer_name or context.customer_name
    context.methods_used = payload.methods_used
    context.confidence_scores = payload.confidence_scores
    context.liveness_passed = payload.liveness_passed

    # ── Auth passed ────────────────────────────────────────────────────────
    if payload.auth_status == "pass":
        context.customer_id = payload.customer_id
        if not context.customer_name and payload.customer_id:
            c = bank_db.get_customer(payload.customer_id)
            if c:
                context.customer_name = c["display_name"]

        # Ensure customer exists in database before session upsert (foreign key constraint)
        if context.customer_id and not bank_db.get_customer(context.customer_id):
            bank_db.upsert_customer(
                customer_id=context.customer_id,
                display_name=context.customer_name or f"Customer #{context.customer_id}",
                account_number="XXXX1234",
                balance=285000.0,
            )

        # Persist session state to database
        bank_db.upsert_session(
            session_id=payload.session_id,
            customer_id=context.customer_id,
            customer_name=context.customer_name,
            auth_status="pass",
            fsm_state="awaiting_confirmation" if machine.state == "awaiting_auth" else "idle",
        )

        if machine.state == "awaiting_auth":
            machine.auth_passed()
            logger.info(
                "[%s] Auth passed. customer_id=%s methods=%s → state='%s'",
                payload.session_id,
                payload.customer_id,
                payload.methods_used,
                machine.state,
            )
            return {
                "status": "ok",
                "session_id": payload.session_id,
                "state": machine.state,   # awaiting_confirmation
                "customer_id": context.customer_id,
                "customer_name": context.customer_name,
            }
        else:
            logger.info(
                "[%s] Auth passed upfront. customer_id=%s customer_name=%s (FSM in idle ready for voice)",
                payload.session_id,
                context.customer_id,
                context.customer_name,
            )
            return {
                "status": "ok",
                "session_id": payload.session_id,
                "state": machine.state,   # idle
                "customer_id": context.customer_id,
                "customer_name": context.customer_name,
            }

    # ── Auth failed ────────────────────────────────────────────────────────
    bank_db.upsert_session(
        session_id=payload.session_id,
        customer_id=payload.customer_id,
        customer_name=None,
        auth_status="fail",
        fsm_state=machine.state,
    )

    if machine.state == "awaiting_auth":
        if context.can_retry_auth():
            machine.auth_failed_retry()
            logger.warning(
                "[%s] Auth failed. retry_count=%d. Prompting retry.",
                payload.session_id,
                context.retry_count,
            )
            return {
                "status": "ok",
                "session_id": payload.session_id,
                "state": machine.state,   # awaiting_auth (retry)
                "retry_count": context.retry_count,
                "action": "retry_auth",
            }
        else:
            machine.auth_failed_terminal()
            logger.error(
                "[%s] Auth failed terminally after %d retries. FSM → idle.",
                payload.session_id,
                context.retry_count,
            )
            return {
                "status": "ok",
                "session_id": payload.session_id,
                "state": machine.state,   # idle
                "action": "session_ended",
                "message": "Maximum authentication retries exceeded. Session has been reset.",
            }
    else:
        context.increment_retry_count()
        logger.warning("[%s] Upfront auth failed. retry_count=%d", payload.session_id, context.retry_count)
        return {
            "status": "ok",
            "session_id": payload.session_id,
            "state": machine.state,
            "retry_count": context.retry_count,
            "action": "retry_auth",
            "auth_status": "fail",
        }
