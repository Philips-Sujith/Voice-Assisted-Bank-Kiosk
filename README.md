# AI-Based Voice-Assisted Banking Kiosk

An integrated AI-powered banking kiosk prototype combining hands-free voice assistance, biometric face authentication with anti-spoofing liveness detection, cryptographically secured QR-based transaction handoff, automated queue management, and teller-side transaction verification.

---

## 👥 Team

1. **Sujith B**
2. **Gokul M**
3. **Sri Harish Kumar S**
4. **Tharnikaa Balakrishnan**
5. **Gopika M**
6. **Jaya Mathanesh C**

---

## 📌 Project Overview

Modern banking interfaces often pose accessibility barriers for senior citizens, individuals with visual or motor impairments, and users unfamiliar with complex menu-driven digital kiosks. Traditional ATM and kiosk workflows rely heavily on repetitive screen taps, rigid navigation hierarchies, and manual card or PIN entry.

The **AI-Based Voice-Assisted Banking Kiosk** re-imagines customer self-service banking by introducing:
- **Biometric Face Authentication**: Password-free, card-free identity verification backed by dual-stage neural networks (YuNet face detection + ArcFace feature recognition) and real-time anti-spoofing liveness checks (MiniFASNet).
- **Natural Voice Interaction**: Voice-driven command navigation, balance inquiries, cash deposits, and cash withdrawals powered by real-time speech recognition, intent classification, and responsive Text-to-Speech (TTS) audio prompts.
- **Cryptographic Security QR Verification**: Generating short-lived, tamper-evident HMAC-SHA256 security tokens encoded into scannable QR receipts. Customers transition seamlessly from self-service kiosk to staff counters without verbal repetition or physical slip exchange.
- **Dual-Receipt Lifecycle**: Clean, standardized customer transaction receipts with dynamic QR tokens paired with verified teller acknowledgement receipts upon staff-side redemption.

> **Disclaimer**: This project is an academic and engineering prototype designed for demonstration, hackathons, and technical evaluation. It uses synthetic mock customer records and isolated local services, and is not connected to any live production banking network.

---

## 🚀 Key Features

### 1. Customer Kiosk (Module 1)
- **Voice-Driven Navigation**: Complete end-to-end banking transactions without mandatory touch input.
- **Flexible Transaction Handling**: Guided deposit, withdrawal, and balance inquiry workflows with clear visual and auditory feedback.
- **Live Confirmation & Numeric Keypad**: Visual confirmation cards with amount breakdown and manual correction keypad.
- **Customer Transaction Receipt**: High-contrast, compact, centered receipt displaying transaction details, issued timestamp, expiration window, and cryptographic QR token.

### 2. Face Authentication (Module 4)
- **Fast Face Detection**: Powered by OpenCV's YuNet ONNX model for high-speed face detection across varying lighting angles.
- **Anti-Spoofing & Liveness Detection**: Employs MiniFASNet dual-model inference to reject printouts, video replays, and digital masks.
- **Biometric Vector Matching**: ArcFace (buffalo_l w600k_r50) 512-dimensional embedding comparison against registered customer templates.
- **Separation of Concerns**: Strictly partitioned authentication interface reserved solely for verified account holders.

### 3. Face Enrollment & Demo Passbook System (Separate Workflow)
- **Dedicated Enrollment Interface**: Isolated route (`/enrollment`) designed for authorized customer onboarding.
- **Synthetic Passbook Recognition**: Automatic OCR parsing of fictional bank passbooks to auto-fill customer profile details.
- **10 Fictional Demo Passbook Fixtures**: Pre-generated, distinct passbook templates mapped to synthetic bank accounts (`passbook_01.png` through `passbook_10.png`).
- **3-Sample Face Capture**: Progressive multi-angle face enrollment storing normalized embeddings into the biometric repository.

### 4. Voice AI (Module 2)
- **Speech Input & Audio Processing**: Web-based speech capture with fallback speech synthesis.
- **Intent Parsing & Slot Extraction**: Understands conversational banking requests (e.g., *"I want to deposit five thousand rupees"* or *"Check my account balance"*).
- **Dual Communication**: Synchronous WebSocket and REST endpoints linking the Kiosk UI and Central Backend.

