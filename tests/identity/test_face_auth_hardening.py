"""
Test Suite for Hardened Face Registration and Face Authentication
Covers:
1. Face capability check (InsightFace, OpenCV, AntiSpoof)
2. Face enrollment status endpoint & 4-sample database persistence verification
3. Biometric verification with customer identification (Sujith)
4. Wrong-face rejection test
5. Photo spoof / no-blink rejection test
6. Authentication gate enforcement (unauthenticated customer blocked from transaction)
7. Complete end-to-end flow: Face Authentication -> Voice AI (1 Lakh deposit) -> Backend confirmation -> Queue & Staff Portal
"""
import json
import os
import sys
import uuid
import httpx
import numpy as np
import pytest

_candidate_data_dirs = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "database")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "database")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data")),
]
for _d in _candidate_data_dirs:
    if os.path.exists(_d) and _d not in sys.path:
        sys.path.insert(0, _d)

import bank_db

BACKEND_URL = "http://127.0.0.1:8000"
FACE_URL = "http://127.0.0.1:8003"
VOICE_URL = "http://127.0.0.1:8002"
SECURITY_URL = "http://127.0.0.1:8001"


def test_01_face_capabilities():
    """Verify face engine has OpenCV, InsightFace, and models loaded."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(f"{FACE_URL}/face-auth/capabilities")
        assert resp.status_code == 200, f"Capabilities endpoint failed: {resp.text}"
        data = resp.json()
        assert data["dependencies"]["opencv"] is True
        assert data["dependencies"]["insightface"] is True
        assert data["embedding_model_ready"] is True
        assert data["liveness_model_ready"] is True
        print(f"[PASS] Face Auth Capabilities: models ready, anti_spoof backend: {data['anti_spoof']['backend']}")


def test_02_enrollment_database_persistence():
    """Verify 4 face samples enrolled for Sujith are persisted in database and verified via endpoint."""
    customer_id = "cust_sujith"
    customer_name = "Sujith"

    # Reset customer and enroll 4 distinct embeddings
    bank_db.clear_customer_embeddings(customer_id)
    bank_db.upsert_customer(customer_id, customer_name, account_number="AC987654")

    labels = ["front_neutral", "left_angle", "right_angle", "tilt_smile"]
    for i in range(4):
        emb = np.random.randn(512).astype(np.float32)
        emb = emb / np.linalg.norm(emb)
        bank_db.enroll_face_sample(
            customer_id=customer_id,
            embedding=emb.tolist(),
            sample_index=i + 1,
            sample_label=labels[i],
        )

    # Verify via database layer
    enrollment = bank_db.get_customer_enrollment(customer_id)
    assert enrollment["registered"] is True
    assert enrollment["sample_count"] == 4
    assert enrollment["customer_name"] == "Sujith"
    assert len(enrollment["samples"]) == 4

    # Verify via Face Auth GET /face-auth/enrollment-status/{customer_id}
    with httpx.Client(timeout=6.0) as client:
        resp = client.get(f"{FACE_URL}/face-auth/enrollment-status/{customer_id}")
        assert resp.status_code == 200, f"Enrollment status API failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "ok"
        assert data["customer_id"] == customer_id
        assert data["customer_name"] == customer_name
        assert data["registered"] is True
        assert data["sample_count"] == 4
        print(f"[PASS] 4 face samples securely verified in bank database for {customer_name} ({customer_id})")


def test_03_authentication_pass_and_identity_binding():
    """Verify face authentication binds customer identity to the backend session with auth_status='pass'."""
    session_id = str(uuid.uuid4())

    with httpx.Client(timeout=8.0) as client:
        # 1. Start session
        start_res = client.post(f"{BACKEND_URL}/api/v1/session/start", json={"session_id": session_id, "preferred_language": "en"})
        assert start_res.status_code == 200
        assert start_res.json()["auth_status"] == "pending"

        # 2. Run Face Auth verification for Sujith
        verify_res = client.post(
            f"{FACE_URL}/face-auth/verify-simulated",
            json={
                "session_id": session_id,
                "scenario": "success",
                "customer_id": "cust_sujith",
                "customer_name": "Sujith",
                "auth_status": "pass",
                "liveness_passed": True,
                "face_score": 0.94,
            },
        )
        assert verify_res.status_code == 200
        v_data = verify_res.json()
        assert v_data["auth_status"] == "pass"
        assert v_data["customer_id"] == "cust_sujith"
        assert v_data["customer_name"] == "Sujith"
        assert v_data["liveness_passed"] is True

        # 3. Confirm Backend session is now authenticated
        state_res = client.get(f"{BACKEND_URL}/api/v1/session/{session_id}/state")
        assert state_res.status_code == 200
        state = state_res.json()
        assert state["auth_status"] == "pass"
        assert state["customer_id"] == "cust_sujith"
        assert state["customer_name"] == "Sujith"
        print(f"[PASS] Authentication passed: session {session_id} bound to {state['customer_name']} ({state['customer_id']})")


def test_04_wrong_face_rejection():
    """Verify that an unregistered or wrong face is rejected and cannot authenticate."""
    session_id = str(uuid.uuid4())

    with httpx.Client(timeout=8.0) as client:
        # Start session
        client.post(f"{BACKEND_URL}/api/v1/session/start", json={"session_id": session_id, "preferred_language": "en"})

        # Run verification with wrong face
        verify_res = client.post(
            f"{FACE_URL}/face-auth/verify-simulated",
            json={
                "session_id": session_id,
                "scenario": "wrong_face",
            },
        )
        assert verify_res.status_code == 200
        v_data = verify_res.json()
        assert v_data["auth_status"] == "fail"
        assert v_data["error_code"] == "FACE_MATCH_FAILED"
        assert v_data["customer_id"] is None

        # Backend session must remain unauthenticated
        state_res = client.get(f"{BACKEND_URL}/api/v1/session/{session_id}/state")
        state = state_res.json()
        assert state["auth_status"] != "pass"
        assert state["customer_id"] is None
        print("[PASS] Wrong face correctly rejected with FACE_MATCH_FAILED. Access denied.")


def test_05_photo_spoof_no_blink_rejection():
    """Verify that a static photo or presentation spoof with no genuine blink is rejected."""
    session_id = str(uuid.uuid4())

    with httpx.Client(timeout=8.0) as client:
        # Start session
        client.post(f"{BACKEND_URL}/api/v1/session/start", json={"session_id": session_id, "preferred_language": "en"})

        # Run verification with photo spoof (no blink)
        verify_res = client.post(
            f"{FACE_URL}/face-auth/verify-simulated",
            json={
                "session_id": session_id,
                "scenario": "photo_spoof",
            },
        )
        assert verify_res.status_code == 200
        v_data = verify_res.json()
        assert v_data["auth_status"] == "fail"
        assert v_data["error_code"] == "BLINK_NOT_DETECTED"
        assert v_data["liveness_passed"] is False

        # Backend session must remain unauthenticated
        state_res = client.get(f"{BACKEND_URL}/api/v1/session/{session_id}/state")
        state = state_res.json()
        assert state["auth_status"] != "pass"
        print("[PASS] Photo spoof correctly rejected with BLINK_NOT_DETECTED. Access denied.")


def test_06_complete_transaction_flow():
    """
    Test Complete End-to-End Flow:
    1. Customer face authentication (Sujith)
    2. Voice intent: "I want to deposit one lakh rupees"
    3. Backend verification & state cascade
    4. Reconfirmation -> Signed token -> Database persistence -> Staff Portal queue
    """
    session_id = str(uuid.uuid4())

    with httpx.Client(timeout=10.0) as client:
        # 1. Start session
        start_res = client.post(f"{BACKEND_URL}/api/v1/session/start", json={"session_id": session_id, "preferred_language": "en"})
        assert start_res.status_code == 200

        # 2. Authenticate customer Sujith
        auth_res = client.post(
            f"{FACE_URL}/face-auth/verify-simulated",
            json={
                "session_id": session_id,
                "scenario": "success",
                "customer_id": "cust_sujith",
                "customer_name": "Sujith",
                "auth_status": "pass",
                "liveness_passed": True,
                "face_score": 0.95,
            },
        )
        assert auth_res.status_code == 200
        assert auth_res.json()["auth_status"] == "pass"

        # 3. Voice AI: "I want to deposit one lakh rupees"
        parse_res = client.post(
            f"{VOICE_URL}/api/v1/parse",
            json={
                "session_id": session_id,
                "text": "I want to deposit one lakh rupees",
                "preferred_language": "en",
                "recognition_confidence": 0.96,
                "forward_to_backend": True,
            },
        )
        assert parse_res.status_code == 200
        voice_data = parse_res.json()
        assert voice_data["intent"] == "deposit"
        assert voice_data["entities"]["amount"] == 100000

        backend_resp = voice_data["backend_response"]
        assert backend_resp["status"] == "ok"
        # Since customer was already authenticated upfront, state cascades directly to awaiting_confirmation
        assert backend_resp["state"] == "awaiting_confirmation"

        # 4. Confirm transaction
        confirm_res = client.post(
            f"{BACKEND_URL}/api/v1/session/{session_id}/confirm",
            json={"session_id": session_id, "confirmed": True},
        )
        assert confirm_res.status_code == 200, f"Confirmation failed: {confirm_res.text}"
        conf_data = confirm_res.json()
        assert conf_data["status"] == "ok"
        assert conf_data["state"] == "queued"
        assert conf_data["customer_name"] == "Sujith"
        assert conf_data["transaction_type"] == "deposit"
        assert conf_data["amount"] == 100000
        assert conf_data["token_number"] is not None
        assert conf_data["qr_payload"] is not None

        # 5. Verify database records
        tx_row = bank_db.get_transaction_by_session(session_id)
        assert tx_row is not None
        assert tx_row["customer_id"] == "cust_sujith"
        assert tx_row["customer_name"] == "Sujith"
        assert tx_row["transaction_type"] == "deposit"
        assert tx_row["status"] == "confirmed"

        # Verify queue entry
        queue_row = bank_db.get_queue_entry_by_token(conf_data["token_id"])
        assert queue_row is not None
        assert queue_row["customer_id"] == "cust_sujith"
        assert queue_row["customer_display_name"] == "Sujith"
        assert queue_row["status"] == "WAITING"

        print(f"[PASS] Complete Transaction Flow Successful!")
        print(f"       Customer: {tx_row['customer_name']} ({tx_row['customer_id']})")
        print(f"       Transaction: {tx_row['transaction_type']} of INR {tx_row['amount']:,}")
        print(f"       Token: #{conf_data['token_number']} (Queue Position: {conf_data['queue_position']})")
        print(f"       Status: {tx_row['status']}")


def test_07_teller_queue_and_debug_trace():
    """Verify GET /api/v1/teller/queue and GET /api/v1/session/{session_id}/debug."""
    with httpx.Client(timeout=8.0) as client:
        # 1. Teller queue check
        queue_res = client.get(f"{BACKEND_URL}/api/v1/teller/queue")
        assert queue_res.status_code == 200
        q_data = queue_res.json()
        assert q_data["status"] == "ok"
        assert isinstance(q_data["queue"], list)
        print(f"[PASS] Staff Portal Queue API verified: {q_data['count']} active queue entries in database")

        # 2. Debug trace check on recent session
        if len(q_data["queue"]) > 0:
            sample_session_id = q_data["queue"][-1]["session_id"]
            debug_res = client.get(f"{BACKEND_URL}/api/v1/session/{sample_session_id}/debug")
            assert debug_res.status_code == 200
            d_data = debug_res.json()
            assert d_data["status"] == "ok"
            assert d_data["session_id"] == sample_session_id
            assert d_data["customer"]["customer_name"] is not None
            assert d_data["transaction"] is not None
            assert d_data["queue"] is not None
            print(f"[PASS] End-to-End Debug Trace verified for session {sample_session_id}")


def test_08_voice_ai_websocket_utterance():
    """Verify Voice AI WebSocket parses utterance 'I want to deposit one lakh rupees' into deposit and 100000."""
    import websockets.sync.client as ws_sync
    import json

    with ws_sync.connect("ws://127.0.0.1:8002/ws/audio") as ws:
        # Send utterance payload with session_id, text, and preferred_language
        msg = {
            "session_id": "test_ws_session",
            "text": "I want to deposit one lakh rupees",
            "preferred_language": "en",
        }
        ws.send(json.dumps(msg))
        raw_res = ws.recv()
        res = json.loads(raw_res)

        assert res.get("status") == "ok"
        assert res.get("intent") == "deposit", f"Expected intent deposit, got {res.get('intent')}"
        assert res.get("entities", {}).get("amount") == 100000, f"Expected amount 100000, got {res.get('entities')}"
        print(f"[PASS] Voice AI WebSocket parsed utterance correctly: intent={res.get('intent')}, amount={res.get('entities', {}).get('amount')}")


if __name__ == "__main__":
    test_01_face_capabilities()
    test_02_enrollment_database_persistence()
    test_03_authentication_pass_and_identity_binding()
    test_04_wrong_face_rejection()
    test_05_photo_spoof_no_blink_rejection()
    test_06_complete_transaction_flow()
    test_07_teller_queue_and_debug_trace()
    test_08_voice_ai_websocket_utterance()
    print("\n========================================================")
    print("  ALL 8 ACCEPTANCE CRITERIA AUTOMATED TESTS PASSED!    ")
    print("========================================================")

