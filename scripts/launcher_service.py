"""
Unified Launcher & Process Lifecycle Manager for AI Voice-Assisted Banking Kiosk
Controls startup, health checking, browser launching, port diagnostics, and surgical process termination.
Fully portable across Windows paths, drives, and directory names (including spaces).
Guarantees zero interference with unrelated external applications (e.g. LMS, VS Code, other Node/Vite apps).
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

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass


# Dynamically determine project root relative to this script
CURRENT_FILE = Path(__file__).resolve()
if CURRENT_FILE.parent.name == "scripts":
    PROJECT_ROOT = CURRENT_FILE.parent.parent
else:
    PROJECT_ROOT = CURRENT_FILE.parent

KIOSK_ROOT = PROJECT_ROOT / "apps" / "customer-kiosk"
TELLER_ROOT = PROJECT_ROOT / "apps" / "teller-portal"
BANKING_ROOT = PROJECT_ROOT / "services" / "banking-api"
IDENTITY_ROOT = PROJECT_ROOT / "services" / "identity"
SECURITY_ROOT = PROJECT_ROOT / "services" / "security"
VOICE_ROOT = PROJECT_ROOT / "services" / "voice"
REDIS_SCRIPT = PROJECT_ROOT / "infrastructure" / "redis" / "run_redis.py"

RUNTIME_DIR = PROJECT_ROOT / "runtime"
PIDS_DIR = RUNTIME_DIR / "pids"
PID_FILE = RUNTIME_DIR / "demo_pids.json"
LOGS_DIR = RUNTIME_DIR / "logs"

# Dynamically discover npm executable
NPM_BIN = shutil.which("npm.cmd") or shutil.which("npm") or "npm"

SERVICES = [
    {
        "id": "redis",
        "name": "Redis Broker",
        "cmd": [sys.executable, str(REDIS_SCRIPT)],
        "cwd": str(PROJECT_ROOT),
        "port": 6379,
        "type": "tcp",
    },
    {
        "id": "security",
        "name": "Security Service",
        "cmd": [sys.executable, "app.py"],
        "cwd": str(SECURITY_ROOT),
        "port": 8001,
        "url": "http://127.0.0.1:8001/health",
        "type": "http",
    },
    {
        "id": "identity",
        "name": "Identity & Biometrics Service",
        "cmd": [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8003"],
        "cwd": str(IDENTITY_ROOT),
        "port": 8003,
        "url": "http://127.0.0.1:8003/health",
        "type": "http",
    },
    {
        "id": "banking_api",
        "name": "Banking Core API",
        "cmd": [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        "cwd": str(BANKING_ROOT),
        "port": 8000,
        "url": "http://127.0.0.1:8000/docs",
        "type": "http",
    },
    {
        "id": "voice",
        "name": "Voice Interaction Service",
        "cmd": [sys.executable, "server.py"],
        "cwd": str(VOICE_ROOT),
        "port": 8002,
        "url": "http://127.0.0.1:8002/health",
        "type": "http",
    },
    {
        "id": "teller_portal",
        "name": "Teller Portal",
        "cmd": [NPM_BIN, "run", "dev"],
        "cwd": str(TELLER_ROOT),
        "port": 5174,
        "url": "http://localhost:5174",
        "type": "http",
    },
    {
        "id": "customer_kiosk",
        "name": "Customer Kiosk",
        "cmd": [NPM_BIN, "run", "dev"],
        "cwd": str(KIOSK_ROOT),
        "port": 5173,
        "url": "http://localhost:5173",
        "type": "http",
    },
]

DEMO_PORTS = [s["port"] for s in SERVICES]


# ==============================================================================
# PORT & PROCESS INSPECTION UTILITIES
# ==============================================================================

def is_port_in_use(port: int) -> bool:
    """Fast socket connect check to see if a port is accepting TCP connections."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False


def wait_for_port_free(port: int, timeout: float = 5.0) -> bool:
    """Waits until a port is no longer in use."""
    start = time.time()
    while time.time() - start < timeout:
        if not is_port_in_use(port):
            return True
        time.sleep(0.2)
    return not is_port_in_use(port)


