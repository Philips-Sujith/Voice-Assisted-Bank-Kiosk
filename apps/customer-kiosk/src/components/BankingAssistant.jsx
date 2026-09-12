import { useEffect, useRef, useState } from 'react'
import AIOrb from './AIOrb.jsx'
import { replayVoiceResponse, speakText, stopSpeechOutput } from '../services/ttsService.js'
import { translate } from '../services/translations.js'

// SCREEN 4: AI BANKING ASSISTANT (main screen)
//
// Voice input pipeline, in order (UNCHANGED from the previous version):
//   1. Speech recognition/transcript - the browser's native
//      SpeechRecognition API listens and returns exactly what it heard.
//      That transcript is shown on screen immediately, before anything
//      is sent for processing, so it's easy to debug what was heard.
//   2. Intent detection + amount extraction - handled entirely by
//      voiceService.js (see that file for the normalize -> intent ->
//      amount stages). This component never guesses either one itself.
//
// Text input remains a fully-supported fallback and is treated as
// maximum-confidence input (there's no ambiguity in typed text).
//
// NEW in this redesign: the small mic circle is now a large central
// AI orb (see AIOrb.jsx) that IS the mic button, plus a row of quick
// action shortcut cards. Both call the exact same handlers as before
// (handleMicClick / handleChipClick) - no voice/text logic changed.

const LANGUAGE_LABEL = { ta: 'தமிழ்', en: 'English', tanglish: 'Tanglish' }

// Maps our app's language codes to BCP-47 tags the Web Speech API expects.
const RECOGNITION_LANG = { ta: 'ta-IN', en: 'en-IN', tanglish: 'en-IN' }
const SPEECH_TIMEOUT_MS = 10000

const SpeechRecognitionAPI =
  typeof window !== 'undefined'
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : null

// Quick action shortcuts. These reuse handleChipClick exactly like the
// old sample-phrase chips did - they're just canned trigger phrases,
// not a separate code path. Kept in English on purpose: intent
// detection in voiceService.js matches on keyword content, not on the
// kiosk's display language, so these work no matter which language is
// selected.
const QUICK_ACTIONS = [
  { label: 'Withdraw Cash', phrase: 'Withdraw 5000 rupees', icon: '↓' },
  { label: 'Deposit Money', phrase: 'Deposit 10000 rupees', icon: '↑' },
  { label: 'Check Balance', phrase: 'Check my balance', icon: '≡' },
  { label: 'Send Money', phrase: 'Send 2000 rupees', icon: '→' },
]

