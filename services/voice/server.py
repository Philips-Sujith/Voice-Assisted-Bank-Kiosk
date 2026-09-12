"""
Module 2: Vernacular Voice AI — Service & WebSocket Server
Port: 8002
WebSocket: /ws/audio
REST: /api/v1/parse, /api/v1/confirm, /health
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from typing import Any, Dict, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from intent_parser import parse_intent_and_entities
from stt_pipeline import transcribe_audio_buffer
from tts_pipeline import synthesize_speech_wav

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [VoiceAI]: %(message)s")
logger = logging.getLogger("VoiceAI")

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
SERVICE_PORT = int(os.getenv("VOICE_AI_PORT", "8002"))

app = FastAPI(title="Vernacular Voice AI Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseRequest(BaseModel):
    session_id: str
    text: str
    preferred_language: str = "en"
    recognition_confidence: float = 0.92
    forward_to_backend: bool = True


class ConfirmRequest(BaseModel):
    session_id: str
    confirmed: bool
    amount: Optional[float] = None
    transaction_type: Optional[str] = None
    customer_id: Optional[str] = None


async def post_to_backend(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Forward parsed intent payload to Central Backend Orchestrator."""
    url = f"{BACKEND_URL}/api/v1/voice-intent"
    logger.info("Sending intent to Backend [%s]: intent='%s' session_id='%s'", url, payload.get("intent"), payload.get("session_id"))
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=payload)
            if resp.is_success:
                return resp.json()
            logger.warning("Backend returned error %s: %s", resp.status_code, resp.text)
            return {"status": "backend_error", "status_code": resp.status_code, "detail": resp.text}
    except Exception as exc:
        logger.error("Could not reach Backend orchestrator at %s: %s", url, exc)
        return {"status": "backend_unreachable", "error": str(exc)}


