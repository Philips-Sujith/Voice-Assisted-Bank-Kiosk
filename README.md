# AI Voice-Assisted Banking Kiosk

An enterprise-grade, accessible, service-oriented banking kiosk platform engineered to eliminate literacy, language, and operational friction in retail bank branches through vernacular voice AI, contactless biometric authentication, and cryptographically verified teller workflows.

---

## 1. Project Overview

The **AI Voice-Assisted Banking Kiosk** is an integrated omnichannel branch automation solution. It bridges the accessibility gap for elderly, low-literacy, and rural customers who struggle with traditional ATM interfaces or handwritten paper deposit and withdrawal slips.

By orchestrating real-time vernacular speech-to-text, natural language intent recognition, on-device facial anti-spoofing biometrics, and HMAC-SHA256 one-time digital transaction tokens, the platform transitions walk-in banking counter encounters from an average of **4 minutes down to under 30 seconds**.

---

## 2. Key Capabilities

- **Vernacular Conversational AI**: Native speech recognition and natural language entity parsing in English, Tamil, and Tanglish (Tamil-English code-switching).
- **Contactless 2FA Biometric Authentication**: Deep neural network face recognition with multi-sample gallery matching, passive eye-blink liveness verification, and MiniFASNet anti-spoofing.
- **Dynamic Real-Time Account Ledger**: Instant deposit, withdrawal, and balance reconciliation with persistent SQLite transactional safety.
- **Cryptographic One-Time QR Tokens**: HMAC-SHA256 signed 1800-second expiring payloads preventing tampering, replay attacks, and man-in-the-middle manipulation.
- **Dual Thermal Receipt Generation**: High-resolution, professional PDF receipts for customer confirmation and teller counter physical audit trails.
- **Teller Queue Management & Operations Portal**: Instant webcam and file-upload QR scanning with real-time WebSocket queue updates.
- **Isolated Face Enrollment & Passbook Verification**: Passbook OCR verification with multi-angle biometric sample enrollment isolated from the public customer kiosk.

---

## 3. System Architecture

The platform is engineered as an integrated service-oriented architecture comprising decoupled frontends, domain microservices, an embedded protocol broker, and unified persistent storage:

### Architecture Tiers

| Tier | Components | Protocols / Interfaces | Primary Responsibility |
|---|---|---|---|
| **Presentation Tier** | Customer Kiosk (`apps/customer-kiosk`)<br>Teller Operations Portal (`apps/teller-portal`) | React 18, Vite, Web Audio API, WebRTC Camera Stream | Touchscreen customer self-service, vernacular voice interactions, teller counter queue visualization, and QR verification. |
| **Core Orchestration** | Banking Core API (`services/banking-api`) | FastAPI, Uvicorn, REST, WebSockets, Transitions FSM | Kiosk session lifecycle, finite state machine (FSM) state transitions, biometric auth gates, queue management, and transaction ledger. |
| **Domain Microservices** | Identity Service (`services/identity`)<br>Voice Service (`services/voice`)<br>Security Service (`services/security`) | REST, WebSocket Audio Stream, ONNX Runtime | Biometric face verification and liveness; vernacular speech recognition and intent parsing; HMAC-SHA256 token issuance and QR generation. |
| **Event & Data Tier** | Redis Protocol Broker (`infrastructure/redis`)<br>Unified Database (`data/database`)<br>Demo Fixtures (`data/demo`) | Redis Pub/Sub (TCP 6379), SQLite3 (WAL Mode) | Asynchronous event broadcasting for real-time queue synchronization, ACID persistent storage for account balances, transactions, and face embeddings. |

### Inter-Service Communication Flow
- **Customer Kiosk to Banking API**: Session initiation, transaction state progression, and customer confirmation via REST (`/api/v1/session/*`).
- **Customer Kiosk to Identity Service**: Direct camera frame transmission for biometric verification and liveness checks (`/face-auth/verify`).
- **Customer Kiosk to Voice Service**: Bidirectional raw PCM audio streaming over WebSocket (`/ws/audio`) for real-time transcription and entity extraction.
- **Banking API to Security Service**: Server-side dispatch to cryptographic engine for deterministic HMAC-SHA256 token signing (`/sign`).
- **Banking API to Redis Broker**: Event publication (`kiosk:queue:events`) upon transaction confirmation, token call, and completion.
- **Teller Portal to Banking API**: Real-time queue event consumption over WebSocket (`/ws/dashboard`) and cryptographic QR token validation (`/api/v1/token/verify-qr`).