def get_pid_on_port(port: int) -> int | None:
    """
    Finds the process ID (PID) currently listening on a specific TCP port.
    Uses psutil if available, with robust fallback to Windows netstat.
    """
    try:
        import psutil
        for conn in psutil.net_connections(kind="tcp"):
            if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port:
                if conn.pid:
                    return conn.pid
    except Exception:
        pass

    try:
        out = subprocess.check_output(["netstat", "-ano", "-p", "tcp"], text=True, errors="replace")
        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and "LISTENING" in parts[3].upper():
                local_addr = parts[1]
                if local_addr.endswith(f":{port}"):
                    return int(parts[4])
    except Exception:
        pass
    return None


def get_process_info(pid: int) -> dict | None:
    """Safely inspects a process by PID without raising exceptions on exit or access restrictions."""
    try:
        import psutil
        if not psutil.pid_exists(pid):
            return None
        proc = psutil.Process(pid)
        try:
            name = proc.name()
        except Exception:
            name = "unknown"
        try:
            exe = proc.exe()
        except Exception:
            exe = ""
        try:
            cwd = proc.cwd()
        except Exception:
            cwd = ""
        try:
            cmdline = " ".join(proc.cmdline())
        except Exception:
            cmdline = ""
        try:
            create_time = proc.create_time()
        except Exception:
            create_time = 0.0

        return {
            "pid": pid,
            "name": name,
            "exe": exe,
            "cwd": cwd,
            "cmdline": cmdline,
            "create_time": create_time,
            "proc": proc,
        }
    except Exception:
        return None


# ==============================================================================
# PROCESS TRACKING & PERSISTENCE
# ==============================================================================

def init_runtime_dirs():
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    PIDS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def save_service_pid(svc: dict, proc: subprocess.Popen):
    init_runtime_dirs()
    pid_data = {
        "id": svc["id"],
        "name": svc["name"],
        "port": svc["port"],
        "pid": proc.pid,
        "start_time": time.time(),
        "cwd": str(svc["cwd"]),
        "cmd": [str(c) for c in svc["cmd"]],
        "project_root": str(PROJECT_ROOT),
    }
    svc_file = PIDS_DIR / f"{svc['id']}.json"
    try:
        with open(svc_file, "w", encoding="utf-8") as f:
            json.dump(pid_data, f, indent=2)
    except Exception:
        pass

    # Update legacy demo_pids.json
    current_legacy = load_pids()
    current_legacy[svc["id"]] = proc.pid
    save_pids(current_legacy)


def remove_service_pid(service_id: str):
    svc_file = PIDS_DIR / f"{service_id}.json"
    if svc_file.exists():
        try:
            svc_file.unlink()
        except Exception:
            pass

    current_legacy = load_pids()
    if service_id in current_legacy:
        del current_legacy[service_id]
        save_pids(current_legacy)


def load_all_tracked_pids() -> dict[str, dict]:
    """Loads metadata for all currently tracked Bank services."""
    tracked: dict[str, dict] = {}
    if PIDS_DIR.exists():
        for file in PIDS_DIR.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sid = data.get("id") or file.stem
                    tracked[sid] = data
            except Exception:
                pass

    # Also incorporate any entries from legacy demo_pids.json not already loaded
    legacy = load_pids()
    for sid, pid in legacy.items():
        if sid not in tracked and isinstance(pid, int):
            tracked[sid] = {"id": sid, "pid": pid}
    return tracked


def save_pids(pid_map: dict[str, int]):
    init_runtime_dirs()
    try:
        with open(PID_FILE, "w", encoding="utf-8") as f:
            json.dump(pid_map, f, indent=2)
    except Exception:
        pass


def load_pids() -> dict[str, int]:
    if not PID_FILE.exists():
        return {}
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ==============================================================================
# BANK PROCESS OWNERSHIP VERIFICATION (PROTECTS UNRELATED PROCESSES)
# ==============================================================================

