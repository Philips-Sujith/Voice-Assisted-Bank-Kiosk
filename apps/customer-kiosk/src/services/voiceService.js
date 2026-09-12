import { getTransactionLabel } from '../constants/transactions.js'

/*
  ============================================================
  VOICE AI CLIENT SERVICE (Frontend Connection to Module 2)
  ============================================================
  Connects to Vernacular Voice AI microservice over WebSocket (/ws/audio)
  and REST (/api/v1/parse, /api/v1/confirm).
*/

export const SAMPLE_PHRASES = {
  en: [
    'Withdraw 5000 rupees',
    'Deposit 10000 rupees',
    'I want to deposit one lakh rupees',
    'Check my balance',
    'Send 2000 rupees',
  ],
  ta: [
    'ஐந்தாயிரம் ரூபாய் எடுக்க வேண்டும்',
    'ஒரு லட்சம் ரூபாய் டெபாசிட் செய்ய வேண்டும்',
    'என் இருப்பை பார்க்க வேண்டும்',
  ],
  tanglish: [
    'Enakku 5000 rupees withdraw pannanum',
    '1 lakh deposit pannanum',
    'Balance check pannanum',
  ],
}

export function numberToTamilWords(num) {
  const map = {
    1000: 'ஆயிரம்',
    2000: 'இரண்டாயிரம்',
    5000: 'ஐந்தாயிரம்',
    10000: 'பத்தாயிரம்',
    25000: 'இருபத்தைந்தாயிரம்',
    50000: 'ஐம்பதாயிரம்',
    100000: 'ஒரு லட்சம்',
    150000: 'ஒன்றரை லட்சம்',
    200000: 'இரண்டு லட்சம்',
    9900000: 'தொண்ணூற்று ஒன்பது லட்சம்',
    10000000: 'ஒரு கோடி',
  }
  return map[num] || num
}

const WORD_AMOUNTS = [
  { pattern: /ஒரு\s*கோடி|கோடி/, amount: 10000000 },
  { pattern: /ஒன்றரை\s*லட்சம்/, amount: 150000 },
  { pattern: /இரண்டு\s*லட்சம்|ரெண்டு\s*லட்சம்/, amount: 200000 },
  { pattern: /ஒரு\s*லட்சம்|லட்சம்/, amount: 100000 },
  { pattern: /ஐம்பதாயிரம்/, amount: 50000 },
  { pattern: /இருபதாயிரம்/, amount: 20000 },
  { pattern: /பத்தாயிரம்/, amount: 10000 },
  { pattern: /ஐந்தாயிரம்|அஞ்சாயிரம்/, amount: 5000 },
  { pattern: /இரண்டாயிரம்/, amount: 2000 },
  { pattern: /ஆயிரம்/, amount: 1000 },
  { pattern: /\b(?:one|1)?\s*(?:lakhs?|lacs?)\b/i, amount: 100000 },
  { pattern: /\b(?:two|2)\s*(?:lakhs?|lacs?)\b/i, amount: 200000 },
  { pattern: /\b(?:two\s*lakh\s*fifty\s*thousand|2\.5\s*(?:lakh|lac))\b/i, amount: 250000 },
  { pattern: /\bfifty\s*thousand\b/i, amount: 50000 },
  { pattern: /\btwenty\s*five\s*thousand\b/i, amount: 25000 },
  { pattern: /\btwenty\s*thousand\b/i, amount: 20000 },
  { pattern: /\bten\s*thousand\b/i, amount: 10000 },
  { pattern: /\bfive\s*thousand\b/i, amount: 5000 },
  { pattern: /\btwo\s*thousand\b/i, amount: 2000 },
  { pattern: /\bone\s*thousand\b/i, amount: 1000 },
]

const AMOUNT_REQUIRED_INTENTS = ['withdraw', 'deposit', 'send_money']

const INTENT_PATTERNS = [
  ['balance_check', [/\bbalance\b/i, 'இருப்பு', 'இருப்பை', /\biruppu\w*/i]],
  ['withdraw', [/\bwithdraw\w*/i, 'எடுக்க', 'எடுக்கனும்', /\bedukka\w*/i]],
  ['deposit', [/\bdeposit\w*/i, 'டெபாசிட்', 'செலுத்த', 'போடு', /\bpodu\w*/i, /\bpodanum\b/i]],
  ['send_money', [/\bsend\b/i, /\btransfer\w*/i, 'அனுப்பு', /\banuppu\w*/i]],
  ['open_account', [/\bopen\s*(?:an?\s*)?account\b/i, /\bnew\s*account\b/i, 'புதிய கணக்கு', 'கணக்கு தொடங்க']],
]