### 5. Security QR Verification (Module 5)
- **Cryptographic HMAC-SHA256 Tokenization**: Every transaction payload is signed with a high-entropy key to guarantee payload authenticity and tamper-proofing.
- **Anti-Replay & Expiration**: Configurable 10-minute Time-To-Live (TTL) with single-use revocation tracking.
- **Zero Secrets on Client**: The client application receives only the signed token and payload; signing keys and verification logic remain strictly on the backend.

### 6. Staff Portal & Teller Workflow (Module 6)
- **Live QR Scanner**: Real-time webcam scanning with support for manual token entry and sample QR injection for testing.
- **Backend Verification**: Immediate verification of token status, customer identity, requested transaction, and account balance.
- **Teller Approval & Ledger Update**: Secure one-click transaction completion updating central database balances in real-time.
- **Teller Acknowledgement Receipt**: Clean, minimal, centered confirmation receipt formatted for thermal printers and PDF export.

---

## 🏛️ System Architecture

```
                       ┌─────────────────────────┐
                       │     Customer Kiosk      │
                       │   (React / Vite: 5173)  │
                       └────────────┬────────────┘
                                    │
             ┌──────────────────────┼──────────────────────┐
             ▼                      ▼                      ▼
    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
    │    Voice AI     │    │ Face Auth /     │    │ Redis In-Memory │
    │ (FastAPI: 8002) │    │ Enrollment      │    │ Protocol Broker │
    └─────────────────┘    │ (FastAPI: 8003) │    │  (Port: 6379)   │
                           └─────────────────┘    └────────┬────────┘
                                    │                      │
                                    ▼                      ▼
                       ┌────────────────────────────────────────┐
                       │         Central Backend Router         │
                       │          (FastAPI / Port: 8000)        │
                       └───────────────────┬────────────────────┘
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    ▼                                             ▼
         ┌─────────────────────┐                       ┌─────────────────────┐
         │     Security QR     │                       │    Staff Portal     │
         │   (FastAPI: 8001)   │                       │(React / Vite: 5174) │
         └─────────────────────┘                       └──────────┬──────────┘
                                                                  │
                                                                  ▼
                                                          Teller Processing
```

### Module Table & Network Ports

| Module | Service Name | Technology | Port | Primary Responsibility |
|---|---|---|---|---|
| **Broker** | Redis Protocol Broker | Python / Embedded | `6379` | Inter-service pub/sub event distribution & queue messaging |
| **Module 1** | Customer Kiosk | React + Vite | `5173` | Customer-facing voice & touch banking interface |
| **Module 2** | Voice AI | Python + FastAPI | `8002` | Speech recognition, intent extraction, and voice synthesis |
| **Module 3** | Central Backend | Python + FastAPI | `8000` | Transaction state machine, customer database, ledger management |
| **Module 4** | Face Authentication | Python + OpenCV + ONNX | `8003` | Biometric face verification, liveness checks, and enrollment |
| **Module 5** | Security QR | Python + PyCryptodome | `8001` | HMAC-SHA256 signature generation and single-use validation |
| **Module 6** | Staff Portal | React + Vite | `5174` | Teller verification interface, QR scanning, and transaction approval |

---

## 💻 Tech Stack

- **Frontend**: React 18, Vite, JavaScript (ES6+), Vanilla CSS (Custom Design System), HTML5 Canvas.
- **Backend Services**: Python 3.10+, FastAPI, Uvicorn, Pydantic v2, SQLite3.
- **Computer Vision & Biometrics**:
  - **YuNet**: High-performance ONNX face detector (`face_detection_yunet_2023mar.onnx`).
  - **ArcFace / InsightFace**: Deep face representation embeddings (`w600k_r50.onnx`, `1k3d68.onnx`).
  - **MiniFASNet**: Real-time anti-spoofing binary classification (`2.7_80x80_MiniFASNetV2.onnx`, `4_0_0_80x80_MiniFASNetV1SE.onnx`).
- **Cryptography & Security**: PyCryptodome (HMAC-SHA256), URL-safe Base64 token serialization, Single-Use Nonce Validation.
- **State & Messaging**: In-Memory Redis Protocol Broker, WebSockets, REST APIs.

---

## 📋 System Requirements & Prerequisites

Before running the project, verify that the following prerequisites are installed on your Windows machine:

1. **Operating System**: Windows 10 or Windows 11 (64-bit).
2. **Python**: Python 3.10, 3.11, or 3.12.
   - *Ensure **"Add python.exe to PATH"** is checked during installation.*
