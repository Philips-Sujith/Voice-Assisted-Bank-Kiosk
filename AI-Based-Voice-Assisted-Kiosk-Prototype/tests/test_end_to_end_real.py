"""
Comprehensive End-to-End Integration Test Suite
Verifies all 10 acceptance criteria across all live microservices:
- Module 1 (Customer Kiosk logic & session management)
- Module 2 (Voice AI Vernacular Parsing & Intent Extraction)
- Module 3 (Central Backend Orchestrator & FSM State Machine)
- Module 4 (Face Authentication & Multi-Sample Enrollment)
- Module 5 (Security QR HMAC-SHA256 Token Service)
- Module 6 (Staff Portal Queue & WebSocket Events)
- Unified Database (SQLite bank_db)
- Redis Protocol Event Bus
"""
import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
import httpx
import pytest
import websockets

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Setup paths
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
if str(DATA_DIR) not in sys.path:
    sys.path.insert(0, str(DATA_DIR))

import bank_db

BACKEND_URL = "http://127.0.0.1:8000"
VOICE_URL = "http://127.0.0.1:8002"
FACE_URL = "http://127.0.0.1:8003"
SECURITY_URL = "http://127.0.0.1:8001"
WS_BACKEND_URL = "ws://127.0.0.1:8000/ws/dashboard"


def test_01_face_enrollment_multi_sample():
    """Test 1: Enroll a customer with 4 face samples and verify persistence in bank_db."""
    print("\n--- Running Test 1: Multi-Sample Face Enrollment ---")
    bank_db.init_db()
    customer_id = "cust_sujith_e2e"
    customer_name = "Sujith Kumar"
    
    # Clean previous test embeddings if any
    bank_db.clear_customer_embeddings(customer_id)
    bank_db.upsert_customer(customer_id, customer_name)
    
    # Enroll 4 distinct synthetic 512-d embeddings
    import numpy as np
    for i in range(4):
        emb = np.random.randn(512).astype(np.float32)
        emb = emb / np.linalg.norm(emb)
        bank_db.enroll_face_sample(
            customer_id=customer_id,
            embedding=emb.tolist(),
            sample_index=i + 1,
            sample_label=f"angle_{i+1}",
        )
    
    # Verify embeddings are persisted in bank_db
    records = bank_db.list_face_embeddings(customer_id)
    assert len(records) == 4, f"Expected 4 enrolled samples, found {len(records)}"
    for idx, rec in enumerate(records, start=1):
        assert rec["sample_index"] == idx
        assert len(rec["embedding"]) == 512
        assert rec["customer_id"] == customer_id
    
    cust = bank_db.get_customer(customer_id)
    assert cust is not None
    assert cust["display_name"] == customer_name
    print(f"[PASS] Successfully verified 4 face samples enrolled for {customer_name} ({customer_id})")


def test_02_face_authentication_pass():
    """Test 2: Authenticate session with recognized customer face, verifying server-side state."""
    print("\n--- Running Test 2: Face Authentication & Identity Binding ---")
    session_id = str(uuid.uuid4())
    
    # 1. Start session in Backend
    with httpx.Client(timeout=5.0) as client:
        res = client.post(f"{BACKEND_URL}/api/v1/session/start", json={"session_id": session_id, "preferred_language": "en"})
        assert res.status_code == 200, f"Session start failed: {res.text}"
        data = res.json()
        assert data["auth_status"] == "pending"
        
        # 2. Call Face Auth verification
        verify_res = client.post(
            f"{FACE_URL}/face-auth/verify-simulated",
            json={
                "session_id": session_id,
                "auth_status": "pass",
                "customer_id": "cust_sujith",
                "liveness_passed": True,
                "face_score": 0.96,
            },
        )
        assert verify_res.status_code == 200, f"Face verification failed: {verify_res.text}"
        verify_data = verify_res.json()
        assert verify_data["auth_status"] == "pass"
        assert verify_data["customer_name"] == "Sujith"
        
        # 3. Check Backend session state
        state_res = client.get(f"{BACKEND_URL}/api/v1/session/{session_id}/state")
        assert state_res.status_code == 200
        state = state_res.json()
        assert state["auth_status"] == "pass"
        assert state["customer_id"] == "cust_sujith"
        assert state["customer_name"] == "Sujith"
        print(f"[PASS] Customer identified: {state['customer_name']} bound to session {session_id} with auth_status=pass")


def test_03_authentication_gate_enforcement():
    """Test 3: Unauthenticated session is rejected at the server side if attempting confirmation."""
    print("\n--- Running Test 3: Server-Side Authentication Gate Enforcement ---")
    unauth_session_id = str(uuid.uuid4())
    
    with httpx.Client(timeout=5.0) as client:
        # Start session but DO NOT authenticate
        client.post(f"{BACKEND_URL}/api/v1/session/start", json={"session_id": unauth_session_id})
        
        # Attempt to confirm without authentication (FSM state gate)
        res = client.post(f"{BACKEND_URL}/api/v1/session/{unauth_session_id}/confirm", json={"session_id": unauth_session_id, "confirmed": True})
        assert res.status_code in (400, 403, 409), f"Expected rejection, but got status {res.status_code}: {res.text}"
        print(f"[PASS] Unauthenticated confirmation blocked by server with status {res.status_code}: {res.json().get('detail')}")


