"""
Unified Launcher & Process Lifecycle Manager for Voice-Assisted Banking Kiosk
Controls startup, health checking, browser launching, and clean process termination.
Fully portable across Windows paths, drives, and directory names (including spaces).
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

# Dynamically determine project root relative to this script
ROOT = Path(__file__).resolve().parent

# Support either flat or nested directory layout
if (ROOT / "AI-Based-Voice-Assisted-Kiosk-Prototype").exists():
    REPO_ROOT = ROOT / "AI-Based-Voice-Assisted-Kiosk-Prototype"
else:
    REPO_ROOT = ROOT

if (ROOT / "module-repos" / "Gopika_Module").exists():
    KIOSK_ROOT = ROOT / "module-repos" / "Gopika_Module"
elif (ROOT.parent / "module-repos" / "Gopika_Module").exists():
    KIOSK_ROOT = ROOT.parent / "module-repos" / "Gopika_Module"
elif (REPO_ROOT / "module1_customer_kiosk").exists():
    KIOSK_ROOT = REPO_ROOT / "module1_customer_kiosk"
else:
    KIOSK_ROOT = ROOT / "module-repos" / "Gopika_Module"

STAFF_ROOT = REPO_ROOT / "module6_staff_portal"

RUNTIME_DIR = ROOT / "runtime"
PID_FILE = RUNTIME_DIR / "demo_pids.json"
LOGS_DIR = RUNTIME_DIR / "logs"

# Dynamically discover npm executable
NPM_BIN = shutil.which("npm.cmd") or shutil.which("npm") or "npm"

SERVICES = [
    {
        "id": "redis",
        "name": "Redis Broker",
        "cmd": [sys.executable, str(ROOT / "run_redis.py")],
        "cwd": str(ROOT),
        "port": 6379,
        "type": "tcp",
    },
    {
        "id": "security_qr",
        "name": "Module 5: Security QR",
        "cmd": [sys.executable, "app.py"],
        "cwd": str(REPO_ROOT / "module5_security"),
        "port": 8001,
        "url": "http://127.0.0.1:8001/health",
        "type": "http",
    },
    {
        "id": "face_auth",
        "name": "Module 4: Face Auth",
        "cmd": [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8003"],
        "cwd": str(REPO_ROOT / "module4_face_auth"),
        "port": 8003,
        "url": "http://127.0.0.1:8003/health",
        "type": "http",
    },
    {
        "id": "backend",
        "name": "Module 3: Central Backend",
        "cmd": [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        "cwd": str(REPO_ROOT / "module3_backend"),
        "port": 8000,
        "url": "http://127.0.0.1:8000/docs",
        "type": "http",
    },
    {
        "id": "voice_ai",
        "name": "Module 2: Voice AI",
        "cmd": [sys.executable, "server.py"],
        "cwd": str(REPO_ROOT / "module2_voice"),
        "port": 8002,
        "url": "http://127.0.0.1:8002/health",
        "type": "http",
    },
    {
        "id": "staff_portal",
        "name": "Module 6: Staff Portal",
        "cmd": [NPM_BIN, "run", "dev"],
        "cwd": str(STAFF_ROOT),
        "port": 5174,
        "url": "http://localhost:5174",
        "type": "http",
    },
    {
        "id": "customer_kiosk",
        "name": "Module 1: Customer Kiosk",
        "cmd": [NPM_BIN, "run", "dev"],
        "cwd": str(KIOSK_ROOT),
        "port": 5173,
        "url": "http://localhost:5173",
        "type": "http",
    },
]

DEMO_PORTS = [s["port"] for s in SERVICES]


def is_port_in_use(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False


def check_health(svc: dict) -> bool:
    if svc["type"] == "tcp":
        return is_port_in_use(svc["port"])
    elif svc["type"] == "http":
        try:
            req = urllib.request.Request(svc["url"], headers={"User-Agent": "BankingKioskHealth/1.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status in (200, 301, 302, 307)
        except Exception:
            return False
    return False


def save_pids(pid_map: dict[str, int]):
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with open(PID_FILE, "w", encoding="utf-8") as f:
        json.dump(pid_map, f, indent=2)


def load_pids() -> dict[str, int]:
    if not PID_FILE.exists():
        return {}
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def kill_pid_tree(pid: int):
    """Terminates process and all its children safely."""
    try:
        import psutil
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            try:
                child.kill()
            except Exception:
                pass
        parent.kill()
    except Exception:
        # Fallback to Windows taskkill
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def kill_process_on_port(port: int):
    """Kills process listening on a specific demo port if still lingering."""
    try:
        import psutil
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == port and conn.pid:
                kill_pid_tree(conn.pid)
    except Exception:
        pass


def stop_services():
    print("========================================")
    print("   STOPPING BANKING KIOSK SERVICES...   ")
    print("========================================")

    pids = load_pids()
    if pids:
        for name, pid in pids.items():
            print(f"Stopping {name} (PID {pid})...")
            kill_pid_tree(pid)

    # Secondary sweep on demo ports to ensure clean release
    for port in DEMO_PORTS:
        if is_port_in_use(port):
            kill_process_on_port(port)

    # Clean up PID file
    if PID_FILE.exists():
        try:
            PID_FILE.unlink()
        except Exception:
            pass

    time.sleep(1)

    print("\n========================================")
    print("      BANKING KIOSK DEMO STOPPED        ")
    print("========================================")
    print("All demo services have been stopped cleanly.")
    print("You can run START_DEMO.bat again anytime.\n")


def start_services():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    started_pids: dict[str, int] = {}
    proc_list: list[tuple[dict, subprocess.Popen]] = []

    print("[6/7] Starting backend & frontend services...")

    for svc in SERVICES:
        name = svc["name"]
        port = svc["port"]

        if is_port_in_use(port):
            print(f"  [OK] {name} is already running on port {port}.")
            continue

        safe_name = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")
        log_path = LOGS_DIR / f"{safe_name}.log"
        log_file = open(log_path, "a", encoding="utf-8")

        try:
            # Determine shell flag on Windows for .cmd or .bat files
            first_arg = str(svc["cmd"][0]).lower()
            is_cmd = sys.platform == "win32" and (
                first_arg.endswith(".cmd")
                or first_arg.endswith(".bat")
                or "npm" in first_arg
            )
            proc = subprocess.Popen(
                svc["cmd"],
                cwd=svc["cwd"],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                shell=is_cmd,
            )
            started_pids[svc["id"]] = proc.pid
            proc_list.append((svc, proc))
            print(f"  [Started] {name.ljust(28)} (PID {proc.pid})")
        except Exception as e:
            print(f"[ERROR] Failed to start {name}: {e}")

    save_pids(started_pids)

    # Health check wait loop
    print("\n[7/7] Waiting for services to become healthy...")
    time.sleep(2)

    all_healthy = True
    proc_map = {svc["id"]: proc for svc, proc in proc_list}

    for svc in SERVICES:
        name = svc["name"]
        port = svc["port"]
        safe_name = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")
        proc = proc_map.get(svc["id"])
        healthy = False

        # Poll up to 25 seconds for each service, failing fast if process died
        for _ in range(25):
            if proc and proc.poll() is not None:
                # Process has already exited
                break
            if check_health(svc):
                healthy = True
                break
            time.sleep(1)

        if healthy:
            print(f"  [OK]   {name.ljust(28)} -> ONLINE on port {port}")
        else:
            all_healthy = False
            if proc and proc.poll() is not None:
                print(f"  [FAIL] {name.ljust(28)} -> EXITED (Code {proc.poll()})")
                print(f"         Log: runtime/logs/{safe_name}.log")
            else:
                print(f"  [!]    {name.ljust(28)} -> TIMED OUT / PENDING on port {port}")

    if all_healthy:
        print("\n========================================")
        print("      BANKING KIOSK DEMO IS READY       ")
        print("========================================")
        print("")
        print("Customer Kiosk:  http://localhost:5173")
        print("Face Enrollment: http://localhost:5173/#/face-enrollment")
        print("Staff Portal:    http://localhost:5174")
        print("")
        print("========================================")
        print("\nOpening Customer Kiosk in your browser...")
        try:
            webbrowser.open("http://localhost:5173")
        except Exception as e:
            print(f"Notice: Could not automatically open browser ({e}).")
            print("Please manually visit http://localhost:5173")
    else:
        print("\n========================================")
        print("    BANKING KIOSK DEMO — STATUS REPORT  ")
        print("========================================")
        print("[NOTICE] One or more services failed to start or exited.")
        print("Please check the log files in runtime/logs/ for details.\n")

    print("\nDemo monitor active.")
    print("Customer Kiosk:  http://localhost:5173")
    print("Face Enrollment: http://localhost:5173/#/face-enrollment")
    print("Staff Portal:    http://localhost:5174")
    print("\nUse STOP_DEMO.bat when you are finished.")
    print("(Press Ctrl+C to terminate services from this window)\n")

    def handle_signal(sig=None, frame=None):
        print("\nShutdown signal received. Stopping demo...")
        stop_services()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    reported_exits = set()
    try:
        while True:
            time.sleep(2)
            # Check if any started process exited unexpectedly (deduplicated reporting)
            for svc, proc in proc_list:
                ret = proc.poll()
                if ret is not None and svc["id"] not in reported_exits:
                    reported_exits.add(svc["id"])
                    safe_name = "".join(c if c.isalnum() else "_" for c in svc["name"].lower()).strip("_")
                    print(f"\n[ALERT] {svc['name']} (PID {proc.pid}) exited with code {ret}!")
                    print(f"        Log: runtime/logs/{safe_name}.log\n")
    except KeyboardInterrupt:
        handle_signal()


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "start"
    if action == "stop":
        stop_services()
    else:
        start_services()