3. **Node.js**: Node.js v18.x or v20.x LTS.
4. **npm**: v9.x or higher (included with Node.js).
5. **Git & Git LFS**:
   - Git 2.30+ installed.
   - Git LFS installed (`git lfs install`).
6. **Hardware**:
   - Standard USB or integrated Webcam (required for Face Authentication & QR scanning).
   - Standard Microphone (required for Voice AI interaction).

---

## ⚡ Quick Start: Clone & Run

The repository contains a fully automated, portable launcher for Windows that sets up environments, verifies dependencies, checks model assets, and boots all 6 services with one click.

### Step 1: Clone the Repository
```cmd
git clone https://github.com/Philips-Sujith/Voice-Assisted-Bank-Kiosk.git
cd Voice-Assisted-Bank-Kiosk
```

### Step 2: Ensure Git LFS Pulled Large Biometric Models
```cmd
git lfs pull
```

### Step 3: Run the All-in-One Demo Launcher
Double-click `START_DEMO.bat` or execute in Command Prompt / PowerShell:
```cmd
START_DEMO.bat
```

**What the automated launcher does:**
1. Checks system Python and Node.js versions.
2. Creates an isolated, local virtual environment (`.venv`).
3. Installs missing Python dependencies automatically via `setup_env.py`.
4. Checks frontend `node_modules` and runs `npm install` automatically if needed.
5. Verifies all 5 ONNX biometric model weights are present.
6. Launches the Redis protocol broker and all 5 backend Python microservices on their dedicated ports.
7. Launches the Customer Kiosk (`http://localhost:5173`) and Staff Portal (`http://localhost:5174`).
8. Automatically opens both portals in your default web browser.

### Step 4: Stop All Services Cleanly
Whenever you want to stop the demonstration, double-click:
```cmd
STOP_DEMO.bat
```
This safely shuts down all 6 microservices, frees all occupied ports (`5173`, `5174`, `6379`, `8000`, `8001`, `8002`, `8003`), and cleans runtime temporary PIDs.

---

## 🛠️ Manual Startup (Alternative)

If you prefer starting individual microservices manually in separate terminal windows:

### 1. Redis Protocol Broker
```cmd
python run_redis.py
```

### 2. Module 5: Security QR (Port 8001)
```cmd
cd AI-Based-Voice-Assisted-Kiosk-Prototype\module5_security
python app.py
```

### 3. Module 4: Face Authentication (Port 8003)
```cmd
cd AI-Based-Voice-Assisted-Kiosk-Prototype\module4_face_auth
uvicorn app.main:app --host 127.0.0.1 --port 8003
```