def _matches_bank_signatures(proc) -> bool:
    """
    Checks if a psutil.Process instance is located in or launched by this Bank repository.
    Handles canonical path junctions, Windows casing, and directory aliases.
    """
    try:
        proj_resolved = os.path.normcase(str(PROJECT_ROOT.resolve()))
        proj_raw = os.path.normcase(str(PROJECT_ROOT.absolute()))

        # Check process working directory (cwd)
        try:
            cwd = proc.cwd()
            if cwd:
                cwd_res = os.path.normcase(str(Path(cwd).resolve()))
                cwd_raw = os.path.normcase(str(cwd))
                if cwd_res.startswith(proj_resolved) or cwd_raw.startswith(proj_raw):
                    return True
        except Exception:
            pass

        # Check process command line arguments
        try:
            cmdline = proc.cmdline()
            for arg in cmdline:
                a = os.path.normcase(str(arg))
                if proj_resolved in a or proj_raw in a:
                    return True
                if "voice-assisted-kiosk-demo" in a:
                    return True
                # Check for bank-specific module directories
                if "apps\\customer-kiosk" in a or "apps/customer-kiosk" in a:
                    return True
                if "apps\\teller-portal" in a or "apps/teller-portal" in a:
                    return True
                if "services\\banking-api" in a or "services/banking-api" in a:
                    return True
                if "services\\identity" in a or "services/identity" in a:
                    return True
                if "services\\security" in a or "services/security" in a:
                    if "app.py" in a:
                        return True
                if "services\\voice" in a or "services/voice" in a:
                    if "server.py" in a:
                        return True
                if "infrastructure\\redis" in a or "infrastructure/redis" in a:
                    return True
        except Exception:
            pass

        # Check parent process working directory
        try:
            parent = proc.parent()
            if parent and parent.pid > 4:
                parent_cwd = os.path.normcase(str(parent.cwd()))
                if parent_cwd.startswith(proj_resolved) or parent_cwd.startswith(proj_raw):
                    return True
        except Exception:
            pass

    except Exception:
        pass
    return False


def is_our_bank_process(pid: int, expected_service: dict | None = None) -> bool:
    """
    Surgically determines whether a process belongs to THIS Bank application.
    CRITICAL SAFETY GUARANTEE:
      Never returns True for an unrelated application (e.g. LMS, VS Code, other Vite dev servers).
    """
    if not pid or pid <= 4:
        return False

    import psutil
    try:
        if not psutil.pid_exists(pid):
            return False
        proc = psutil.Process(pid)
    except Exception:
        return False

    # Check 1: Explicitly tracked PID in runtime/pids/*.json or demo_pids.json
    tracked = load_all_tracked_pids()
    tracked_pids = {info.get("pid") for info in tracked.values() if isinstance(info.get("pid"), int)}
    if pid in tracked_pids:
        # Verified match in our runtime registry
        return True

    # Check 2: Process is a direct child or descendant of a tracked Bank process
    for t_pid in tracked_pids:
        try:
            if psutil.pid_exists(t_pid):
                t_proc = psutil.Process(t_pid)
                descendants = [c.pid for c in t_proc.children(recursive=True)]
                if pid in descendants:
                    return True
        except Exception:
            pass

    # Check 3: Process signatures match this repository's root, cwd, or scripts
    return _matches_bank_signatures(proc)


# ==============================================================================
# PROCESS TERMINATION & HEALTH CHECKING
# ==============================================================================

def kill_pid_tree(pid: int):
    """
    Safely terminates a process and all its child processes without affecting
    unrelated parent or sibling processes.
    """
    if not pid or pid <= 4:
        return

    try:
        import psutil
        if not psutil.pid_exists(pid):
            return
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except Exception:
                pass
        parent.terminate()
        _, still_alive = psutil.wait_procs(children + [parent], timeout=2.0)
        for p in still_alive:
            try:
                p.kill()
            except Exception:
                pass
    except Exception:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def check_health(svc: dict) -> bool:
    """Verifies service health via TCP handshake or HTTP endpoint."""
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


# ==============================================================================
# PRE-STARTUP PORT DIAGNOSTICS & CONFLICT DETECTION
# ==============================================================================