---

## 4. Team

1. **Sujith B**
2. **Gokul M** — [GitHub](https://github.com/gokulwm)
3. **Sri Harish Kumar S** — [GitHub](https://github.com/SriHarishKumar3542)
4. **Tharnikaa Balakrishnan** — [GitHub](https://github.com/Tharnikaa)
5. **Gopika M** — [GitHub](https://github.com/pavigopi2023-commits)
6. **Jaya Mathanesh C** — [GitHub](https://github.com/jaya-mathanesh)

---

## 5. Customer Journey & Core Workflow

The end-to-end customer workflow follows a deterministic, state-machine-controlled journey:

1. **Language & Service Selection**: Customer selects English or Tamil on the kiosk touchscreen. Audio prompts guide the user through each step.
2. **Contactless Biometric Verification**: The customer aligns their face with the on-screen target. The Identity Service verifies liveness and matches the facial vector against enrolled customer records.
3. **Conversational Voice Request**: The customer speaks naturally into the kiosk microphone (e.g., *"Deposit fifty thousand rupees"* or *"பத்தாயிரம் ரூபாய் டெபாசிட் செய்"*).
4. **Confirmation & Intent Summary**: The kiosk parses the request, confirms the transaction type and amount, and presents an explicit confirmation screen.
5. **Token Generation & Scannable QR**: Once confirmed, the Security Service signs the transaction parameters into an HMAC-SHA256 QR token, queued for the teller counter.
6. **Customer Receipt Issuance**: The customer receives a physical or digital transaction token receipt with timestamp, masked account number, and transaction summary.

---

## 6. Biometric Authentication & Liveness

The Identity Service provides defense-in-depth biometric verification through a multi-stage computer vision pipeline:

### Verification Pipeline
1. **Face Detection**: Fast YuNet neural network detects the bounding box, facial landmarks, and rotational alignment from camera frames.
2. **Anti-Spoofing Filter**: MiniFASNet convolutional neural network evaluates texture, depth, and reflection cues to reject printed photographs, screens, and masks (threshold > 0.50).
3. **Dynamic Liveness (EAR)**: Eye Aspect Ratio (EAR) tracking over consecutive video frames verifies natural eye-blink patterns before authentication is granted.
4. **Embedding Extraction**: InsightFace (ArcFace ResNet-50) extracts a normalized 512-dimensional facial feature vector.
5. **Gallery Matching**: Cosine similarity is computed against all stored embeddings for the customer. A similarity score equal to or exceeding 0.60 securely identifies the customer.
6. **Auth Gate Enforcement**: Financial transactions (withdrawals and deposits) strictly enforce an authenticated session status; unauthenticated requests are halted at the API gateway.

---

## 7. Voice-Assisted Transactions

The Voice Service enables hands-free vernacular transaction specification:

- **Vernacular Audio Pipeline**: Real-time microphone audio is ingested over WebSocket, converted to 16 kHz mono PCM, and transcribed.
- **Multilingual Support**: Supports English, pure Tamil, and colloquial Tanglish (mixed Tamil and English terms common in daily banking).
- **Entity & Multiplier Extraction**: Recognizes banking intents (`deposit`, `withdraw`, `balance_inquiry`, `send_money`) and parses complex numerical expressions including vernacular multipliers (*lakh*, *thousand*, *ஆயிரம்*, *கோடி*).
- **Graceful Intent Degradation**: Requests lacking critical parameters (such as an unspecified amount) prompt targeted voice follow-up queries rather than failing.

---

## 8. Security & Cryptographic Verification

All financial operations follow banking-grade zero-trust principles:

- **HMAC-SHA256 Signing**: Every transaction token is signed using a symmetric 256-bit cryptographic key, binding `token_id`, `session_id`, `customer_id`, `transaction_type`, `amount`, and `expires_at`.
- **Tamper Detection**: Any modification of QR code payload parameters invalidates the HMAC signature immediately upon scanning.
- **Single-Use Enforcement**: Tokens are consumed atomically upon teller processing. Once processed, subsequent scan attempts fail with `TOKEN_ALREADY_USED`.
- **Strict TTL Windows**: Tokens carry a strict 1800-second (30-minute) time-to-live. Expired tokens are marked `EXPIRED` and cannot be processed.
- **Privacy Masking**: Account numbers are consistently masked across on-screen displays, QR payloads, and printed receipts (e.g., `DEMO-XXXX01`).

---

## 9. Teller Operations Portal

The Teller Portal provides a real-time counter interface for bank staff:

- **Real-Time Queue Visualization**: Listens on WebSocket (`/ws/dashboard`) to display newly issued tokens immediately with queue position and customer details.
- **Dual-Mode QR Verification**: Supports both counter webcam scanning and image file uploads for scannable QR tokens.
- **Transaction Processing**: One-click counter processing automatically reconciles account balances in `bank_kiosk.db`.
- **Teller Audit Receipt**: Generates a standardized, centered teller acknowledgment receipt confirming physical currency exchange for branch audit archives.

---

## 10. Face Enrollment & Passbook Verification

Face registration is isolated in a secure enrollment flow (`/#face-enrollment`) to ensure branch-supervised onboarding:

- **Physical Passbook Verification**: Accepts uploaded passbook images and validates account authenticity via native Windows OCR or demo fixture SHA-256 matching.
- **Multi-Angle Gallery Registration**: Guides the customer to capture 4 distinct facial samples (center, slight left, slight right, slight smile) to build a robust biometric profile.
- **Database Persistence**: Embeddings are stored in SQLite `face_embeddings` table linked to the verified customer record.

---

## 11. Technology Stack

| Domain | Technology / Library | Purpose |
|---|---|---|
| **Frontends** | React 18, Vite, Lucide Icons, jsPDF, html2canvas | High-performance reactive web interfaces |
| **Banking Core API** | FastAPI, Pydantic v2, Transitions FSM, Uvicorn | Session orchestration and account business logic |
| **Voice Service** | FastAPI, WebSockets, Python Sound Pipeline | Real-time vernacular speech parsing and entity extraction |
| **Identity Service** | InsightFace (ArcFace), YuNet ONNX, MiniFASNet, OpenCV | Biometric detection, liveness, and face matching |
| **Security Service** | PyCryptodome, QRCode, Base64 | HMAC-SHA256 signing and one-time token verification |
| **Data & Storage** | SQLite3 (WAL mode), Fakeredis TCP Broker | ACID persistent database and Redis pub/sub broker |
| **Automation** | Windows Batch Scripts, PowerShell | Fully portable, location-independent system launcher |

---

## 12. Project Structure

```
Voice-Assisted-Bank-Kiosk/
│
├── apps/                                  # Frontend Applications
│   ├── customer-kiosk/                    # Touchscreen & voice customer terminal (Port 5173)
│   │   ├── src/                           # React components, screens, services
│   │   ├── public/                        # Static assets, branding
│   │   ├── index.html                     # HTML5 template
│   │   ├── package.json                   # Dependencies: customer-kiosk
│   │   └── vite.config.js                 # Vite build settings
│   │
│   └── teller-portal/                     # Teller counter & QR processing app (Port 5174)
│       ├── src/                           # React components, QR scanner, queue
│       ├── public/                        # Static assets, brand icons
│       ├── index.html                     # HTML5 template
│       ├── package.json                   # Dependencies: teller-portal
│       └── vite.config.js                 # Vite build settings
│
├── services/                              # Microservices Layer
│   ├── banking-api/                       # Central Orchestrator & Banking API (Port 8000)
│   │   ├── app/                           # Routers, FSM, services, session store
│   │   ├── mocks/                         # Test fixtures & mocks
│   │   └── requirements.txt               # API dependencies
│   │
│   ├── identity/                          # Face Authentication & Anti-Spoofing (Port 8003)
│   │   ├── app/                           # Face routes, antispoof, db adapter
│   │   ├── models/                        # ONNX biometric weights (YuNet, MiniFASNet, ArcFace)
│   │   └── requirements.txt               # Identity dependencies
│   │
│   ├── security/                          # Cryptographic Token & QR Service (Port 8001)
│   │   ├── crypto.py                      # HMAC-SHA256 signing & validation
│   │   ├── qr_generator.py                # QR matrix generation
│   │   ├── token_service.py               # Token lifecycle & TTL management
│   │   └── requirements.txt               # Security dependencies
│   │
│   └── voice/                             # Vernacular Voice AI Engine (Port 8002)
│       ├── intent_parser.py               # Multilingual intent & entity parser
│       ├── server.py                      # WebSocket & REST server
│       ├── stt_pipeline.py                # Speech-to-text pipeline
│       └── tts_pipeline.py                # Text-to-speech engine
│
├── infrastructure/                        # Infrastructure Runners
│   └── redis/                             # Embedded Redis protocol server (Port 6379)
│       └── run_redis.py                   # Standalone TCP fake server
│
├── data/                                  # Data Layer
│   ├── database/                          # Persistent SQLite database
│   │   ├── bank_db.py                     # Database access layer & migrations
│   │   └── bank_kiosk.db                  # Live SQLite database file
│   └── demo/                              # Demonstration Assets
│       ├── manifest.json                  # Authorized test fixtures manifest
│       └── passbooks/                     # 10 synthetic demo passbook templates
│
├── tests/                                 # Automated Test Suites
│   ├── backend/                           # 107 Unit tests for Banking API & FSM
│   ├── identity/                          # Face authentication hardening & liveness tests
│   ├── integration/                       # End-to-end multi-service integration tests
│   ├── security/                          # HMAC signing and token expiration tests
│   └── voice/                             # Vernacular speech & entity parsing tests
│
├── scripts/                               # Operational & Portable Scripts
│   ├── START_DEMO.bat                     # Complete one-click portable launcher
│   ├── STOP_DEMO.bat                      # Graceful shutdown & cleanup script
│   ├── launcher_service.py                # Python multi-process orchestrator
│   ├── setup_env.py                       # Automated dependency verification
│   └── reset_demo_face_enrollments.py     # Biometric reset tool for 10 demo accounts
│
├── .env.example                           # Configuration templates
├── .gitignore                             # Git ignore rules
├── requirements.txt                       # Unified Python requirements
└── README.md                              # Complete product documentation
```

---

## 13. Port Allocation & Endpoints

| Port | Service / Application | Protocol | Primary Endpoints | Description |
|---|---|---|---|---|
| **5173** | Customer Kiosk | HTTP | `http://localhost:5173` | React customer-facing kiosk interface |
| **5174** | Teller Portal | HTTP | `http://localhost:5174` | React operations & QR counter portal |
| **8000** | Banking API | HTTP / WS | `/api/v1/session/*`<br>`/ws/dashboard` | Central orchestrator, FSM, and SQLite layer |
| **8001** | Security Service | HTTP | `/sign`<br>`/verify` | HMAC-SHA256 cryptographic signing engine |
| **8002** | Voice Service | HTTP / WS | `/api/v1/parse`<br>`/ws/audio` | Vernacular speech recognition & intent parser |
| **8003** | Identity Service | HTTP | `/face-auth/verify`<br>`/face-auth/enroll` | Facial recognition, liveness, & anti-spoofing |
| **6379** | Redis Protocol Broker | TCP | `127.0.0.1:6379` | Standalone event bus for pub/sub notifications |

---

## 14. Setup & Installation

### Prerequisites
- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Python**: 3.10 or 3.11 with `python` or `py` in system PATH
- **Node.js**: Node.js 18+ LTS and npm

### Automated One-Click Launch (Recommended)
Simply double-click:
```cmd
START_DEMO.bat
```
The launcher will automatically:
1. Detect project paths relative to `%~dp0` without hardcoded absolute paths.
2. Initialize and verify a portable Python virtual environment (`.venv`).
3. Verify all required packages and ONNX neural network weights.
4. Install npm dependencies and build production bundles for both frontends.
5. Launch all 7 microservices in background threads with health verification.
6. Automatically launch Google Chrome to `http://localhost:5173` and `http://localhost:5174`.

### Graceful Termination
To terminate all demo processes cleanly and free allocated ports:
```cmd
STOP_DEMO.bat
```

---

## 15. Demo Accounts & Passbooks

The database is pre-seeded with 10 synthetic demo accounts mapped directly to passbook fixtures located in `data/demo/passbooks/`:

| Customer ID | Account Name | Account Number | Initial Balance | Demo Passbook Fixture |
|---|---|---|---|---|
| `demo_cust_001` | Arjun Kumar | `DEMO-100001` | INR 125,000.00 | `passbook_01.png` |
| `demo_cust_002` | Priya Sharma | `DEMO-100002` | INR 85,000.00 | `passbook_02.png` |
| `demo_cust_003` | Rahul Verma | `DEMO-100003` | INR 210,000.00 | `passbook_03.png` |
| `demo_cust_004` | Ananya Reddy | `DEMO-100004` | INR 340,000.00 | `passbook_04.png` |
| `demo_cust_005` | Karthik Menon | `DEMO-100005` | INR 95,000.00 | `passbook_05.png` |
| `demo_cust_006` | Meera Nair | `DEMO-100006` | INR 180,000.00 | `passbook_06.png` |
| `demo_cust_007` | Aditya Rao | `DEMO-100007` | INR 65,000.00 | `passbook_07.png` |
| `demo_cust_008` | Sneha Iyer | `DEMO-100008` | INR 275,000.00 | `passbook_08.png` |
| `demo_cust_009` | Vikram Das | `DEMO-100009` | INR 150,000.00 | `passbook_09.png` |
| `demo_cust_010` | Kavya Krishnan | `DEMO-100010` | INR 315,000.00 | `passbook_10.png` |

To reset demo biometric face enrollments back to un-enrolled state without wiping customer balances:
```cmd
py -3 scripts/reset_demo_face_enrollments.py
```

---

## 16. Automated Testing

The repository contains multi-layer test suites covering unit logic, cryptographic contracts, and live microservice integration (142 total tests):

```bash
# Run 107 Banking Core API unit and FSM state machine tests
py -3 -m pytest tests/backend

# Run Voice Service vernacular parser unit tests
py -3 -m unittest tests/voice/test_voice_service.py

# Run Security Service HMAC & token consumption tests
py -3 -m unittest tests/security/test_security_service.py

# Run Face Authentication capabilities and hardening tests (requires live service on 8003)
py -3 -m pytest tests/identity/test_face_auth_hardening.py

# Run End-to-End multi-service integration test suite (requires live system)
py -3 -m pytest tests/integration/test_end_to_end_real.py

# Run Full System Integration test suite
py -3 -m pytest tests/integration/test_system_integration.py
```

---

## 17. Security Considerations

- **HMAC-SHA256 Signature Verification**: QR payloads are verified exclusively on the server side using a secure symmetric signing key.
- **Single-Use Replay Protection**: Tokens are consumed atomically on first verification; repeated scans are rejected with `ALREADY_USED`.
- **Account Number Masking**: Account numbers on physical thermal receipts and QR codes are masked (e.g. `XXXX1234` or `DEMO-XXXX01`) to protect customer privacy.
- **Liveness & Anti-Spoofing Defense**: Real-time passive eye-blink detection combined with MiniFASNet convolutional anti-spoofing filters prevent photo and screen replay attacks.
- **Ephemeral Session Security**: Kiosk state machines enforce strict timeouts and unauthenticated request blocks.

---

## 18. Troubleshooting

| Symptom | Cause | Solution |
|---|---|---|
| `Port already in use` | Previous instance not stopped | Run `STOP_DEMO.bat` or kill orphan processes via Task Manager. |
| `Camera not detected` | Browser camera permissions blocked | Allow camera access in Chrome settings for `http://localhost:5173` and `http://localhost:5174`. |
| `Audio not transcribing` | Browser microphone permissions blocked | Click camera/microphone icon in URL bar and grant microphone permission. |
| `Face models missing` | Model weights not downloaded | Verify that all 5 `.onnx` files exist in `services/identity/models/`. |
| `Missing Python module` | Environment not updated | Run `py -3 scripts/setup_env.py` to auto-install missing packages. |

---

## 19. Limitations & Future Roadmap

### Current Limitations
- **On-Premise Single Kiosk Setup**: The current architecture is designed for a single kiosk terminal paired with a teller workstation.
- **Embedded Database Architecture**: Utilizes SQLite with Write-Ahead Logging (WAL) for local branch durability rather than an enterprise distributed relational database.
- **Simulated Core Banking Ledger**: Demonstrates realistic balance updates and transactions locally; real deployments would connect via ISO 8583 / REST adapters to a core banking system (CBS).

### Future Roadmap
- **Multimodal Conversational LLM**: Integration of fine-tuned domain-specific banking LLMs for complex inquiries (loan applications, fixed deposit calculations).
- **Expanded Regional Languages**: Adding support for Hindi, Telugu, Kannada, and Malayalam.
- **Hardware Integration**: Direct peripheral drivers for physical motorized card readers, cash acceptance modules, and thermal ESC/POS roll printers.
- **Enterprise Central Management**: Centralized dashboard for managing kiosk fleet deployments, firmware updates, and branch-wide security audits.
