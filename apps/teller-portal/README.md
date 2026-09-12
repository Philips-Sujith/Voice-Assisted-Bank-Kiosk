# AI Smart Bank Self-Service Kiosk & Verification Portal

**Accessible, Multimodal, and Privacy-Compliant Banking for Regional & Low-Literacy Users**

## Overview

The AI Smart Bank Self-Service Kiosk is an accessible banking terminal and teller workflow automation system designed to eliminate literacy, language, and operational friction in retail bank branches.

By combining Edge OCR, a Bi-directional Web Speech Engine (Tamil & English), 2FA Facial Biometrics, and an Integrated Teller QR Portal, the system bridges the gap between illiterate or elderly customers and physical bank tellers, reducing counter transaction times from ~4 minutes to under 30 seconds.

## Key Problems Solved

- **Literacy & Language Barriers**: Eliminates manual paper pay-in/withdrawal slips through hands-free Tamil (ta-IN) and Indian English (en-IN) voice commands.
- **Proxy Fraud & Security Vulnerabilities**: Prevents unauthorized slips by enforcing biometric identity verification (Fingerprint authentication + Live Face Embedding 2FA) while keeping customer account numbers private.
- **Branch Bottlenecks & Teller Errors**: Automatically encodes verified customer transactions into a 58mm thermal slip with a signed QR token, enabling tellers to decode and approve requests in a single camera scan.

## End-to-End System Workflow

```
                        [ CUSTOMER INTERACTION ]
                                   │
                   ( Multilingual Voice Assistant )
              "Account Holder or Non-Account Holder?"
                     /                            \
        [ Non-Account Holder ]             [ Account Holder ]
                 │                                 │
     • Passbook OCR Scanning              1. Fingerprint Lookup (1:1 / 1:N)
     • Voice-Guided Form Filling          2. Live 2FA Face Embedding Match
                 │                                 │
                 \                                /
                  ▼                              ▼
                 [ Dual-Input Transaction Configuration ]
                 • Spoken Intent: "Deposit 5000" / "ஐந்தாயிரம் எடு"
                 • Natural Language Number & Multiplier Parser
                                   │
                                   ▼
             ┌───────────────────────────────────────────┐
             │ 58mm Thermal Slip (ReportLab PDF Engine)   │
             │ • Masked Account Display (e.g. 3155XXXX)   │
             │ • Physical Signature Verification Line     │
             │ • Secure Encrypted Teller QR Token         │
             └─────────────────────┬─────────────────────┘
                                   │
                                   ▼
                        [ BANK TELLER PORTAL ]
             ┌───────────────────────────────────────────┐
             │ • Live Webcam QR Code Auto-Decoder         │
             │ • High-Value Alert (> ₹50,000 PAN Check)   │
             │ • Physical Signature Match Checklist       │
             │ • Instant Approval & Teller Ack Slip       │
             └───────────────────────────────────────────┘
```

## Core Features & Technical Highlights

### 1. Dual-Track Customer Routing

- **Account Holders**: Fast-tracks identity validation through fingerprint matching paired with facial embedding cosine similarity verification (SFace / YuNet / MobileFaceNet).
- **Non-Account / Walk-in Customers**: Seamlessly guides walk-ins through voice prompts to scan physical passbooks or documents for deposits and branch onboarding.

### 2. Targeted Passbook OCR (Tesseract Engine)

Employs heuristic regex parsing to extract Account Number, Account Holder Name, and IFSC Code while isolating and ignoring the CIF Number (preventing OCR false positives). Operates locally on CPU with zero cloud dependency.

### 3. Bi-directional Web Speech Bridge (Tamil & English)

Captures voice directly in the browser using the HTML5 Web Speech API (ta-IN / en-IN), avoiding Python audio format mismatches (PCM WAV/WebM codec errors). Implements a handshake protocol (`streamlit:componentReady`, `setFrameHeight`, `setComponentValue`) to stream transcripts into backend session state.

Bilingual Natural Language Parser extracts intents (Cash Deposit or Cash Withdrawal) and converts spoken Tamil words ("ஐந்தாயிரம்", "பத்தாயிரம்", "ஒரு லட்சம்") or English numbers into integer amounts.

### 4. Privacy-by-Design TTS & Display

- **No Spoken Account Numbers**: The text-to-speech assistant only greets users by name or speaks generic action prompts to protect sensitive financial data in public kiosk environments.
- **Masked Display**: Account numbers appear partially masked on screen and printed receipts (e.g., 3155XXXX4787). Full account credentials are exclusively encoded into the signed teller QR payload.

### 5. Live Bank Teller Verification Portal

- **Integrated QR Scanner**: Decodes thermal-slip tokens using OpenCV (`cv2.QRCodeDetector`) with sound feedback.
- **Compliance Checks**: Displays high-value transaction warnings (> ₹50,000), enforces signature matching, and logs approved/rejected tokens with downloadable Teller Counter Acknowledgement Slips.

## Tech Stack

| Category | Technologies |
|---|---|
| UI & Workflow Framework | Streamlit |
| Computer Vision & OCR | Tesseract OCR (pytesseract), OpenCV (opencv-python-headless), Pillow |
| PDF & Token Generation | ReportLab, qrcode |
| Speech & Audio | HTML5 Web Speech API (webkitSpeechRecognition & SpeechSynthesisUtterance), Web Audio API Oscillator Beeps |
| Biometrics (Optional 2FA module) | OpenCV SFace / YuNet ONNX, DeepFace |

## Repository Structure

```
├── app.py                  # Core application (Customer Kiosk + Teller Portal)
├── requirements.txt        # Python library dependencies
├── packages.txt             # Linux OS dependencies for cloud deployment
├── .gitignore               # Excluded files (virtual environments, caches)
└── README.md                # Project documentation
```

## Installation & Local Setup

### 1. Prerequisites

- Python 3.10+
- Tesseract OCR for Windows (installed to `C:\Program Files\Tesseract-OCR`)

### 2. Clone the Repository

```bash
git clone https://github.com/<YOUR_GITHUB_USERNAME>/bank-kiosk-prototype.git
cd bank-kiosk-prototype
```

### 3. Create a Virtual Environment & Install Dependencies

```bash
# Windows
py -m venv venv
venv\Scripts\activate

# Install Python requirements
pip install -r requirements.txt
```

### 4. Run the Kiosk

```bash
streamlit run app.py
```

Open `http://localhost:8501` in Google Chrome or Microsoft Edge to allow microphone and camera permissions.

## Free Cloud Deployment (Streamlit Community Cloud)

1. Push this repository to GitHub.
2. Visit share.streamlit.io and log in with GitHub.
3. Click "New App" then select your repository and specify `app.py` as the main file path.
4. Streamlit Cloud automatically reads `packages.txt` to install system Tesseract binaries and deploys the app with full HTTPS / SSL encryption (enabling camera and microphone streaming across remote devices).

## Future Scope

- **Hardware Denomination Counter**: Integrating physical optical currency validator sensors to cross-verify cash deposit counts automatically.
- **Core Banking System (CBS) Integration**: REST API webhooks into core banking backends (Finacle/TCS BaNCS) for real-time ledger updates.
- **Passive Anti-Spoofing**: Eye Aspect Ratio (EAR) blink detection to prevent 2FA photo and video replay spoofing attacks.