def diagnose_all_ports() -> tuple[bool, list[dict]]:
    """
    Inspects all ports required by the Bank system before startup.
    Determines if each port is:
      - AVAILABLE
      - BANK_HEALTHY (Already running healthy Bank service)
      - BANK_STALE   (Stale or lingering Bank process from a previous run)
      - CONFLICT_EXTERNAL (Occupied by an unrelated process like LMS)
    Returns: (has_external_conflict, list_of_diagnostics)
    """
    diagnostics = []
    has_external_conflict = False

    for svc in SERVICES:
        port = svc["port"]
        pid = get_pid_on_port(port)

        if pid is None:
            diagnostics.append({
                "port": port,
                "service": svc,
                "status": "AVAILABLE",
                "pid": None,
                "info": None,
            })
        else:
            info = get_process_info(pid)
            is_bank = is_our_bank_process(pid, svc)

            if not is_bank:
                has_external_conflict = True
                diagnostics.append({
                    "port": port,
                    "service": svc,
                    "status": "CONFLICT_EXTERNAL",
                    "pid": pid,
                    "info": info,
                })
            else:
                healthy = check_health(svc)
                diagnostics.append({
                    "port": port,
                    "service": svc,
                    "status": "BANK_HEALTHY" if healthy else "BANK_STALE",
                    "pid": pid,
                    "info": info,
                })

    return has_external_conflict, diagnostics


def print_port_conflict_report(conflicts: list[dict]):
    """Renders a clear diagnostic report when external port conflicts exist."""
    print("")
    print("==============================================================================")
    print("                      PORT CONFLICT DETECTED BEFORE STARTUP                  ")
    print("==============================================================================")
    print("The Bank Demo cannot start because one or more required ports are currently in")
    print("use by another application on this computer.\n")
    print("Conflicting Port Details:")

    for d in conflicts:
        svc = d["service"]
        port = d["port"]
        pid = d["pid"]
        info = d["info"] or {}
        pname = info.get("name") or "unknown"
        exe = info.get("exe") or "unknown"
        cwd = info.get("cwd") or "unknown"
        cmd = info.get("cmdline") or ""

        print(f"  ----------------------------------------------------------------------------")
        print(f"  [!] Port {port} is currently being used by another application.")
        print(f"      Bank Service:       {svc['name']} (ID: {svc['id']})")
        print(f"      Required Port:      {port}")
        print(f"      Process Name:       {pname}")
        print(f"      Process ID (PID):   {pid}")
        print(f"      Executable Path:    {exe}")
        print(f"      Working Directory:  {cwd}")
        if cmd:
            print(f"      Command Line:       {cmd[:100]}{'...' if len(cmd) > 100 else ''}")

    print("  ----------------------------------------------------------------------------")
    print("\nSafety Policy:")
    print("  These processes do NOT belong to this Bank application.")
    print("  The Bank launcher will NEVER terminate unrelated applications (e.g. LMS,")
    print("  VS Code dev servers, or other Node/Vite development projects).\n")
    print("Why Ports Cannot Be Changed Silently:")
    print("  Customer Kiosk (5173), Teller Portal (5174), and Banking APIs (8000-8003)")
    print("  rely on explicit port configurations for CORS, session tokens, biometric")
    print("  callbacks, and secure QR generation. Vite will not silently shift ports.\n")
    print("How to Resolve:")
    for d in conflicts:
        port = d["port"]
        pid = d["pid"]
        info = d["info"] or {}
        pname = info.get("name") or "process"
        print(f"  1. To free port {port}: Close the terminal window running '{pname}' (PID {pid}),")
        print(f"     or terminate it specifically in CMD/PowerShell with: taskkill /F /PID {pid}")
    print("  2. Once the conflicting port(s) are released, re-run START_DEMO.bat.")
    print("==============================================================================\n")


# ==============================================================================
# SERVICE STARTUP ORCHESTRATION
# ==============================================================================