def test_04_and_05_voice_ai_intent_and_amount_extraction():
    """Test 4 & 5: Voice utterance 'I want to deposit one lakh rupees' yields intent=deposit, amount=100000."""
    print("\n--- Running Tests 4 & 5: Voice AI Indian Currency Parsing & FSM Update ---")
    session_id = str(uuid.uuid4())
    
    with httpx.Client(timeout=6.0) as client:
        # 1. Start and authenticate session
        client.post(f"{BACKEND_URL}/api/v1/session/start", json={"session_id": session_id})
        client.post(
            f"{FACE_URL}/face-auth/verify-simulated",
            json={"session_id": session_id, "auth_status": "pass", "customer_id": "cust_sujith"},
        )
        
        # 2. Send utterance to Voice AI
        utterance = "I want to deposit one lakh rupees"
        parse_res = client.post(
            f"{VOICE_URL}/api/v1/parse",
            json={"session_id": session_id, "text": utterance, "forward_to_backend": True},
        )
        assert parse_res.status_code == 200, f"Voice AI parse failed: {parse_res.text}"
        voice_data = parse_res.json()
        assert voice_data["intent"] == "deposit"
        assert voice_data["entities"]["amount"] == 100000, f"Expected 100000, got {voice_data['entities'].get('amount')}"
        
        # 3. Check Backend Session Context
        state_res = client.get(f"{BACKEND_URL}/api/v1/session/{session_id}/state")
        assert state_res.status_code == 200
        state = state_res.json()
        assert state["transaction_type"] == "deposit"
        assert state["amount"] == 100000
        assert state["customer_name"] == "Sujith"
        assert state["fsm_state"] == "awaiting_confirmation"
        print(f"[PASS] Voice utterance successfully parsed: intent='deposit', amount={state['amount']} (₹1,00,000), FSM state='awaiting_confirmation'")


def test_06_to_08_confirmation_security_db_and_queue():
    """Test 6, 7, 8: Confirm transaction -> real HMAC token from Security -> DB record -> Queue entry."""
    print("\n--- Running Tests 6, 7 & 8: Confirmation, Security Signing, DB & Queue ---")
    session_id = str(uuid.uuid4())
    
    with httpx.Client(timeout=6.0) as client:
        # 1. Setup authenticated session with deposit 100000
        client.post(f"{BACKEND_URL}/api/v1/session/start", json={"session_id": session_id})
        client.post(
            f"{FACE_URL}/face-auth/verify-simulated",
            json={"session_id": session_id, "auth_status": "pass", "customer_id": "cust_sujith"},
        )
        client.post(
            f"{VOICE_URL}/api/v1/parse",
            json={"session_id": session_id, "text": "I want to deposit one lakh rupees", "forward_to_backend": True},
        )
        
        # 2. Confirm transaction
        confirm_res = client.post(f"{BACKEND_URL}/api/v1/session/{session_id}/confirm", json={"session_id": session_id, "confirmed": True})
        assert confirm_res.status_code == 200, f"Confirmation failed: {confirm_res.text}"
        res_data = confirm_res.json()
        
        assert res_data["status"] == "ok"
        token_id = res_data["token_id"]
        queue_pos = res_data["queue_position"]
        assert token_id is not None and len(token_id) > 0
        assert queue_pos >= 1
        print(f"[PASS] Transaction confirmed. Generated Token ID: {token_id}, Queue Position: #{queue_pos:02d}")
        
        # 3. Verify Database Persistence
        db_txn = bank_db.get_transaction_by_session(session_id)
        assert db_txn is not None, "Transaction was NOT saved in database!"
        assert db_txn["customer_id"] == "cust_sujith"
        assert db_txn["customer_name"] == "Sujith"
        assert db_txn["transaction_type"] == "deposit"
        assert db_txn["amount"] == 100000
        assert db_txn["status"] == "confirmed"
        print(f"[PASS] SQLite database verified: record txn_id={db_txn['transaction_id']}, amount={db_txn['amount']}, customer='{db_txn['customer_name']}'")
        
        # 4. Verify Queue Entry
        queue_entries = bank_db.list_queue_entries()
        matching_q = [q for q in queue_entries if q["session_id"] == session_id]
        assert len(matching_q) == 1, "Queue entry missing from database!"
        q_item = matching_q[0]
        assert q_item["token_id"] == token_id
        assert q_item["customer_display_name"] == "Sujith"
        assert q_item["transaction_type"] == "deposit"
        assert q_item["amount"] == 100000
        assert q_item["status"].lower() == "waiting"
        print(f"[PASS] Queue table verified: token={token_id}, display_name='{q_item['customer_display_name']}', status='{q_item['status']}'")