export default function BankingAssistant({
  preferredLanguage,
  customerName,
  aiResponse,
  cancellationNotice,
  transactionStage,
  voiceFeedback,
  loading,
  onSubmit,
  onCancel,
}) {
  const [typedText, setTypedText] = useState('')
  const [listening, setListening] = useState(false)
  const [lastUserMessage, setLastUserMessage] = useState(null)
  const [micNotice, setMicNotice] = useState(null)

  const audioCtxRef = useRef(null)
  const analyserRef = useRef(null)
  const streamRef = useRef(null)
  const rafRef = useRef(null)
  const canvasRef = useRef(null)
  const recognitionRef = useRef(null)
  const speechTimeoutRef = useRef(null)
  const speechDeadlineRef = useRef(0)
  const lastSpeechActivityRef = useRef(0)
  const hasUsableTranscriptRef = useRef(false)
  const submittedTranscriptRef = useRef(false)
  const manuallyStoppedRef = useRef(false)

  // --- Waveform drawing loop (visual only, does not affect recognition) ---
  const drawWaveform = () => {
    const canvas = canvasRef.current
    const analyser = analyserRef.current
    if (!canvas || !analyser) return

    const ctx = canvas.getContext('2d')
    const bufferLength = analyser.fftSize
    const dataArray = new Uint8Array(bufferLength)
    analyser.getByteTimeDomainData(dataArray)

    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.lineWidth = 3
    ctx.strokeStyle = '#22d3ee'
    ctx.beginPath()

    const sliceWidth = canvas.width / bufferLength
    let x = 0
    for (let i = 0; i < bufferLength; i++) {
      const v = dataArray[i] / 128.0
      const y = (v * canvas.height) / 2
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
      x += sliceWidth
    }
    ctx.lineTo(canvas.width, canvas.height / 2)
    ctx.stroke()

    rafRef.current = requestAnimationFrame(drawWaveform)
  }

  const stopWaveform = () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    rafRef.current = null
    streamRef.current?.getTracks().forEach((track) => track.stop())
    audioCtxRef.current?.close()
    streamRef.current = null
    audioCtxRef.current = null
    analyserRef.current = null

    const canvas = canvasRef.current
    if (canvas) canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height)
  }

  const startWaveform = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      console.info('[BankingAssistant] microphone permission granted')
      streamRef.current = stream

      const AudioContext = window.AudioContext || window.webkitAudioContext
      const audioCtx = new AudioContext()
      const source = audioCtx.createMediaStreamSource(stream)
      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 2048
      source.connect(analyser)

      audioCtxRef.current = audioCtx
      analyserRef.current = analyser
      drawWaveform()
      return true
    } catch (err) {
      // Waveform is cosmetic only - recognition still works without it.
      console.warn('[BankingAssistant] microphone permission or access failed', err.name, err.message)
      return false
    }
  }

  const getMicrophonePermission = async () => {
    if (!navigator.permissions?.query) return 'unknown'
    try {
      const { state } = await navigator.permissions.query({ name: 'microphone' })
      console.info('[BankingAssistant] microphone permission status', state)
      return state
    } catch (error) {
      console.warn('[BankingAssistant] microphone permission status unavailable', error.message)
      return 'unknown'
    }
  }

  // --- Real speech recognition (Stage 1: speech recognition/transcript) ---
  const startListening = async () => {
    console.info('[BankingAssistant] speech recognition support detected', Boolean(SpeechRecognitionAPI))
    console.info('[BankingAssistant] selected recognition language', RECOGNITION_LANG[preferredLanguage] || 'en-IN')
    stopSpeechOutput()
    setMicNotice(null)
    setListening(true)
    manuallyStoppedRef.current = false
    hasUsableTranscriptRef.current = false
    submittedTranscriptRef.current = false
    lastSpeechActivityRef.current = Date.now()
    speechDeadlineRef.current = Date.now() + SPEECH_TIMEOUT_MS
    clearTimeout(speechTimeoutRef.current)
    if (!SpeechRecognitionAPI) {
      console.warn('[BankingAssistant] SpeechRecognition is not supported in this browser')
      setMicNotice(
        'Speech recognition is not supported in this browser. Please use a quick action below or type your request.',
      )
      setListening(false)
      stopWaveform()
      return
    }

    const permissionState = await getMicrophonePermission()
    if (permissionState === 'denied') {
      setListening(false)
      setMicNotice('Microphone access is blocked. Allow microphone access for this site, then try again.')
      console.error('[BankingAssistant] microphone permission denied')
      return
    }

    if (!(await startWaveform())) {
      setListening(false)
      setMicNotice('Microphone access is unavailable. Check browser permissions, then try again.')
      return
    }

    const recognition = new SpeechRecognitionAPI()
    recognition.lang = RECOGNITION_LANG[preferredLanguage] || 'en-IN'
    recognition.continuous = true
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    const scheduleSpeechTimeout = () => {
      clearTimeout(speechTimeoutRef.current)
      const now = Date.now()
      const silenceDeadline = lastSpeechActivityRef.current + SPEECH_TIMEOUT_MS
      const deadline = Math.max(speechDeadlineRef.current, silenceDeadline)
      speechTimeoutRef.current = setTimeout(() => {
        if (hasUsableTranscriptRef.current || submittedTranscriptRef.current) return

        if (Date.now() < deadline || Date.now() - lastSpeechActivityRef.current < SPEECH_TIMEOUT_MS) {
          scheduleSpeechTimeout()
          return
        }

        manuallyStoppedRef.current = true
        recognition.stop()
        recognitionRef.current = null
        setListening(false)
        setMicNotice("Couldn't hear you. Please try again or type your request.")
        stopWaveform()
      }, Math.max(0, deadline - now))
    }

    recognition.onresult = (event) => {
      const result = event.results[event.resultIndex][0]
      const transcript = result.transcript
      console.info('[BankingAssistant] raw transcript received', transcript)
      setLastUserMessage(transcript)
      if (transcript.trim()) {
        lastSpeechActivityRef.current = Date.now()
        scheduleSpeechTimeout()
      }

      if (!event.results[event.resultIndex].isFinal || !transcript.trim() || submittedTranscriptRef.current) return

      const normalizedTranscript = transcript.trim().toLowerCase()
      if (/^cancel(?: transaction)?[.!]?$/i.test(normalizedTranscript) ||
        ['ரத்து', 'ரத்து செய்', 'பரிவர்த்தனையை ரத்து செய்'].includes(normalizedTranscript)) {
        submittedTranscriptRef.current = true
        clearTimeout(speechTimeoutRef.current)
        recognition.stop()
        onCancel()
        return
      }

      hasUsableTranscriptRef.current = true
      submittedTranscriptRef.current = true
      clearTimeout(speechTimeoutRef.current)
      recognition.stop()
      // Some browsers don't report a real confidence value (0 in that
      // case) - treat that as "unknown" rather than "definitely bad".
      const confidence =
        typeof result.confidence === 'number' && result.confidence > 0
          ? result.confidence
          : 0.85

      // Show exactly what the browser heard BEFORE sending it off for
      // intent/amount processing, so it's easy to debug what was heard.
      onSubmit(transcript, confidence)
    }

    recognition.onerror = (event) => {
      console.error('[BankingAssistant] speech recognition error', event.error, event.message || '')
      if (event.error !== 'no-speech') {
        setMicNotice(`Voice recognition error: ${event.error}. Check microphone permissions and try again.`)
      }
    }

    recognition.onend = () => {
      console.info('[BankingAssistant] speech recognition ended')
      if (!manuallyStoppedRef.current && !submittedTranscriptRef.current && Date.now() < speechDeadlineRef.current) {
        try {
          recognition.start()
          console.info('[BankingAssistant] speech recognition restarted')
        } catch (error) {
          console.error('[BankingAssistant] speech recognition restart failed', error.message)
          setListening(false)
          stopWaveform()
        }
        return
      }

      setListening(false)
      stopWaveform()
    }

    recognitionRef.current = recognition
    try {
      recognition.start()
      console.info('[BankingAssistant] speech recognition started')
    } catch (error) {
      console.error('[BankingAssistant] speech recognition start failed', error.message)
      recognitionRef.current = null
      setListening(false)
      setMicNotice('Voice recognition could not start. Check microphone permissions and try again.')
      stopWaveform()
      return
    }
    scheduleSpeechTimeout()
  }

  const stopListening = () => {
    manuallyStoppedRef.current = true
    clearTimeout(speechTimeoutRef.current)
    recognitionRef.current?.stop()
    recognitionRef.current = null
    setListening(false)
    stopWaveform()
  }

  const handleMicClick = () => {
    if (loading) return
    if (listening) stopListening()
    else startListening()
  }

  // Typed text is unambiguous, so it's sent with full confidence (1).
  const handleTextSend = () => {
    if (!typedText.trim() || loading) return
    setLastUserMessage(typedText)
    onSubmit(typedText, 1)
    setTypedText('')
  }

  // Quick-phrase shortcuts (both the quick action cards) are exact,
  // known strings - also sent with full confidence.
  const handleChipClick = (phrase) => {
    if (loading) return
    setLastUserMessage(phrase)
    onSubmit(phrase, 1)
  }

  useEffect(() => {
    return () => {
      manuallyStoppedRef.current = true
      clearTimeout(speechTimeoutRef.current)
      recognitionRef.current?.stop()
      stopWaveform()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (transactionStage !== 'amount') return undefined

    let cancelled = false
    const delayRef = { current: null }
    const prompt = translate(preferredLanguage || 'en', 'amountEntryPrompt')
    const textToSpeak = typeof prompt === 'function' ? prompt(voiceFeedback?.intent) : prompt
    speakText(textToSpeak, preferredLanguage || 'en')
      .then(() => {
        if (!cancelled) {
          delayRef.current = window.setTimeout(() => {
            if (!cancelled) startListening()
          }, 300)
        }
      })

    return () => {
      cancelled = true
      if (delayRef.current) window.clearTimeout(delayRef.current)
    }
    // The stage transition is the trigger; startListening reads current props.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [transactionStage])

  const orbState = listening ? 'listening' : loading ? 'processing' : 'idle'
  const statusText = listening
    ? translate(preferredLanguage, 'listening')
    : loading
      ? translate(preferredLanguage, 'processing')
      : translate(preferredLanguage, 'howCanIHelp')

  const quickActionItems = [
    {
      label: translate(preferredLanguage, 'quickWithdraw'),
      phrase: preferredLanguage === 'ta' ? '1000 ரூபாய் எடுக்க வேண்டும்' : 'Withdraw 5000 rupees',
      icon: '↓',
    },
    {
      label: translate(preferredLanguage, 'quickDeposit'),
      phrase: preferredLanguage === 'ta' ? '1000 ரூபாய் டெபாசிட் செய்ய வேண்டும்' : 'Deposit 10000 rupees',
      icon: '↑',
    },
    {
      label: translate(preferredLanguage, 'quickBalance'),
      phrase: preferredLanguage === 'ta' ? 'என் இருப்பை பார்க்க வேண்டும்' : 'Check my balance',
      icon: '≡',
    },
    {
      label: translate(preferredLanguage, 'quickSend'),
      phrase: preferredLanguage === 'ta' ? '2000 ரூபாய் அனுப்ப வேண்டும்' : 'Send 2000 rupees',
      icon: '→',
    },
  ]

  return (
    <section className="screen screen--assistant">
      <div className="assistant-topbar">
        <span className="assistant-topbar__greeting">
          {customerName ? `${translate(preferredLanguage, 'greeting')}, ${customerName}` : translate(preferredLanguage, 'greeting')}
        </span>
        <div className="assistant-topbar__status">
          <span className="session-chip">
            <span className="session-chip__dot" aria-hidden="true" />
            {translate(preferredLanguage, 'sessionActive')}
          </span>
          <span className="language-pill">
            {LANGUAGE_LABEL[preferredLanguage] || 'English'}
          </span>
        </div>
      </div>

      <div className="ai-stage">
        <button
          className="orb-button"
          onClick={handleMicClick}
          disabled={loading}
          aria-pressed={listening}
          aria-label={listening ? 'Stop listening' : 'Start listening'}
        >
          <AIOrb state={orbState} size={200} />
        </button>

        <p className="ai-stage__status">{statusText}</p>
        <p className="ai-stage__hint">
          {listening ? translate(preferredLanguage, 'tapToStop') : translate(preferredLanguage, 'tapToSpeak')}
        </p>

        <canvas ref={canvasRef} width="220" height="34" className="waveform" />

        {micNotice && <p className="mic-notice">{micNotice}</p>}
        <p className="voice-state" role="status">
          {translate(preferredLanguage, 'currentState')} {transactionStage === 'amount' ? translate(preferredLanguage, 'stateAmount') : translate(preferredLanguage, 'stateSelection')}
          {voiceFeedback?.intent && ` | ${translate(preferredLanguage, 'recognizedIntent')} ${voiceFeedback.intent}`}
          {voiceFeedback?.value != null && ` | ${translate(preferredLanguage, 'recognizedValue')} ${voiceFeedback.value}`}
        </p>
        {voiceFeedback?.message && <p className="mic-notice" role="alert">{voiceFeedback.message}</p>}
      </div>

      <div className="quick-actions">
        {quickActionItems.map((action) => (
          <button
            key={action.label}
            className="quick-action-card"
            onClick={() => handleChipClick(action.phrase)}
            disabled={loading}
          >
            <span className="quick-action-card__icon" aria-hidden="true">
              {action.icon}
            </span>
            {action.label}
          </button>
        ))}
      </div>

      <div className="conversation">
        {lastUserMessage && (
          <div className="bubble bubble--user">
            <span className="bubble__label">You said</span>
            <p>{lastUserMessage}</p>
          </div>
        )}

        {loading && (
          <div className="bubble bubble--ai bubble--loading">
            <span className="bubble__label">AI Assistant</span>
            <div className="typing-dots">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}

        {!loading && aiResponse?.spoken_text && (
          <div className="bubble bubble--ai">
            <span className="bubble__label">AI Assistant</span>
            <p>{aiResponse.spoken_text}</p>
            <button
              className="listen-again-button"
              type="button"
              onClick={() => replayVoiceResponse(aiResponse, preferredLanguage)}
              aria-label="Listen again to the AI response"
            >
              🔊 {translate(preferredLanguage, 'listenAgain')}
            </button>
          </div>
        )}

        {!lastUserMessage && !loading && !aiResponse && (
          cancellationNotice ? (
            <p className="mic-notice" role="status">{cancellationNotice}</p>
          ) : (
          <p className="conversation__placeholder">
            {translate(preferredLanguage, 'placeholderPlaceholder')}
          </p>
          )
        )}
      </div>

      <div className="text-fallback">
        <input
          type="text"
          value={typedText}
          placeholder={transactionStage === 'amount' ? translate(preferredLanguage, 'placeholderAmount') : translate(preferredLanguage, 'placeholderType')}
          onChange={(e) => setTypedText(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleTextSend()}
          disabled={loading}
        />
        <button
          className="btn btn--primary"
          onClick={handleTextSend}
          disabled={loading}
          id="btn-next-transaction"
          aria-label={transactionStage === 'amount' ? 'Next' : 'Send'}
        >
          {transactionStage === 'amount'
            ? (translate(preferredLanguage, 'next') || 'Next')
            : (translate(preferredLanguage, 'send') || 'Send')}
        </button>
      </div>

      <div className="assistant-cancel-action">
        <button
          className="btn btn--danger btn--lg"
          type="button"
          onClick={onCancel}
          aria-label="Cancel current transaction"
        >
          {translate(preferredLanguage, 'cancelTransaction')}
        </button>
      </div>
    </section>
  )
}