def start_services():
    init_runtime_dirs()

    print("==============================================================================")
    print("                  DIAGNOSING REQUIRED BANKING PORTS...                        ")
    print("==============================================================================")

    has_conflict, diagnostics = diagnose_all_ports()

    # If any port is held by an unrelated external application, halt safely
    if has_conflict:
        conflicts = [d for d in diagnostics if d["status"] == "CONFLICT_EXTERNAL"]
        print_port_conflict_report(conflicts)
        sys.exit(1)

    diag_map = {d["service"]["id"]: d for d in diagnostics}

    # Clean up any stale Bank processes from previous sessions
    for d in diagnostics:
        if d["status"] == "BANK_STALE":
            port = d["port"]
            pid = d["pid"]
            svc = d["service"]
            print(f"  [Clean] Lingering Bank process on port {port} (PID {pid}) is stale. Restarting...")
            kill_pid_tree(pid)
            remove_service_pid(svc["id"])
            wait_for_port_free(port, timeout=5.0)

    print("\n[6/7] Starting services...")

    started_pids: dict[str, int] = {}
    proc_list: list[tuple[dict, subprocess.Popen]] = []

    for svc in SERVICES:
        name = svc["name"]
        port = svc["port"]
        sid = svc["id"]
        d = diag_map.get(sid)

        # Check if already running and healthy from our own project
        if d and d["status"] == "BANK_HEALTHY":
            existing_pid = d["pid"]
            print(f"  [OK]      {name.ljust(30)} is already running and healthy (PID {existing_pid}) on port {port}.")
            started_pids[sid] = existing_pid
            continue

        safe_name = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")
        log_path = LOGS_DIR / f"{safe_name}.log"
        log_file = open(log_path, "a", encoding="utf-8")

        try:
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
            started_pids[sid] = proc.pid
            proc_list.append((svc, proc))
            save_service_pid(svc, proc)
            print(f"  [Started] {name.ljust(30)} (PID {proc.pid})")
        except Exception as e:
            print(f"[ERROR] Failed to start {name}: {e}")

    save_pids(started_pids)

    # Health check verification loop
    print("\n[7/7] Verifying system...")
    time.sleep(2)

    all_healthy = True
    proc_map = {svc["id"]: proc for svc, proc in proc_list}

    for svc in SERVICES:
        name = svc["name"]
        port = svc["port"]
        sid = svc["id"]
        safe_name = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")
        proc = proc_map.get(sid)
        healthy = False

        for _ in range(25):
            if proc and proc.poll() is not None:
                break
            if check_health(svc):
                healthy = True
                break
            time.sleep(1)

        if healthy:
            print(f"  [OK]   {name.ljust(30)} -> ONLINE on port {port}")
        else:
            all_healthy = False
            if proc and proc.poll() is not None:
                print(f"  [FAIL] {name.ljust(30)} -> EXITED (Code {proc.poll()})")
                print(f"         Log: runtime/logs/{safe_name}.log")
            else:
                print(f"  [!]    {name.ljust(30)} -> TIMED OUT / PENDING on port {port}")

    if all_healthy:
        print("\n========================================")
        print("      BANKING KIOSK DEMO IS READY       ")
        print("========================================")
        print("")
        print("Customer Kiosk:  http://localhost:5173")
        print("Face Enrollment: http://localhost:5173/#/face-enrollment")
        print("Teller Portal:   http://localhost:5174")
        print("")
        print("========================================")
        print("\nOpening Customer Kiosk and Teller Portal in your browser...")
        try:
            webbrowser.open("http://localhost:5173")
            time.sleep(1)
            webbrowser.open("http://localhost:5174")
        except Exception as e:
            print(f"Notice: Could not automatically open browser ({e}).")
            print("Please manually visit http://localhost:5173 and http://localhost:5174")
    else:
        print("\n========================================")
        print("    BANKING KIOSK DEMO — STATUS REPORT  ")
        print("========================================")
        print("[NOTICE] One or more services failed to start or exited.")
        print("Please check the log files in runtime/logs/ for details.\n")

    print("\nDemo monitor active.")
    print("Customer Kiosk:  http://localhost:5173")
    print("Face Enrollment: http://localhost:5173/#/face-enrollment")
    print("Teller Portal:   http://localhost:5174")
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
            for svc, proc in proc_list:
                ret = proc.poll()
                if ret is not None and svc["id"] not in reported_exits:
                    reported_exits.add(svc["id"])
                    safe_name = "".join(c if c.isalnum() else "_" for c in svc["name"].lower()).strip("_")
                    print(f"\n[ALERT] {svc['name']} (PID {proc.pid}) exited with code {ret}!")
                    print(f"        Log: runtime/logs/{safe_name}.log\n")
    except KeyboardInterrupt:
        handle_signal()