function buildSpokenText(intent, amount, language) {
  const formattedAmt = amount != null ? `₹${amount.toLocaleString('en-IN')}` : ''
  const amountText = amount != null ? (language === 'ta' ? numberToTamilWords(amount) : formattedAmt) : ''
  const phrases = {
    en: {
      withdraw: `Please confirm: withdraw ${formattedAmt}?`,
      deposit: `Please confirm: deposit ${formattedAmt}?`,
      send_money: `Please confirm: send ${formattedAmt}?`,
      balance_check: `Sure, let me check your account balance.`,
      open_account: `I can help you open a new bank account.`,
      unknown: `Sorry, I didn't understand that request. Could you please repeat it?`,
    },
    ta: {
      withdraw: `நீங்கள் ${amountText} எடுக்க விரும்புகிறீர்களா?`,
      deposit: `நீங்கள் ${amountText} டெபாசிட் செய்ய விரும்புகிறீர்களா?`,
      send_money: `நீங்கள் ${amountText} அனுப்ப விரும்புகிறீர்களா?`,
      balance_check: `சரி, உங்கள் கணக்கு இருப்பை சரிபார்க்கிறேன்.`,
      open_account: `புதிய கணக்கு தொடங்க உதவுகிறேன்.`,
      unknown: `மன்னிக்கவும், புரியவில்லை. மீண்டும் சொல்ல முடியுமா?`,
    },
    tanglish: {
      withdraw: `Confirm pannunga: ${formattedAmt} withdraw pannalaama?`,
      deposit: `Confirm pannunga: ${formattedAmt} deposit pannalaama?`,
      send_money: `Confirm pannunga: ${formattedAmt} send pannalaama?`,
      balance_check: `Sari, unga balance check panren.`,
      open_account: `Pudhiya account open panna help panren.`,
      unknown: `Sorry, puriyala. Innoru muraiyaa sollunga?`,
    },
  }
  const set = phrases[language] || phrases.en
  return set[intent] || set.unknown
}

const AMOUNT_UNCLEAR_MESSAGE = "I couldn't clearly understand the amount. Please try again."

export function normalizeTranscript(rawText) {
  return String(rawText || '')
    .toLowerCase()
    .trim()
    .replace(/\s+/g, ' ')
}

export function detectIntent(normalizedText) {
  for (const [intent, patterns] of INTENT_PATTERNS) {
    const matched = patterns.some((pattern) =>
      pattern instanceof RegExp ? pattern.test(normalizedText) : normalizedText.includes(pattern),
    )
    if (matched) return intent
  }
  return 'unknown'
}

export function extractAmount(normalizedText) {
  if (!normalizedText) return null
  const cleaned = normalizedText.replace(/,/g, '').replace(/₹/g, '').replace(/rs\.?/g, '').trim()

  const wordMap = {
    one: 1, two: 2, three: 3, four: 4, five: 5,
    six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
    twenty: 20, 'twenty five': 25, thirty: 30, forty: 40, fifty: 50,
    'ninety nine': 99,
  }

  // 1. Crores (e.g. "1 crore", "1.5 crore", "one crore", "ஒரு கோடி")
  const croreMatch = cleaned.match(/(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|twenty|fifty|ninety\s*nine)\s*(?:crores?|cr\b|கோடி)/i)
  if (croreMatch) {
    const valStr = croreMatch[1].toLowerCase()
    const val = /^\d/.test(valStr) ? parseFloat(valStr) : (wordMap[valStr] || 1)
    return Math.round(val * 10000000)
  }

  // 2. Compound or decimal lakh (e.g. "1.5 lakh", "99 lakh", "two lakh fifty thousand", "1 lakh 20 thousand")
  const lakhMatch = cleaned.match(/(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|twenty|twenty\s*five|fifty|ninety\s*nine)\s*(?:lakhs?|lacs?|லட்சம்)(?:\s*(?:and\s*)?(\d+|fifty|twenty\s*five|twenty|ten)\s*thousand)?/i)
  if (lakhMatch) {
    const lStr = lakhMatch[1].toLowerCase()
    const thStr = lakhMatch[2]
    const lVal = /^\d/.test(lStr) ? parseFloat(lStr) : (wordMap[lStr] || 1)
    let thVal = 0
    if (thStr) {
      const thLower = thStr.toLowerCase()
      thVal = /^\d/.test(thLower) ? parseFloat(thLower) : (wordMap[thLower] || 0)
    }
    return Math.round(lVal * 100000 + thVal * 1000)
  }

  // 3. Standalone lakh / lac
  if (/\b(?:one|1)?\s*(?:lakh|lac|லட்சம்)\b/i.test(cleaned)) {
    return 100000
  }

  // 4. Thousands in words or digits (e.g. "twenty five thousand", "50 thousand", "50000")
  const thMatch = cleaned.match(/(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|twenty|twenty\s*five|fifty)\s*thousand/i)
  if (thMatch) {
    const thStr = thMatch[1].toLowerCase()
    const thVal = /^\d/.test(thStr) ? parseFloat(thStr) : (wordMap[thStr] || 1)
    return Math.round(thVal * 1000)
  }

  // 5. Word patterns
  for (const { pattern, amount } of WORD_AMOUNTS) {
    if (pattern.test(cleaned)) return amount
  }

  // 6. Plain digits
  const digitMatch = cleaned.match(/\b\d+\b/)
  if (digitMatch) {
    return parseInt(digitMatch[0], 10)
  }

  return null
}

