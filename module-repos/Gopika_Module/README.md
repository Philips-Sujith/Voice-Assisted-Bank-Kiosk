# AI Smart Banking — Frontend & Edge Kiosk (Module 1)

Voice-assisted banking kiosk UI, built with React + Vite. This is **only**
the Frontend & Edge Kiosk module — it talks to Voice AI (Module 2) using the
fixed interface contract, and mocks that module locally until it's ready.

## Run it

```bash
npm install
npm run dev
```

Then open the printed `localhost` URL. For the full kiosk feel, use your
browser's fullscreen mode (F11).

> The first time you use the mic on the assistant screen, your browser will
> ask for microphone permission. If you decline (or there's no mic), the
> demo still works — it just skips the live waveform and goes straight to a
> simulated recognized phrase.

## How the six screens connect

```
Welcome → Language Selection → Authentication (simulated)
   → AI Banking Assistant → Confirmation → Success
                                  ↓
                             Error / Retry
```

`App.jsx` owns all shared state (`currentScreen`, `sessionId`,
`preferredLanguage`, `userInput`, `aiResponse`, `transactionType`,
`transactionAmount`, `loading`, `error`) and renders exactly one screen
component at a time based on `currentScreen`. Each screen is a plain
function component that receives only the data and callback handlers it
needs — no routing library, no Redux, just `useState` + props.

## How the mock Voice AI works

`src/services/voiceService.js` stands in for Module 2 until it's built. It:

1. `connect()` — pretends to open the WebSocket and "sends" the one-time
   session metadata (`session_id`, `preferred_language`, `sample_rate`).
2. `sendMessage(text)` — takes either a typed message or a recognized mic
   phrase, runs simple keyword matching (English/Tamil/Tanglish) to guess an
   `intent` and `amount`, and resolves with the **exact fixed response
   shape** (`session_id`, `spoken_text`, `language`), plus extra fields
   (`intent`, `entities`, `confidence`) the rest of the UI uses to drive the
   Confirmation screen.

Since real speech-to-text isn't part of this module, the mic button records
real audio (for the live waveform, via the Web Audio API) but the
"recognized" transcript is picked from a small set of sample phrases per
language — the same ones listed in the mock's `SAMPLE_PHRASES` export.
Typing your own text always works and is matched the same way.

**Do not rename any field in the fixed contract.** If the real Voice AI
module needs something different, that's a team decision — flag it in
`kiosk_module_interfaces.md`, don't change it here quietly.

## Project structure

```
src/
├── components/
│   ├── Welcome.jsx
│   ├── LanguageSelection.jsx
│   ├── Authentication.jsx
│   ├── BankingAssistant.jsx
│   ├── Confirmation.jsx
│   ├── Success.jsx
│   └── ErrorScreen.jsx
├── services/
│   └── voiceService.js
├── App.jsx
├── App.css
├── index.css
└── main.jsx
```

## Swapping in the real Voice AI later

When Module 2 is ready, replace the contents of `voiceService.js` with a
real WebSocket client that sends/receives the same fixed JSON shapes. Nothing
in `App.jsx` or the components needs to change, since they only depend on
that response shape — not on how it's produced.