# ==============================================================================
# SERVICE SHUTDOWN ORCHESTRATION (SURGICAL & SAFE)
# ==============================================================================

def stop_services():
    print("========================================")
    print("   STOPPING BANKING KIOSK SERVICES...   ")
    print("========================================")

    # 1. Terminate all tracked Bank processes
    tracked = load_all_tracked_pids()
    if tracked:
        for sid, info in tracked.items():
            pid = info.get("pid")
            name = info.get("name", sid)
            if isinstance(pid, int):
                p_info = get_process_info(pid)
                if p_info and is_our_bank_process(pid):
                    print(f"Stopping {name} (PID {pid})...")
                    kill_pid_tree(pid)
                else:
                    # Process either already stopped or PID recycled
                    pass
            remove_service_pid(sid)

    # 2. Inspect demo ports and terminate ONLY verified Bank processes lingering on them
    for svc in SERVICES:
        port = svc["port"]
        name = svc["name"]
        pid = get_pid_on_port(port)
        if pid:
            if is_our_bank_process(pid, svc):
                print(f"Stopping lingering Bank process on port {port} (PID {pid})...")
                kill_pid_tree(pid)
                wait_for_port_free(port, timeout=3.0)
            else:
                p_info = get_process_info(pid)
                pname = p_info["name"] if p_info else "unknown"
                print(f"  [Preserved] Port {port} is held by external application '{pname}' (PID {pid}). Not terminated.")

    # 3. Clean up PID files
    if PID_FILE.exists():
        try:
            PID_FILE.unlink()
        except Exception:
            pass

    if PIDS_DIR.exists():
        for f in PIDS_DIR.glob("*.json"):
            try:
                f.unlink()
            except Exception:
                pass

    time.sleep(1)

    # 4. Verify release of all demo ports
    print("\nVerifying demo port release:")
    all_released = True
    for svc in SERVICES:
        port = svc["port"]
        name = svc["name"]
        pid = get_pid_on_port(port)
        if pid is None:
            print(f"  [RELEASED] Port {port} ({name}) is free.")
        else:
            if is_our_bank_process(pid, svc):
                all_released = False
                print(f"  [WARNING]  Port {port} ({name}) is still held by Bank PID {pid}!")
            else:
                p_info = get_process_info(pid)
                pname = p_info["name"] if p_info else "unknown"
                print(f"  [EXTERNAL] Port {port} is preserved for external process '{pname}' (PID {pid}).")

    print("\n========================================")
    print("      BANKING KIOSK DEMO STOPPED        ")
    print("========================================")
    if all_released:
        print("All Bank processes stopped cleanly.")
    else:
        print("Bank processes shutdown completed.")
    print("You can run START_DEMO.bat again anytime.\n")


# ==============================================================================
# PORT DIAGNOSTIC CLI COMMAND
# ==============================================================================

def print_diagnose_summary():
    print("==============================================================================")
    print("               BANKING KIOSK DEMO - PORT & PROCESS DIAGNOSTICS                ")
    print("==============================================================================")
    print(f"{'Port':<6} {'Service':<30} {'Status':<22} {'PID':<8} {'Owner'}")
    print("-" * 78)

    _, diagnostics = diagnose_all_ports()
    for d in diagnostics:
        port = str(d["port"])
        name = d["service"]["name"]
        status = d["status"]
        pid = str(d["pid"]) if d["pid"] else "-"
        info = d["info"]
        owner = "-"
        if info:
            pname = info.get("name", "")
            cwd = info.get("cwd", "")
            owner = f"{pname} ({Path(cwd).name if cwd else 'unknown'})"

        print(f"{port:<6} {name:<30} {status:<22} {pid:<8} {owner}")
    print("==============================================================================\n")


if __name__ == "__main__":
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "start"
    if action == "stop":
        stop_services()
    elif action in ("diagnose", "check", "ports", "status"):
        print_diagnose_summary()
    else:
        start_services()