function buildResponsePayload({ sessionId, language, transcript, intent, amount, recognitionConfidence }) {
  const amountRequired = AMOUNT_REQUIRED_INTENTS.includes(intent)
  const amountIsUnclear = amountRequired && amount === null
  const recognitionIsPoor = typeof recognitionConfidence === 'number' && recognitionConfidence < 0.55

  const needsClarification = intent === 'unknown' || amountIsUnclear || recognitionIsPoor

  let spokenText
  if (intent === 'unknown') {
    spokenText = buildSpokenText('unknown', null, language)
  } else if (needsClarification) {
    spokenText = AMOUNT_UNCLEAR_MESSAGE
  } else {
    spokenText = buildSpokenText(intent, amount, language)
  }

  return {
    session_id: sessionId,
    status: 'ok',
    language,
    intent,
    entities: {
      amount,
      account_number: 'XXXX1234',
      recipient: null,
    },
    confidence: needsClarification ? 0.4 : Math.min(0.95, recognitionConfidence ?? 0.9),
    raw_transcript: transcript,
    spoken_text: spokenText,
    transaction_label: getTransactionLabel(intent),
    needs_clarification: needsClarification,
  }
}

const VOICE_AI_WS_URL = (typeof window !== 'undefined' && window.__VOICE_AI_WS_URL__) || 'ws://localhost:8002/ws/audio'
const VOICE_AI_REST_URL = (typeof window !== 'undefined' && window.__VOICE_AI_REST_URL__) || 'http://localhost:8002'
const BACKEND_REST_URL = (typeof window !== 'undefined' && window.__BACKEND_REST_URL__) || 'http://localhost:8000'

class VoiceAIService {
  constructor() {
    this.connected = false
    this.sessionId = null
    this.preferredLanguage = 'en'
    this.ws = null
    this.pendingResolves = new Map()
  }

