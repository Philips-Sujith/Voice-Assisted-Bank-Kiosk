"""
GET /api/v1/token/{token_id}/verify
Used by the Staff Portal before a teller acts on a token.
Verifies the token exists, checks expiry, and returns transaction details.
"""
import base64
import binascii
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.session_store import session_store

import os
import sys
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


class QRVerifyRequest(BaseModel):
    qr_payload: str


def _decode_token_id(qr_payload: str) -> str:
    try:
        raw = base64.b64decode(qr_payload, validate=True)
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error) as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "error_code": "INVALID_QR_PAYLOAD",
                "error_message": "The scanned QR payload is not a valid security token.",
            },
        ) from exc

    token_id = data.get("token_id")
    if not isinstance(token_id, str) or not token_id.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "error_code": "INVALID_QR_PAYLOAD",
                "error_message": "The QR payload does not contain a valid token identifier.",
            },
        )
    return token_id


@router.post("/token/verify-qr")
async def verify_qr_payload(body: QRVerifyRequest):
    """
    Verify a scanned customer QR against the exact payload issued for its token.

    The QR itself is never trusted for transaction details. After the payload is
    matched to the backend-issued token, the canonical transaction/session state is
    returned. This keeps the security signing key out of both the frontend and backend.
    """
    token_id = _decode_token_id(body.qr_payload)
    result = session_store.find_by_token_id(token_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "error_code": "TOKEN_NOT_FOUND",
                "error_message": f"No active session found for token_id '{token_id}'.",
            },
        )

    ctx, machine = result

    if ctx.qr_payload != body.qr_payload:
        raise HTTPException(
            status_code=401,
            detail={
                "status": "error",
                "error_code": "QR_PAYLOAD_MISMATCH",
                "error_message": "The scanned QR payload does not match the security token issued by the bank.",
            },
        )

    if machine.state != "queued":
        code = "TOKEN_ALREADY_USED" if machine.state in ("completed", "idle") else "INVALID_STATE"
        raise HTTPException(
            status_code=409,
            detail={
                "status": "error",
                "error_code": code,
                "error_message": f"Token '{token_id}' has already been processed or is in state '{machine.state}'.",
            },
        )

    if ctx.expires_at:
        expires_dt = datetime.fromisoformat(ctx.expires_at.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expires_dt:
            raise HTTPException(
                status_code=410,
                detail={
                    "status": "error",
                    "error_code": "TOKEN_EXPIRED",
                    "error_message": f"Token expired at {ctx.expires_at}.",
                },
            )

    return {
        "status": "ok",
        "token_id": token_id,
        "session_id": ctx.session_id,
        "fsm_state": machine.state,
        "transaction_type": ctx.intent,
        "amount": ctx.entities.get("amount"),
        "customer_id": ctx.customer_id,
        "customer_name": ctx.customer_name,
        "account_balance": bank_db.get_customer_balance(ctx.customer_id or "cust_sujith"),
        "token_number": ctx.token_number,
        "queue_position": ctx.queue_position,
        "expires_at": ctx.expires_at,
        "hmac_signature": ctx.hmac_signature,
    }
logger = logging.getLogger(__name__)


@router.get("/token/{token_id}/verify")
async def verify_token(token_id: str):
    """
    Staff Portal calls this when a customer presents their QR code.
    Returns transaction details if the token is valid and unexpired.
    """
    result = session_store.find_by_token_id(token_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "error_code": "TOKEN_NOT_FOUND",
                "error_message": f"No session found for token_id '{token_id}'.",
            },
        )
    ctx, machine = result

    # Enforce one-time token use: tokens can only be verified while in queued state
    if machine.state != "queued":
        raise HTTPException(
            status_code=409,
            detail={
                "status": "error",
                "error_code": "TOKEN_ALREADY_USED" if machine.state in ("completed", "idle") else "INVALID_STATE",
                "error_message": f"Token '{token_id}' has already been processed or is in state '{machine.state}'.",
            },
        )

    # Enforce expiry — Backend is responsible per the contract
    if ctx.expires_at:
        expires_dt = datetime.fromisoformat(ctx.expires_at.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expires_dt:
            raise HTTPException(
                status_code=410,
                detail={
                    "status": "error",
                    "error_code": "TOKEN_EXPIRED",
                    "error_message": f"Token expired at {ctx.expires_at}.",
                },
            )

    return {
        "status": "ok",
        "token_id": token_id,
        "session_id": ctx.session_id,
        "fsm_state": machine.state,
        "transaction_type": ctx.intent,
        "amount": ctx.entities.get("amount"),
        "customer_id": ctx.customer_id,       # None for non-auth flows
        "customer_name": ctx.customer_name,
        "token_number": ctx.token_number,
        "queue_position": ctx.queue_position,
        "expires_at": ctx.expires_at,
        "hmac_signature": ctx.hmac_signature,  # teller portal can re-verify server-side
    }