### 4. Module 3: Central Backend (Port 8000)
```cmd
cd AI-Based-Voice-Assisted-Kiosk-Prototype\module3_backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 5. Module 2: Voice AI (Port 8002)
```cmd
cd AI-Based-Voice-Assisted-Kiosk-Prototype\module2_voice
python server.py
```

### 6. Module 6: Staff Portal Frontend (Port 5174)
```cmd
cd AI-Based-Voice-Assisted-Kiosk-Prototype\module6_staff_portal
npm install
npm run dev
```

### 7. Module 1: Customer Kiosk Frontend (Port 5173)
```cmd
cd module-repos\Gopika_Module
npm install
npm run dev
```

---

## 📝 Complete Transaction Walkthrough

```
[Customer Step]
1. Open Customer Kiosk (http://localhost:5173).
2. Look directly into the camera frame. The kiosk runs YuNet face detection and MiniFASNet anti-spoofing.
3. Upon biometric recognition, the customer is authenticated (e.g., "Sujith").
4. Click the Voice AI microphone or speak: "Deposit 10,000 rupees" or "Withdraw 5,000 rupees".
5. The Voice AI classifies intent and populates the transaction card.
6. Confirm the amount on the numeric confirmation keypad.
7. Central Backend records the pending transaction and requests an HMAC-signed token from Security QR.
8. The customer receipt appears, displaying transaction details and the secure QR code.

[Staff Step]
9. Switch to the Staff Portal (http://localhost:5174).
10. Login with default demo staff credentials (Staff ID: `STAFF-001`, Password: `Password@123`).
11. Navigate to the QR Scanner tab.
12. Present the customer kiosk QR code to the staff webcam (or select the matching sample QR).
13. Security QR validates the HMAC signature, expiration time, and single-use status.
14. The teller reviews customer name, transaction type, and amount.
15. Click "Approve & Complete Transaction". The customer balance updates in the central ledger.
16. A clean, centered Teller Acknowledgement Receipt is generated for printing or PDF export.
```

---

## 📷 Face Enrollment Demo & 10 Synthetic Passbooks

To demonstrate registering new bank customers without exposing real personal information, the repository includes an isolated **Face Enrollment Workflow** supported by **10 fictional demo passbook templates**:

### How to Demo Face Enrollment:
1. Open the Customer Kiosk at `http://localhost:5173/enrollment` (or click "Face Enrollment Demo").
2. Under **Step 1: Demo Passbook Verification**, click **"Select Demo Passbook"**.
3. Choose any of the 10 fictional synthetic passbooks (`passbook_01.png` through `passbook_10.png`).
4. The system automatically reads the passbook metadata (fictional customer name, masked account number, demo branch).
5. Click **"Verify & Proceed to Face Capture"**.
6. Under **Step 2: Biometric Face Enrollment**, align your face in the oval guide.
7. Capture 3 biometric samples. The system extracts ArcFace embeddings and links them to the selected demo account.
8. Return to the main kiosk page (`http://localhost:5173`). Look at the camera — you will now be recognized under your newly enrolled demo customer identity!

### Resetting Demo Enrollments:
To clear enrolled biometric vectors back to a fresh state without modifying customer balances, run:
```cmd
python reset_demo_face_enrollments.py
```

### Synthetic Demo Customer Fixtures:
Located in `demo_fixtures/passbooks/`:
- `passbook_01.png` — AI Smart Bank (Aarav Sharma)
- `passbook_02.png` — Bharat National Bank (Diya Patel)
- `passbook_03.png` — Digital India Bank (Rohan Verma)
- `passbook_04.png` — Vistara Cooperative Bank (Ananya Iyer)
- `passbook_05.png` — National Savings Bank (Vikram Malhotra)
- `passbook_06.png` — Apex Mercantile Bank (Sneha Kulkarni)
- `passbook_07.png` — Metro Community Bank (Aditya Joshi)
- `passbook_08.png` — Union Trust Bank (Meera Nambiar)
- `passbook_09.png` — Heritage Commercial Bank (Kavya Sundaram)
- `passbook_10.png` — Pratham Rural Bank (Rajesh Khanna)

*All names, bank identities, account numbers, and IFSC codes are 100% synthetic fixtures.*

---

## 🔒 Security Architecture

The kiosk prototype implements multiple defense-in-depth principles:
- **Biometric Anti-Spoofing**: Prevents presentation attacks using 2D screen replays or paper photographs via MiniFASNet neural evaluation.
- **Cryptographic QR Signing**: QR payloads are structured with `token_id`, `customer_id`, `amount`, `issued_at`, and `expires_at`, signed using HMAC-SHA256 with 256-bit entropy keys.
- **Single-Use Nonce Revocation**: Tokens can only be scanned and processed once. Once redeemed at the teller terminal, re-scanning the same QR returns a `"Token Already Used"` error.
- **Zero Client Secrets**: Frontends (Kiosk and Staff Portal) never possess HMAC keys or direct database access. All verification occurs server-side in Module 5 and Module 3.
- **Data Protection**: Virtual environments, debug logs, local runtime caches, and private keys are strictly excluded from git tracking.

---

## 📁 Repository Structure

```
Voice-Assisted-Bank-Kiosk/
│
├── AI-Based-Voice-Assisted-Kiosk-Prototype/
│   ├── data/
│   │   ├── bank_db.py                         # SQLite ledger schema, customer queries & seed data
│   │   ├── bank_kiosk.db                      # Local SQLite demonstration database
│   │   └── sample_passbook.png                # Reference passbook template
│   ├── module2_voice/
│   │   ├── server.py                          # Voice AI FastAPI server (Port 8002)
│   │   └── voice_service.py                   # Intent classification & TTS synthesis
│   ├── module3_backend/
│   │   ├── app/                               # Central Backend FastAPI router (Port 8000)
│   │   ├── tests/                             # Integration tests for transaction state machine
│   │   └── requirements.txt                   # Backend Python dependencies
│   ├── module4_face_auth/
│   │   ├── app/                               # Face Authentication & Enrollment endpoints (Port 8003)
│   │   ├── models/                            # Biometric neural network ONNX weights
│   │   │   ├── face_detection_yunet_2023mar.onnx
│   │   │   ├── 2.7_80x80_MiniFASNetV2.onnx
│   │   │   ├── 4_0_0_80x80_MiniFASNetV1SE.onnx
│   │   │   └── buffalo_l/                     # InsightFace ArcFace models (Git LFS tracked)
│   │   │       ├── w600k_r50.onnx
│   │   │       └── 1k3d68.onnx
│   │   └── requirements.txt                   # Face Auth dependencies
│   ├── module5_security/
│   │   ├── app.py                             # Security QR verification service (Port 8001)
│   │   ├── crypto.py                          # HMAC-SHA256 signing and validation routines
│   │   ├── qr_generator.py                    # Scannable QR code generation
│   │   └── requirements.txt                   # Cryptography dependencies
│   └── module6_staff_portal/
│       ├── src/                               # Teller verification React application (Port 5174)
│       ├── public/sample_qrs/                 # Test QR codes for demonstration
│       ├── package.json                       # Staff Portal npm manifest
│       └── vite.config.js                     # Vite configuration
│
├── module-repos/
│   └── Gopika_Module/
│       ├── src/                               # Customer Kiosk React application (Port 5173)
│       ├── package.json                       # Customer Kiosk npm manifest
│       └── vite.config.js                     # Vite configuration
│
├── demo_fixtures/
│   ├── manifest.json                          # Metadata linking demo passbooks to mock accounts
│   └── passbooks/                             # 10 fictional demo passbook templates (01 - 10)
│
├── .gitattributes                             # Git LFS configuration for large ONNX models
├── .gitignore                                 # Clean ignore rules excluding node_modules, .venv, etc.
├── .env.example                               # Service ports and environment template
├── launcher_service.py                        # Cross-platform microservice orchestration manager
├── reset_demo_face_enrollments.py             # Reset tool for demo biometric enrollments
├── run_redis.py                               # Lightweight embedded Redis protocol broker
├── setup_env.py                               # Automatic Python dependency installer & validator
├── START_DEMO.bat                             # One-click portable Windows demo launcher
├── STOP_DEMO.bat                              # One-click portable Windows demo shutdown tool
└── README.md                                  # Complete documentation & usage guide
```

---

## 🔧 Troubleshooting

### Camera Not Working in Face Auth or QR Scanner
- Ensure your browser has camera permissions allowed for `http://localhost:5173` and `http://localhost:5174`.
- On Windows, check **Settings → Privacy & Security → Camera** to verify desktop apps are allowed to access the camera.
- Close any other running application (Zoom, Teams, Skype) that may be holding an exclusive hardware lock on the webcam.

### Microphone Not Detected
- Check browser permissions for microphone access at `http://localhost:5173`.
- Verify your default recording device in **Windows Sound Settings**.

### Face Authentication Fails or Shows Error
- Verify Module 4 is healthy by opening `http://127.0.0.1:8003/health` in your browser.
- Ensure large biometric model files were completely downloaded via Git LFS:
  ```cmd
  git lfs pull
  ```
- Ensure your face is centered within the camera guide oval with adequate lighting.

### Port Already in Use (`EADDRINUSE` or WinError 10048)
- Run `STOP_DEMO.bat` to terminate any previous background service processes.
- Alternatively, check which process is holding the port using:
  ```cmd
  netstat -ano | findstr :5173
  netstat -ano | findstr :8000
  ```
  and terminate it via `taskkill /F /PID <PID>`.

### Node / Python Dependencies Missing
- Run `setup_env.py` using Python to re-verify Python packages:
  ```cmd
  python setup_env.py
  ```
- Re-run `npm install` inside `module-repos/Gopika_Module` and `AI-Based-Voice-Assisted-Kiosk-Prototype/module6_staff_portal`.

---

## ⚠️ Limitations & Prototype Disclaimer

- **Demonstration Prototype**: This software is designed exclusively as an academic, engineering, and hackathon demonstration. It is not approved or certified for commercial or production banking transactions.
- **Synthetic Financial Data**: All account numbers, balances, IFSC codes, customer profiles, and transaction records are fictional mock data stored in local SQLite databases.
- **Local Deployment**: Designed for local workstation execution (`localhost`). Deployment across wide-area networks would require mutual TLS, external credential vaults, and hardware security modules (HSM) for signing keys.

---

## 👥 Team Members

- **Sujith B**
- **Gokul M**
- **Sri Harish Kumar S**
- **Tharnikaa Balakrishnan**
- **Gopika M**
- **Jaya Mathanesh C**