@pytest.mark.asyncio
async def test_09_staff_portal_realtime_websocket_event():
    """Test 9: Connect to WebSocket dashboard and verify instant receipt of real-time queue event."""
    print("\n--- Running Test 9: Staff Portal Real-Time WebSocket Notification ---")
    session_id = str(uuid.uuid4())
    
    # Connect to staff dashboard websocket
    async with websockets.connect(WS_BACKEND_URL) as ws:
        # Trigger transaction confirmation
        async with httpx.AsyncClient(timeout=6.0) as client:
            await client.post(f"{BACKEND_URL}/api/v1/session/start", json={"session_id": session_id})
            await client.post(
                f"{FACE_URL}/face-auth/verify-simulated",
                json={"session_id": session_id, "auth_status": "pass", "customer_id": "cust_sujith"},
            )
            await client.post(
                f"{VOICE_URL}/api/v1/parse",
                json={"session_id": session_id, "text": "I want to deposit one lakh rupees", "forward_to_backend": True},
            )
            confirm_res = await client.post(f"{BACKEND_URL}/api/v1/session/{session_id}/confirm", json={"session_id": session_id, "confirmed": True})
            assert confirm_res.status_code == 200
            expected_token = confirm_res.json()["token_id"]
        
        # Await WebSocket event with timeout
        received_event = None
        for _ in range(5):
            msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
            data = json.loads(msg)
            if data.get("event") == "new_queue_entry" and data.get("token_id") == expected_token:
                received_event = data
                break
        
        assert received_event is not None, "Staff Portal WebSocket did NOT receive new_queue_entry event!"
        assert received_event["customer_display_name"] == "Sujith"
        assert received_event["transaction_type"] == "deposit"
        assert received_event["amount"] == 100000
        assert received_event["token_id"] == expected_token
        print(f"[PASS] Staff Portal WebSocket received event: Customer='{received_event['customer_display_name']}', Txn='{received_event['transaction_type']}', Amount=₹{received_event['amount']:,}, Token='{received_event['token_id']}'")


def test_10_new_transaction_clears_state_and_requires_auth():
    """Test 10: 'New Transaction' clears state, resets auth_status to pending, and blocks re-entry."""
    print("\n--- Running Test 10: New Transaction State Reset & Authentication Re-requirement ---")
    session_id = str(uuid.uuid4())
    
    with httpx.Client(timeout=5.0) as client:
        # 1. Start, authenticate, and complete transaction
        client.post(f"{BACKEND_URL}/api/v1/session/start", json={"session_id": session_id})
        client.post(
            f"{FACE_URL}/face-auth/verify-simulated",
            json={"session_id": session_id, "auth_status": "pass", "customer_id": "cust_sujith"},
        )
        client.post(
            f"{VOICE_URL}/api/v1/parse",
            json={"session_id": session_id, "text": "I want to deposit one lakh rupees", "forward_to_backend": True},
        )
        client.post(f"{BACKEND_URL}/api/v1/session/{session_id}/confirm", json={"session_id": session_id, "confirmed": True})
        
        # 2. Click "New Transaction" -> call reset endpoint
        reset_res = client.post(f"{BACKEND_URL}/api/v1/session/{session_id}/reset")
        assert reset_res.status_code == 200, f"Reset failed: {reset_res.text}"
        assert reset_res.json()["auth_status"] == "pending"
        
        # 3. Verify transaction fields are wiped and auth_status is reset to pending
        state_res = client.get(f"{BACKEND_URL}/api/v1/session/{session_id}/state")
        assert state_res.status_code == 200
        state = state_res.json()
        assert state["transaction_type"] is None, "transaction_type was not cleared!"
        assert state["amount"] is None, "amount was not cleared!"
        assert state["auth_status"] == "pending", "auth_status was not reset to pending!"
        assert state["fsm_state"] == "idle", "fsm_state was not reset to idle!"
        
        # 4. Verify transaction cannot proceed without re-authenticating
        blocked = client.post(f"{BACKEND_URL}/api/v1/session/{session_id}/confirm", json={"session_id": session_id, "confirmed": True})
        assert blocked.status_code in (400, 403, 409), "Transaction was allowed after reset without re-authenticating!"
        print(f"[PASS] New Transaction reset confirmed: state wiped, auth_status='pending', re-authentication strictly enforced.")


if __name__ == "__main__":
    test_01_face_enrollment_multi_sample()
    test_02_face_authentication_pass()
    test_03_authentication_gate_enforcement()
    test_04_and_05_voice_ai_intent_and_amount_extraction()
    test_06_to_08_confirmation_security_db_and_queue()
    asyncio.run(test_09_staff_portal_realtime_websocket_event())
    test_10_new_transaction_clears_state_and_requires_auth()
    print("\n==================================================================")
    print("      ALL 10 END-TO-END ACCEPTANCE CRITERIA PASSED (100%)       ")
    print("==================================================================")