  async connect({ sessionId, preferredLanguage, sampleRate = 16000 }) {
    this.sessionId = sessionId
    this.preferredLanguage = preferredLanguage

    return new Promise((resolve) => {
      try {
        this.ws = new WebSocket(VOICE_AI_WS_URL)

        this.ws.onopen = () => {
          this.connected = true
          console.log('[voiceService] Connected to Voice AI WebSocket', {
            session_id: sessionId,
            preferred_language: preferredLanguage,
            sample_rate: sampleRate,
          })
          this.ws.send(
            JSON.stringify({
              type: 'init',
              session_id: sessionId,
              preferred_language: preferredLanguage,
              sample_rate: sampleRate,
            }),
          )
          resolve({ status: 'ok' })
        }

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            console.log('[voiceService] WebSocket received:', data)
            if (data.type === 'confirmation_result') {
              const confirmResolver = this.pendingResolves.get('confirm')
              if (confirmResolver) {
                confirmResolver(data)
                this.pendingResolves.delete('confirm')
              }
              return
            }

            const resolver = this.pendingResolves.get('message')
            if (resolver) {
              resolver(data)
              this.pendingResolves.delete('message')
            }
          } catch (e) {
            console.error('[voiceService] Failed to parse response:', e)
          }
        }

        this.ws.onerror = (err) => {
          console.warn('[voiceService] WebSocket error, REST fallback ready:', err)
          this.connected = true
          resolve({ status: 'ok', fallback: true })
        }

        this.ws.onclose = () => {
          this.connected = false
        }

        setTimeout(() => {
          if (!this.connected) {
            this.connected = true
            resolve({ status: 'ok', fallback: true })
          }
        }, 1500)
      } catch (e) {
        this.connected = true
        resolve({ status: 'ok', fallback: true })
      }
    })
  }

  async sendMessage(rawText, recognitionConfidence = 1) {
    if (!rawText || !rawText.trim()) {
      throw new Error('No speech or text was captured.')
    }

    // 1. Try real WebSocket if connected and open
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        const responsePromise = new Promise((resolve, reject) => {
          this.pendingResolves.set('message', resolve)
          setTimeout(() => {
            if (this.pendingResolves.has('message')) {
              this.pendingResolves.delete('message')
              reject(new Error('Voice AI timeout'))
            }
          }, 3500)
        })

        this.ws.send(
          JSON.stringify({
            session_id: this.sessionId,
            text: rawText,
            confidence: recognitionConfidence,
            preferred_language: this.preferredLanguage,
          }),
        )

        const res = await responsePromise
        return {
          ...res,
          transaction_label: getTransactionLabel(res.intent),
          needs_clarification: res.confidence < 0.7 || res.intent === 'unknown',
        }
      } catch (err) {
        console.warn('[voiceService] WS sendMessage failed, trying REST:', err)
      }
    }

    // 2. Try REST parse endpoint with AbortSignal timeout
    try {
      const restResp = await fetch(`${VOICE_AI_REST_URL}/api/v1/parse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: this.sessionId,
          text: rawText,
          preferred_language: this.preferredLanguage,
          recognition_confidence: recognitionConfidence,
          forward_to_backend: true,
        }),
        signal: AbortSignal.timeout(3500),
      })
      if (restResp.ok) {
        const res = await restResp.json()
        return {
          ...res,
          transaction_label: getTransactionLabel(res.intent),
          needs_clarification: res.confidence < 0.7 || res.intent === 'unknown',
        }
      }
    } catch (restErr) {
      console.warn('[voiceService] REST parse failed, using local parser:', restErr)
    }

    // 3. Robust local parser fallback (guaranteed synchronous terminal state)
    const transcript = normalizeTranscript(rawText)
    const intent = detectIntent(transcript)
    const amount = AMOUNT_REQUIRED_INTENTS.includes(intent) ? extractAmount(transcript) : null

    // Sync to backend in background if possible
    try {
      fetch(`${BACKEND_REST_URL}/api/v1/voice-intent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: this.sessionId,
          status: 'ok',
          language: this.preferredLanguage,
          intent,
          requires_auth: true,
          entities: { amount },
          confidence: recognitionConfidence,
          raw_transcript: transcript,
        }),
        signal: AbortSignal.timeout(3000),
      }).catch((e) => console.warn('[voiceService] Local fallback backend sync notice:', e))
    } catch (e) {}

    return buildResponsePayload({
      sessionId: this.sessionId,
      language: this.preferredLanguage,
      transcript,
      intent,
      amount,
      recognitionConfidence,
    })
  }

  async confirm(confirmed = true, transactionData = {}) {
    const payload = {
      session_id: this.sessionId,
      confirmed: confirmed,
    }
    if (transactionData.amount !== undefined && transactionData.amount !== null) {
      payload.amount = Number(transactionData.amount)
    }
    if (transactionData.transaction_type) {
      payload.transaction_type = transactionData.transaction_type
    }
    if (transactionData.customer_id) {
      payload.customer_id = transactionData.customer_id
    }

    console.log('BACKEND REQUEST PAYLOAD:', payload)

    // 1. Try Voice AI WebSocket
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        const confirmPromise = new Promise((resolve) => {
          this.pendingResolves.set('confirm', resolve)
          setTimeout(() => resolve(null), 3500)
        })
        this.ws.send(
          JSON.stringify({
            type: 'confirm',
            ...payload,
          }),
        )
        const res = await confirmPromise
        if (res && res.backend_response?.status === 'ok') return res
      } catch (e) {
        console.warn('[voiceService] WS confirm failed:', e)
      }
    }

    // 2. Try Voice AI REST confirm endpoint
    try {
      const restResp = await fetch(`${VOICE_AI_REST_URL}/api/v1/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(3500),
      })
      if (restResp.ok) {
        const backend_response = await restResp.json()
        if (backend_response.status === 'ok') {
          return { type: 'confirmation_result', session_id: this.sessionId, confirmed, backend_response }
        }
      }
    } catch (e) {
      console.warn('[voiceService] Voice AI REST confirm failed:', e)
    }

    // 3. Try Direct Backend confirmation endpoint
    try {
      const backendResp = await fetch(`${BACKEND_REST_URL}/api/v1/session/${this.sessionId}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(4000),
      })
      if (backendResp.ok) {
        const backend_response = await backendResp.json()
        return { type: 'confirmation_result', session_id: this.sessionId, confirmed, backend_response }
      } else {
        const errJson = await backendResp.json().catch(() => ({}))
        const errorMsg = errJson.detail?.error_message || `Backend error: ${backendResp.status}`
        throw new Error(errorMsg)
      }
    } catch (backendErr) {
      console.error('[voiceService] Backend direct confirm failed:', backendErr)
      throw backendErr
    }
  }

  disconnect() {
    this.connected = false
    if (this.ws) {
      try {
        this.ws.close()
      } catch (e) {}
      this.ws = null
    }
  }
}

export default VoiceAIService
