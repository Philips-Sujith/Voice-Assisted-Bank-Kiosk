"""
Comprehensive End-to-End Multi-Module System Integration Test Suite
Executes live HTTP and WebSocket interactions across all microservices:
- Module 2: Vernacular Voice AI (Port 8002)
- Module 3: Central Backend Orchestrator (Port 8000)
- Module 4: Face Biometric Authentication (Port 8003)
- Module 5: Security QR Signing Service (Port 8001)
- Redis Protocol Broker (Port 6379)
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import unittest
import uuid
from pathlib import Path
import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PROJECT_ROOT
BANK_ROOT = PROJECT_ROOT.parent

SERVICES_CONFIG = [
    {
        "name": "Redis Broker",
        "cmd": [sys.executable, str(BANK_ROOT / "run_redis.py")],
        "cwd": str(BANK_ROOT),
        "port": 6379,
        "type": "tcp",
    },
    {
        "name": "Module 5: Security QR",
        "cmd": [sys.executable, "app.py"],
        "cwd": str(REPO_ROOT / "module5_security"),
        "port": 8001,
        "url": "http://127.0.0.1:8001/health",
        "type": "http",
    },
    {
        "name": "Module 4: Face Auth",
        "cmd": [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8003"],
        "cwd": str(REPO_ROOT / "module4_face_auth"),
        "port": 8003,
        "url": "http://127.0.0.1:8003/health",
        "type": "http",
    },
    {
        "name": "Module 3: Central Backend",
        "cmd": [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        "cwd": str(REPO_ROOT / "module3_backend"),
        "port": 8000,
        "url": "http://127.0.0.1:8000/docs",
        "type": "http",
    },
    {
        "name": "Module 2: Voice AI",
        "cmd": [sys.executable, "server.py"],
        "cwd": str(REPO_ROOT / "module2_voice"),
        "port": 8002,
        "url": "http://127.0.0.1:8002/health",
        "type": "http",
    },
]

spawned_procs: list[subprocess.Popen] = []


def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for_service(port: int, proc: subprocess.Popen | None = None, max_retries: int = 35) -> bool:
    for _ in range(max_retries):
        if is_port_open(port):
            return True
        if proc is not None and proc.poll() is not None:
            return False
        time.sleep(1)
    return False


class TestFullSystemIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure all services are up and running
        for svc in SERVICES_CONFIG:
            port = svc["port"]
            if not is_port_open(port):
                print(f"[Setup] Starting {svc['name']} on port {port}...")
                p = subprocess.Popen(
                    svc["cmd"],
                    cwd=svc["cwd"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                spawned_procs.append(p)
                if not wait_for_service(port, proc=p):
                    raise RuntimeError(f"Could not start service {svc['name']} on port {port} (poll={p.poll()})")
            else:
                print(f"[Setup] {svc['name']} already online on port {port}.")

        cls.http = httpx.Client(timeout=10.0)
        cls.sec_base = "http://127.0.0.1:8001"
        cls.face_base = "http://127.0.0.1:8003"
        cls.backend_base = "http://127.0.0.1:8000"
        cls.voice_base = "http://127.0.0.1:8002"

    @classmethod
    def tearDownClass(cls):
        cls.http.close()
        for p in spawned_procs:
            try:
                p.terminate()
                p.wait(timeout=2)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass

    def test_01_service_health_checks(self):
        """Verify all microservice health endpoints return status ok."""
        # Module 2 Voice AI
        v_resp = self.http.get(f"{self.voice_base}/health")
        self.assertEqual(v_resp.status_code, 200)
        self.assertEqual(v_resp.json()["status"], "ok")

        # Module 3 Central Backend
        b_resp = self.http.get(f"{self.backend_base}/docs")
        self.assertEqual(b_resp.status_code, 200)

        # Module 4 Face Auth
        f_resp = self.http.get(f"{self.face_base}/health")
        self.assertEqual(f_resp.status_code, 200)
        self.assertEqual(f_resp.json()["status"], "ok")

        # Module 5 Security QR
        s_resp = self.http.get(f"{self.sec_base}/health")
        self.assertEqual(s_resp.status_code, 200)
        self.assertEqual(s_resp.json()["status"], "ok")

    def test_02_module5_hmac_signing_contract(self):
        """Verify Module 5 signs payloads and validates request schemas."""
        session_id = str(uuid.uuid4())
        req = {
            "session_id": session_id,
            "customer_id": "acc_cust_8821",
            "transaction_type": "withdraw",
            "amount": 5000,
            "timestamp": "2026-09-04T12:00:00Z",
        }
        res = self.http.post(f"{self.sec_base}/sign", json=req)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("token_id", data)
        self.assertIn("hmac_signature", data)
        self.assertIn("qr_payload", data)
        self.assertIn("expires_at", data)

    def test_03_module2_vernacular_intent_parsing(self):
        """Verify Module 2 parses English, Tamil, Tanglish and applies confidence logic."""
        session_id = str(uuid.uuid4())

        # English withdrawal
        res_en = self.http.post(
            f"{self.voice_base}/api/v1/parse",
            json={"session_id": session_id, "text": "Withdraw 5000 rupees", "preferred_language": "en", "forward_to_backend": False},
        )
        self.assertEqual(res_en.status_code, 200)
        data_en = res_en.json()
        self.assertEqual(data_en["intent"], "withdraw")
        self.assertEqual(data_en["entities"]["amount"], 5000)
        self.assertTrue(data_en["requires_auth"])
        self.assertGreaterEqual(data_en["confidence"], 0.7)

        # Tamil withdrawal
        res_ta = self.http.post(
            f"{self.voice_base}/api/v1/parse",
            json={"session_id": session_id, "text": "ஐந்தாயிரம் ரூபாய் எடுக்க வேண்டும்", "preferred_language": "ta", "forward_to_backend": False},
        )
        self.assertEqual(res_ta.status_code, 200)
        data_ta = res_ta.json()
        self.assertEqual(data_ta["intent"], "withdraw")
        self.assertEqual(data_ta["entities"]["amount"], 5000)
        self.assertTrue(data_ta["requires_auth"])

        # Low confidence (< 0.7) on ambiguous phrase
        res_low = self.http.post(
            f"{self.voice_base}/api/v1/parse",
            json={"session_id": session_id, "text": "I want money please", "preferred_language": "en", "forward_to_backend": False},
        )
        self.assertEqual(res_low.status_code, 200)
        data_low = res_low.json()
        self.assertLess(data_low["confidence"], 0.7)

    def test_04_end_to_end_authenticated_withdrawal_flow(self):
        """
        Complete Real-World Customer & Staff Flow:
        1. Kiosk Frontend creates session_id.
        2. Customer speaks: "Withdraw 5000 rupees".
        3. Voice AI forwards intent to Backend Orchestrator -> FSM: awaiting_auth.
        4. Customer verifies face at Face Auth -> forwards to Backend -> FSM: awaiting_confirmation.
        5. Customer confirms on Kiosk -> Backend calls Security Service -> FSM: queued.
        6. Teller queries token verification -> status ok.
        7. Teller calls customer -> teller completes transaction -> FSM: completed.
        8. Token re-verification returns 409 Conflict (One-time token enforcement).
        """
        session_id = str(uuid.uuid4())

        # 1 & 2: Voice AI parses and forwards to Backend
        voice_res = self.http.post(
            f"{self.voice_base}/api/v1/parse",
            json={
                "session_id": session_id,
                "text": "Withdraw 5000 rupees",
                "preferred_language": "en",
                "forward_to_backend": True,
            },
        )
        self.assertEqual(voice_res.status_code, 200)
        v_data = voice_res.json()
        self.assertEqual(v_data["intent"], "withdraw")
        backend_voice_resp = v_data["backend_response"]
        self.assertEqual(backend_voice_resp["status"], "ok")
        self.assertEqual(backend_voice_resp.get("state") or backend_voice_resp.get("current_state"), "awaiting_auth")

        # 3: Biometric Face Verification
        face_res = self.http.post(
            f"{self.face_base}/face-auth/verify-simulated",
            json={
                "session_id": session_id,
                "auth_status": "pass",
                "customer_id": "acc_cust_8821",
                "forward_to_backend": True,
            },
        )
        self.assertEqual(face_res.status_code, 200)
        face_data = face_res.json()
        self.assertEqual(face_data["status"], "ok")
        backend_face_resp = face_data.get("backend_response", {})
        self.assertEqual(backend_face_resp.get("state") or backend_face_resp.get("current_state"), "awaiting_confirmation")

        # 4: Customer Confirms on Kiosk
        conf_res = self.http.post(
            f"{self.voice_base}/api/v1/confirm",
            json={"session_id": session_id, "confirmed": True},
        )
        self.assertEqual(conf_res.status_code, 200)
        conf_data = conf_res.json()
        self.assertEqual(conf_data["status"], "ok")
        self.assertEqual(conf_data.get("state") or conf_data.get("current_state"), "queued")
        self.assertIn("token_id", conf_data)
        self.assertIn("token_number", conf_data)
        self.assertIn("qr_payload", conf_data)

        token_id = conf_data["token_id"]

        # 5: Teller verifies token at counter
        verify_res = self.http.get(f"{self.backend_base}/api/v1/token/{token_id}/verify")
        self.assertEqual(verify_res.status_code, 200)
        verify_data = verify_res.json()
        self.assertEqual(verify_data["status"], "ok")
        self.assertEqual(verify_data["amount"], 5000)
        self.assertEqual(verify_data["transaction_type"], "withdraw")

        # 6: Teller calls customer
        call_res = self.http.post(f"{self.backend_base}/api/v1/teller/{token_id}/call", json={"teller_id": "T-01"})
        self.assertEqual(call_res.status_code, 200)

        # 7: Teller completes transaction
        comp_res = self.http.post(f"{self.backend_base}/api/v1/teller/{token_id}/complete")
        self.assertEqual(comp_res.status_code, 200)

        # 8: One-time token use enforcement
        reuse_res = self.http.get(f"{self.backend_base}/api/v1/token/{token_id}/verify")
        self.assertEqual(reuse_res.status_code, 409)

    def test_05_non_auth_flow_tamil_balance_inquiry(self):
        """Verify non-auth balance check directly transitions to awaiting_confirmation."""
        session_id = str(uuid.uuid4())

        # Utterance: "என் கணக்கு இருப்பை பார்க்க வேண்டும்" (ta)
        v_res = self.http.post(
            f"{self.voice_base}/api/v1/parse",
            json={
                "session_id": session_id,
                "text": "என் கணக்கு இருப்பை பார்க்க வேண்டும்",
                "preferred_language": "ta",
                "forward_to_backend": True,
            },
        )
        self.assertEqual(v_res.status_code, 200)
        b_data = v_res.json()["backend_response"]
        self.assertEqual(b_data["status"], "ok")
        self.assertEqual(b_data.get("state") or b_data.get("current_state"), "awaiting_confirmation")

        # Customer confirms
        conf_res = self.http.post(
            f"{self.backend_base}/api/v1/session/{session_id}/confirm",
            json={"session_id": session_id, "confirmed": True},
        )
        self.assertEqual(conf_res.status_code, 200)
        self.assertEqual(conf_res.json().get("state") or conf_res.json().get("current_state"), "queued")


if __name__ == "__main__":
    unittest.main()