async def confirm_with_backend(
    session_id: str,
    confirmed: bool,
    amount: Optional[float] = None,
    transaction_type: Optional[str] = None,
    customer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Confirm customer transaction with Central Backend Orchestrator."""
    url = f"{BACKEND_URL}/api/v1/session/{session_id}/confirm"
    body: Dict[str, Any] = {"session_id": session_id, "confirmed": confirmed}
    if amount is not None:
        body["amount"] = amount
    if transaction_type is not None:
        body["transaction_type"] = transaction_type
    if customer_id is not None:
        body["customer_id"] = customer_id
    logger.info("Sending confirmation to Backend [%s]: confirmed=%s amount=%s", url, confirmed, amount)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=body)
            if resp.is_success:
                return resp.json()
            logger.warning("Backend confirmation returned %s: %s", resp.status_code, resp.text)
            return {"status": "backend_error", "status_code": resp.status_code, "detail": resp.text}
    except Exception as exc:
        logger.error("Could not reach Backend for confirmation: %s", exc)
        return {"status": "backend_unreachable", "error": str(exc)}


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "vernacular-voice-ai",
        "port": SERVICE_PORT,
        "backend_url": BACKEND_URL,
    }


@app.post("/api/v1/parse")
async def parse_text_endpoint(req: ParseRequest):
    """
    REST endpoint for parsing text/transcripts into intent and entities,
    and forwarding to Backend.
    """
    logger.info("[TRANSACTION] session_id=%s STEP 3: AI processing started (REST)", req.session_id)
    result = parse_intent_and_entities(
        raw_transcript=req.text,
        preferred_language=req.preferred_language,
        raw_confidence=req.recognition_confidence,
    )
    result["session_id"] = req.session_id

    backend_result = None
    if req.forward_to_backend:
        payload = {
            "session_id": req.session_id,
            "status": "ok",
            "language": req.preferred_language,
            "intent": result["intent"],
            "requires_auth": result["requires_auth"],
            "entities": result["entities"],
            "confidence": result["confidence"],
            "raw_transcript": req.text,
        }
        backend_result = await post_to_backend(payload)

    result["backend_response"] = backend_result
    if backend_result and isinstance(backend_result, dict) and "balance" in backend_result:
        bal = backend_result["balance"]
        if "entities" not in result or result["entities"] is None:
            result["entities"] = {}
        result["entities"]["balance"] = bal
        result["entities"]["amount"] = bal
        formatted_bal = f"₹{int(bal):,}"
        if req.preferred_language == "ta":
            result["spoken_text"] = f"உங்கள் கணக்கு இருப்பு {formatted_bal}."
        else:
            result["spoken_text"] = f"Your current account balance is {formatted_bal}."

    logger.info(
        "[TRANSACTION] session_id=%s STEP 4: AI processing completed: intent=%s amount=%s",
        req.session_id,
        result.get("intent"),
        result.get("entities", {}).get("amount"),
    )
    return result


@app.post("/api/v1/confirm")
async def confirm_endpoint(req: ConfirmRequest):
    """REST endpoint to confirm transaction with Backend."""
    return await confirm_with_backend(
        req.session_id,
        req.confirmed,
        amount=req.amount,
        transaction_type=req.transaction_type,
        customer_id=req.customer_id,
    )


@app.websocket("/ws/audio")
async def websocket_audio_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for Frontend ↔ Voice AI:
    - Receives session metadata handshake:
      {"session_id": "uuid", "preferred_language": "ta|en|tanglish", "sample_rate": 16000}
    - Receives audio chunks (bytes) or text JSON messages.
    - Sends back TTS audio & transcript/caption metadata:
      {"session_id": "uuid", "spoken_text": "...", "language": "...", "intent": "...", "entities": {...}, "confidence": ...}
    """
    await websocket.accept()
    logger.info("Frontend connected to Voice AI WebSocket")

    session_id: Optional[str] = None
    preferred_language: str = "en"
    sample_rate: int = 16000
    audio_buffer = bytearray()

    try:
        while True:
            message = await websocket.receive()
            # 1. Text message (JSON)
            if "text" in message and message["text"]:
                try:
                    data = json.loads(message["text"])
                except Exception:
                    data = {"type": "text", "text": message["text"]}

                msg_type = data.get("type")

                # Session start metadata handshake (must NOT match if text/transcript is provided)
                if msg_type == "init" or (
                    "session_id" in data
                    and "text" not in data
                    and "transcript" not in data
                    and msg_type != "confirm"
                    and "confirmed" not in data
                    and ("preferred_language" in data or "sample_rate" in data)
                ):
                    session_id = data.get("session_id")
                    preferred_language = data.get("preferred_language", preferred_language)
                    sample_rate = data.get("sample_rate", sample_rate)
                    logger.info("Initialized session [%s]: language=%s sample_rate=%d", session_id, preferred_language, sample_rate)
                    await websocket.send_text(json.dumps({
                        "status": "ok",
                        "session_id": session_id,
                        "message": "Session initialized",
                    }))
                    continue

                # Confirmation message
                if msg_type == "confirm" or "confirmed" in data:
                    c_session_id = data.get("session_id", session_id)
                    confirmed = bool(data.get("confirmed", True))
                    c_amount = data.get("amount")
                    c_tx_type = data.get("transaction_type")
                    c_cust_id = data.get("customer_id")
                    backend_res = await confirm_with_backend(
                        c_session_id,
                        confirmed,
                        amount=c_amount,
                        transaction_type=c_tx_type,
                        customer_id=c_cust_id,
                    )
                    await websocket.send_text(json.dumps({
                        "type": "confirmation_result",
                        "session_id": c_session_id,
                        "confirmed": confirmed,
                        "backend_response": backend_res,
                    }))
                    continue

                # Direct transcript / text utterance from client
                if "text" in data or "transcript" in data:
                    utterance = data.get("text") or data.get("transcript")
                    confidence = float(data.get("confidence", 0.92))
                    u_session = data.get("session_id", session_id)
                    u_lang = data.get("preferred_language", preferred_language)

                    logger.info("[TRANSACTION] session_id=%s STEP 3: AI processing started (WS)", u_session)
                    parsed = parse_intent_and_entities(utterance, u_lang, confidence)
                    parsed["session_id"] = u_session

                    # Forward to backend
                    backend_payload = {
                        "session_id": u_session,
                        "status": "ok",
                        "language": u_lang,
                        "intent": parsed["intent"],
                        "requires_auth": parsed["requires_auth"],
                        "entities": parsed["entities"],
                        "confidence": parsed["confidence"],
                        "raw_transcript": utterance,
                    }
                    backend_res = await post_to_backend(backend_payload)
                    parsed["backend_response"] = backend_res

                    logger.info(
                        "[TRANSACTION] session_id=%s STEP 4: AI processing completed: intent=%s amount=%s",
                        u_session,
                        parsed.get("intent"),
                        parsed.get("entities", {}).get("amount"),
                    )

                    # Synthesize TTS audio non-blockingly if applicable
                    try:
                        wav_audio = await asyncio.wait_for(
                            asyncio.to_thread(synthesize_speech_wav, parsed["spoken_text"], u_lang),
                            timeout=1.5,
                        )
                        if wav_audio:
                            parsed["audio_base64"] = base64.b64encode(wav_audio).decode("ascii")
                    except Exception as tts_err:
                        logger.debug("TTS synthesis skipped or timed out: %s", tts_err)

                    await websocket.send_text(json.dumps(parsed))
                    continue

                # Process buffered audio command
                if msg_type == "process_audio":
                    transcript, conf = transcribe_audio_buffer(bytes(audio_buffer), preferred_language, sample_rate)
                    audio_buffer.clear()
                    logger.info("[TRANSACTION] session_id=%s STEP 3: AI processing started (Audio)", session_id)
                    parsed = parse_intent_and_entities(transcript, preferred_language, conf)
                    parsed["session_id"] = session_id

                    backend_payload = {
                        "session_id": session_id,
                        "status": "ok",
                        "language": preferred_language,
                        "intent": parsed["intent"],
                        "requires_auth": parsed["requires_auth"],
                        "entities": parsed["entities"],
                        "confidence": parsed["confidence"],
                        "raw_transcript": transcript,
                    }
                    backend_res = await post_to_backend(backend_payload)
                    parsed["backend_response"] = backend_res

                    logger.info(
                        "[TRANSACTION] session_id=%s STEP 4: AI processing completed: intent=%s amount=%s",
                        session_id,
                        parsed.get("intent"),
                        parsed.get("entities", {}).get("amount"),
                    )

                    try:
                        wav_audio = await asyncio.wait_for(
                            asyncio.to_thread(synthesize_speech_wav, parsed["spoken_text"], preferred_language),
                            timeout=1.5,
                        )
                        if wav_audio:
                            parsed["audio_base64"] = base64.b64encode(wav_audio).decode("ascii")
                    except Exception as tts_err:
                        logger.debug("TTS synthesis skipped or timed out: %s", tts_err)

                    await websocket.send_text(json.dumps(parsed))
                    continue

            # 2. Binary audio chunk
            elif "bytes" in message and message["bytes"]:
                chunk = message["bytes"]
                audio_buffer.extend(chunk)

    except WebSocketDisconnect:
        logger.info("Frontend WebSocket disconnected [%s]", session_id)
    except Exception as exc:
        logger.error("WebSocket exception: %s", exc)


def main():
    logger.info("Starting Vernacular Voice AI Service on port %d...", SERVICE_PORT)
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)


if __name__ == "__main__":
    main()
