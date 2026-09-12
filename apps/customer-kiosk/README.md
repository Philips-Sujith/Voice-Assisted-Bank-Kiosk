# Customer Kiosk Application

Modern, high-contrast, accessible customer-facing frontend for the AI Voice-Assisted Banking Kiosk platform.

## Overview
The Customer Kiosk provides a streamlined, full-screen touchscreen and voice-driven banking experience for branch patrons. Built with React and Vite, it supports bilingual voice interactions, contactless biometric face authentication, dynamic account operations, and digital receipt generation.

## Features
- **Multilingual Interface**: Native support for English and Tamil with high-contrast accessibility themes.
- **Biometric Face Authentication**: Integration with the Identity Service for secure face recognition, liveness verification, and anti-spoofing.
- **Vernacular Voice Assistant**: Interactive conversational banking assistant with live waveform visualizer and speech-to-text feedback.
- **Core Banking Operations**:
  - Cash Withdrawal
  - Cash Deposit
  - Balance Enquiry
  - Fund Transfers
- **Cryptographic QR & Receipt Generation**: Instant on-screen display of HMAC-signed security QR tokens and print/downloadable PDF receipts matching branch teller standards.

## Project Structure
```
apps/customer-kiosk/
├── src/
│   ├── components/       # Kiosk screens (Welcome, Language, Auth, Voice, Confirm, Success)
│   ├── services/         # API integration services (voiceService, receiptService)
│   ├── styles/           # CSS design systems and animations
│   ├── pages/            # Sub-applications (FaceEnrollmentApp)
│   ├── App.jsx           # Main kiosk orchestration
│   └── main.jsx          # Application entry point
├── public/               # Static assets & brand icons
├── index.html            # Main HTML template
├── package.json          # Node dependencies and scripts
└── vite.config.js        # Vite build configuration
```

## Running Locally
```bash
npm install
npm run dev
# Running on http://localhost:5173
```
