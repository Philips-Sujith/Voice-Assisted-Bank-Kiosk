import { useState, useCallback, useEffect, useRef } from 'react'
import Header from './components/Header.jsx'
import Welcome from './components/Welcome.jsx'
import LanguageSelection from './components/LanguageSelection.jsx'
import Authentication from './components/Authentication.jsx'
import BankingAssistant from './components/BankingAssistant.jsx'
import Confirmation from './components/Confirmation.jsx'
import Success from './components/Success.jsx'
import ErrorScreen from './components/ErrorScreen.jsx'
import ProgressIndicator from './components/ProgressIndicator.jsx'
import VoiceAIService, { detectIntent, extractAmount, normalizeTranscript } from './services/voiceService.js'
import { getTransactionLabel } from './constants/transactions.js'
import { speakGuidance, speakText, stopSpeechOutput } from './services/ttsService.js'
import { translate } from './services/translations.js'
import './App.css'

// Simple UUID v4-ish generator - good enough for a hackathon demo.
// (crypto.randomUUID() would also work in modern browsers, this is
// just explicit so it's easy to understand.)
function generateSessionId() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

const INACTIVITY_TIMEOUT_MS = 30000
const INACTIVITY_WARNING_SECONDS = 30
const SpeechRecognitionAPI =
  typeof window !== 'undefined'
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : null

function generateSessionUuid() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

export default function App() {
  // ---- Core navigation state ----
  const [currentScreen, setCurrentScreen] = useState('welcome')

  // ---- Session state (shared across every screen) ----
  const [sessionId, setSessionId] = useState(generateSessionUuid)
  const [preferredLanguage, setPreferredLanguage] = useState(null)
  const [authenticatedCustomer, setAuthenticatedCustomer] = useState(null)

  // ---- Conversation state ----
  const [userInput, setUserInput] = useState('')
  const [aiResponse, setAiResponse] = useState(null) // full response object from Voice AI

  // ---- Transaction state ----
  const [transactionType, setTransactionType] = useState(null)
  const [transactionAmount, setTransactionAmount] = useState(null)
  const [transactionIntent, setTransactionIntent] = useState(null)
  const [transactionStage, setTransactionStage] = useState('selection')
  const [voiceFeedback, setVoiceFeedback] = useState(null)

  // ---- UI state ----
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [cancellationNotice, setCancellationNotice] = useState(null)
  const [backendTokenInfo, setBackendTokenInfo] = useState(null)
  const [inactivityWarning, setInactivityWarning] = useState(false)
  const [inactivitySeconds, setInactivitySeconds] = useState(INACTIVITY_WARNING_SECONDS)

  // The mock Voice AI service instance lives for the whole session.
  const voiceServiceRef = useRef(null)
  const inactivityTimerRef = useRef(null)
  const inactivityCountdownRef = useRef(null)
  const inactivityRecognitionRef = useRef(null)
  const inactivityVoiceFlowRef = useRef(0)
  const resetInactivityTimerRef = useRef(null)

  // ---------------- Navigation helpers ----------------

  const goTo = useCallback((screen) => setCurrentScreen(screen), [])

  const clearInactivityTimers = useCallback(() => {
    clearTimeout(inactivityTimerRef.current)
    clearInterval(inactivityCountdownRef.current)
    inactivityTimerRef.current = null
    inactivityCountdownRef.current = null
  }, [])

  // Ends a session locally and clears all data that could belong to the
  // previous customer before the kiosk returns to its public welcome screen.
  const endSession = useCallback(() => {
    clearInactivityTimers()
    inactivityVoiceFlowRef.current += 1
    inactivityRecognitionRef.current?.stop()
    inactivityRecognitionRef.current = null
    voiceServiceRef.current?.disconnect()
    voiceServiceRef.current = null
    stopSpeechOutput()
    setInactivityWarning(false)
    setInactivitySeconds(INACTIVITY_WARNING_SECONDS)
    setSessionId(null)
    setPreferredLanguage(null)
    setUserInput('')
    setAiResponse(null)
    setTransactionType(null)
    setTransactionAmount(null)
    setTransactionIntent(null)
    setTransactionStage('selection')
    setVoiceFeedback(null)
    setError(null)
    setCancellationNotice(null)
    setBackendTokenInfo(null)
    setAuthenticatedCustomer(null)
    setLoading(false)
    goTo('welcome')
  }, [clearInactivityTimers, goTo])

  const showInactivityWarning = useCallback(() => {
    clearInactivityTimers()
    setInactivityWarning(true)
    setInactivitySeconds(INACTIVITY_WARNING_SECONDS)

    const flowId = ++inactivityVoiceFlowRef.current
    const startWarningRecognition = () => {
      if (!SpeechRecognitionAPI || flowId !== inactivityVoiceFlowRef.current) return

      const recognition = new SpeechRecognitionAPI()
      recognition.lang = preferredLanguage === 'ta' ? 'ta-IN' : 'en-IN'
      recognition.interimResults = false
      recognition.maxAlternatives = 1
      recognition.onresult = (event) => {
        const command = event.results[0][0].transcript
          .trim()
          .toLowerCase()
          .replace(/[.!?,]+$/g, '')
          .trim()
        if (/^(yes|continue|continue session)$/i.test(command) || ['ஆம்', 'தொடரவும்'].includes(command)) {
          recognition.stop()
          resetInactivityTimerRef.current?.()
        }
      }
      recognition.onerror = () => {
        if (inactivityRecognitionRef.current === recognition) inactivityRecognitionRef.current = null
      }
      recognition.onend = () => {
        if (inactivityRecognitionRef.current === recognition) inactivityRecognitionRef.current = null
      }

      inactivityRecognitionRef.current = recognition
      try {
        recognition.start()
      } catch (error) {
        console.warn('[App] inactivity voice recognition could not start', error.message)
        inactivityRecognitionRef.current = null
      }
    }

    speakText(translate(preferredLanguage || 'en', 'continueSessionQuestion'), preferredLanguage || 'en')
      .then(() => window.setTimeout(startWarningRecognition, 300))

    let secondsRemaining = INACTIVITY_WARNING_SECONDS
    inactivityCountdownRef.current = setInterval(() => {
      secondsRemaining -= 1
      setInactivitySeconds(secondsRemaining)
      if (secondsRemaining <= 0) endSession()
    }, 1000)
  }, [clearInactivityTimers, endSession, preferredLanguage])

  const startInactivityTimer = useCallback(() => {
    clearInactivityTimers()
    setInactivityWarning(false)
    setInactivitySeconds(INACTIVITY_WARNING_SECONDS)
    inactivityTimerRef.current = setTimeout(showInactivityWarning, INACTIVITY_TIMEOUT_MS)
  }, [clearInactivityTimers, showInactivityWarning])

  const resetInactivityTimer = useCallback(() => {
    if (!sessionId) return
    startInactivityTimer()
  }, [sessionId, startInactivityTimer])
  resetInactivityTimerRef.current = resetInactivityTimer

  const startSession = useCallback(() => {
    setSessionId(generateSessionId())
    startInactivityTimer()
    goTo('language')
  }, [goTo, startInactivityTimer])

  const selectLanguage = useCallback(
    (langCode) => {
      setPreferredLanguage(langCode)
      goTo('auth')
    },
    [goTo],
  )

  const completeAuthentication = useCallback(async (authData) => {
    console.log('[Kiosk] Biometric authentication callback:', authData)
    if (!authData || authData.auth_status !== 'pass' || !authData.customer_id) {
      console.error('[Kiosk] Blocked navigation: customer identity is not authenticated!', authData)
      return
    }
    const custId = authData.customer_id
    const custName = authData.customer_name || 'Valued Customer'
    setAuthenticatedCustomer({ id: custId, name: custName })

    // Notify backend session
    try {
      await fetch('http://127.0.0.1:8000/api/v1/session/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          preferred_language: preferredLanguage || 'en',
        }),
        signal: AbortSignal.timeout(3000),
      })
    } catch (e) {
      console.warn('[Kiosk] Backend session start notice:', e)
    }

    // Open real Voice AI connection for this session
    voiceServiceRef.current = new VoiceAIService()
    await voiceServiceRef.current.connect({
      sessionId,
      preferredLanguage,
      sampleRate: 16000,
    })
    setTransactionStage('selection')
    goTo('assistant')
  }, [sessionId, preferredLanguage, goTo])

  // Called by BankingAssistant once the user's utterance is ready -
  // either a real recognized transcript from the mic (with the speech
  // recognizer's confidence score) or typed/tapped text (confidence 1).
  const submitToVoiceAI = useCallback(
    async (text, recognitionConfidence = 1) => {
      resetInactivityTimer()
      setCancellationNotice(null)
      setVoiceFeedback(null)
      setUserInput(text)
      setLoading(true)
      setError(null)

      const normalizedText = normalizeTranscript(text)
      const detectedIntent = detectIntent(normalizedText)
      const detectedAmount = extractAmount(normalizedText)

      console.log(
        `[TRANSACTION] session_id=${sessionId} customer_id=${authenticatedCustomer?.id} transaction_type=${transactionIntent || detectedIntent} amount=${detectedAmount} STEP 1: details received`,
      )

      const labels = {
        withdraw: 'Cash Withdrawal',
        deposit: 'Cash Deposit',
        send_money: 'Money Transfer',
        balance_check: 'Balance Inquiry',
        open_account: 'Open Account',
      }

      if (transactionStage === 'selection' && detectedIntent === 'unknown') {
        const message = translate(preferredLanguage || 'en', 'transactionSelectionPrompt')
        setVoiceFeedback({ state: 'selection', value: null, message })
        setLoading(false)
        speakText(message, preferredLanguage || 'en')
        return
      }

      if (transactionStage === 'selection' && detectedIntent !== 'unknown' && detectedAmount === null && detectedIntent !== 'balance_check') {
        setTransactionIntent(detectedIntent)
        setTransactionType(labels[detectedIntent] || 'Cash Deposit')
        setTransactionStage('amount')
        setVoiceFeedback({ state: 'amount', intent: detectedIntent, value: null })
        setLoading(false)
        const prompt = translate(preferredLanguage || 'en', 'amountEntryPrompt')(detectedIntent)
        speakText(prompt, preferredLanguage || 'en')
        return
      }

      let resolvedIntent = transactionIntent
      let resolvedAmount = transactionAmount

      if (transactionStage === 'amount') {
        if (detectedAmount === null) {
          setVoiceFeedback({ state: 'amount', value: null, message: translate(preferredLanguage || 'en', 'invalidAmount') })
          setLoading(false)
          speakText(translate(preferredLanguage || 'en', 'invalidAmount'), preferredLanguage || 'en')
          return
        }

        resolvedAmount = detectedAmount
        resolvedIntent = transactionIntent || (detectedIntent !== 'unknown' ? detectedIntent : 'deposit')
        setTransactionAmount(resolvedAmount)
        setTransactionIntent(resolvedIntent)
        setTransactionType(labels[resolvedIntent] || 'Cash Deposit')
        text = `${resolvedIntent} ${resolvedAmount} rupees`
        recognitionConfidence = 1
        setVoiceFeedback({ state: 'confirmation', intent: resolvedIntent, value: resolvedAmount })
      } else {
        // Selection with both intent and amount or balance check
        resolvedIntent = detectedIntent !== 'unknown' ? detectedIntent : (transactionIntent || 'deposit')
        resolvedAmount = detectedAmount !== null ? detectedAmount : transactionAmount
        setTransactionIntent(resolvedIntent)
        if (resolvedAmount !== null) setTransactionAmount(resolvedAmount)
        setTransactionType(labels[resolvedIntent] || 'Cash Deposit')
        setVoiceFeedback({ state: 'confirmation', intent: resolvedIntent, value: resolvedAmount })
      }

      console.log(
        `[TRANSACTION] session_id=${sessionId} customer_id=${authenticatedCustomer?.id} transaction_type=${resolvedIntent} amount=${resolvedAmount} STEP 2: validation passed`,
      )

      try {
        const response = await voiceServiceRef.current.sendMessage(
          text,
          recognitionConfidence,
        )
        setAiResponse(response)

        console.log('[Kiosk Dev Log]', {
          language: preferredLanguage || 'en',
          session_id: sessionId,
          state: response.needs_clarification ? 'error' : 'confirmation',
          transcript: text,
          intent: response.intent,
          amount: response.entities?.amount ?? null,
          response: response.spoken_text,
          tts_language: preferredLanguage === 'ta' ? 'ta-IN' : 'en-IN',
          tts_status: 'success',
        })

        if (response.needs_clarification) {
          setError(
            response.spoken_text ||
              translate(preferredLanguage || 'en', 'errorDefault'),
          )
          goTo('error')
          return
        }

        const finalIntent = response.intent && response.intent !== 'unknown' ? response.intent : resolvedIntent
        const finalAmount = response.entities?.amount != null
          ? response.entities.amount
          : (response.entities?.balance != null ? response.entities.balance : resolvedAmount)
        const finalLabel = response.transaction_label && response.transaction_label !== 'Unknown Request' ? response.transaction_label : (labels[finalIntent] || 'Cash Deposit')

        setTransactionType(finalLabel)
        setTransactionAmount(finalAmount)
        setTransactionIntent(finalIntent)
        setTransactionStage('confirmation')
        goTo('confirmation')
      } catch (err) {
        console.error('[Kiosk] Voice AI transaction error:', err)
        setError(err.message || translate(preferredLanguage || 'en', 'errorDefault'))
        goTo('error')
      } finally {
        setLoading(false)
      }
    },
    [authenticatedCustomer, goTo, preferredLanguage, resetInactivityTimer, sessionId, transactionAmount, transactionIntent, transactionStage],
  )

  const confirmTransaction = useCallback(async () => {
    resetInactivityTimer()
    setLoading(true)
    try {
      if (voiceServiceRef.current?.confirm) {
        if ((transactionAmount === undefined || transactionAmount === null) && transactionIntent !== 'balance_check') {
          throw new Error('Transaction amount is missing')
        }
        const confirmedTransaction = {
          session_id: sessionId,
          customer_id: authenticatedCustomer?.id,
          transaction_type: transactionIntent || 'deposit',
          amount: Number(transactionAmount),
        }
        console.log('CONFIRMED TRANSACTION:', confirmedTransaction)
        console.log('CONFIRMED AMOUNT:', confirmedTransaction.amount)

        const confirmRes = await voiceServiceRef.current.confirm(true, confirmedTransaction)
        console.log('[Kiosk] Backend confirmation result:', confirmRes)
        const backendData = confirmRes?.backend_response
        if (backendData && backendData.status === 'ok') {
          setBackendTokenInfo(backendData)
          const finalIntent = backendData.transaction_type || transactionIntent || 'deposit'
          const finalAmount = backendData.amount != null ? Number(backendData.amount) : Number(transactionAmount)
          if (finalAmount === undefined || finalAmount === null || isNaN(finalAmount)) {
            throw new Error('Transaction amount is missing after confirmation')
          }
          const finalCustomerName = authenticatedCustomer?.name || backendData.customer_name || 'Authenticated Customer'

          setTransactionIntent(finalIntent)
          setTransactionType(getTransactionLabel(finalIntent))
          setTransactionAmount(finalAmount)

          // Generate the secure PDF receipt from the real Security-module QR payload.
          // Failure to create/download the PDF must not falsely roll back a transaction
          // that the backend has already committed; the Success screen keeps a manual
          // retry button available.
          try {
            const { downloadReceiptPdf } = await import('./services/receiptService.js')
            await downloadReceiptPdf({
              customerName: finalCustomerName,
              transactionType: finalIntent,
              amount: finalAmount,
              tokenId: backendData.token_id,
              tokenNumber: backendData.token_number,
              queuePosition: backendData.queue_position,
              issuedAt: backendData.issued_at,
              expiresAt: backendData.expires_at,
              qrPayload: backendData.qr_payload,
            })
          } catch (receiptError) {
            console.warn('[Kiosk] Automatic receipt download failed; manual retry remains available:', receiptError)
          }

          setLoading(false)
          goTo('success')
          return
        } else {
          throw new Error(backendData?.error_message || 'Transaction confirmation rejected by banking backend.')
        }
      }
      throw new Error('Voice service unavailable.')
    } catch (err) {
      console.error('[Kiosk] Confirmation error:', err)
      setLoading(false)
      setError(err.message || translate(preferredLanguage || 'en', 'errorDefault'))
      goTo('error')
    }
  }, [authenticatedCustomer, goTo, preferredLanguage, resetInactivityTimer, sessionId, transactionAmount, transactionIntent])

  const cancelTransaction = useCallback(() => {
    // Cancellation is local-only: clear pending transaction data and return
    // to the active assistant without ending the authenticated session.
    console.info('Current screen:', currentScreen)
    console.info('Calling transaction cancel handler')
    resetInactivityTimer()
    setUserInput('')
    setAiResponse(null)
    setTransactionType(null)
    setTransactionAmount(null)
    setTransactionIntent(null)
    setTransactionStage('selection')
    setVoiceFeedback(null)
    setError(null)
    setCancellationNotice('Transaction cancelled. No changes were made.')
    console.info('Confirmation state cleared')
    goTo('assistant')
    console.info('Navigation completed')
  }, [currentScreen, goTo, resetInactivityTimer])

  const startNewTransaction = useCallback(async () => {
    // Server-side reset: wipe transaction state and reset auth status to pending
    try {
      if (sessionId) {
        await fetch(`http://localhost:8000/api/v1/session/${sessionId}/reset`, {
          method: 'POST',
        })
      }
    } catch (e) {
      console.warn('[Kiosk] Backend reset notice:', e)
    }

    setUserInput('')
    setAiResponse(null)
    setTransactionType(null)
    setTransactionAmount(null)
    setTransactionIntent(null)
    setTransactionStage('selection')
    setError(null)
    setCancellationNotice(null)
    setVoiceFeedback(null)
    setBackendTokenInfo(null)
    setAuthenticatedCustomer(null)

    // Require fresh face authentication before starting the next transaction
    const nextSessionId = generateSessionUuid()
    setSessionId(nextSessionId)
    goTo('auth')
  }, [goTo, sessionId])

  const exitKiosk = endSession

  const retryFromError = useCallback(() => {
    resetInactivityTimer()
    setError(null)
    setLoading(false)
    if (authenticatedCustomer && sessionId) {
      goTo('assistant')
    } else {
      goTo('welcome')
    }
  }, [authenticatedCustomer, goTo, resetInactivityTimer, sessionId])

  useEffect(() => {
    if (!sessionId) return undefined

    const handleUserActivity = () => resetInactivityTimer()
    const activityEvents = ['click', 'touchstart', 'keydown']
    activityEvents.forEach((eventName) => {
      document.addEventListener(eventName, handleUserActivity)
    })

    return () => {
      activityEvents.forEach((eventName) => {
        document.removeEventListener(eventName, handleUserActivity)
      })
    }
  }, [sessionId, resetInactivityTimer])

  useEffect(() => {
    return () => {
      clearInactivityTimers()
      inactivityVoiceFlowRef.current += 1
      inactivityRecognitionRef.current?.stop()
    }
  }, [clearInactivityTimers])

  useEffect(() => {
    if (!sessionId || currentScreen === 'confirmation') return
    if (currentScreen === 'assistant') {
      console.log('[FLOW] Transaction screen initialized')
      console.log('[FLOW] Transaction TTS started')
    }
    const guidanceStage = {
      language: 'authentication',
      assistant: 'transaction',
      error: 'transaction',
      success: 'complete',
    }[currentScreen]
    if (guidanceStage) speakGuidance(preferredLanguage || 'en', guidanceStage)
  }, [currentScreen, preferredLanguage, sessionId])

  // ---------------- Screen router ----------------
  // (No handler/state logic below was changed - only the addition of
  // the persistent Header and a <main> wrapper for layout purposes.)

  return (
    <div className="kiosk-shell">
      {currentScreen !== 'welcome' && (
        <Header preferredLanguage={preferredLanguage} />
      )}

      <ProgressIndicator currentScreen={currentScreen} preferredLanguage={preferredLanguage} />

      <main className="kiosk-main">
        {currentScreen === 'welcome' && <Welcome preferredLanguage={preferredLanguage || 'en'} onStart={startSession} />}

        {currentScreen === 'language' && (
          <LanguageSelection onSelect={selectLanguage} />
        )}

        {currentScreen === 'auth' && (
          <Authentication
            sessionId={sessionId}
            preferredLanguage={preferredLanguage || 'en'}
            onVerified={completeAuthentication}
          />
        )}

        {currentScreen === 'assistant' && (
          <BankingAssistant
            preferredLanguage={preferredLanguage}
            customerName={authenticatedCustomer?.name}
            userInput={userInput}
            aiResponse={aiResponse}
            cancellationNotice={cancellationNotice}
            transactionStage={transactionStage}
            voiceFeedback={voiceFeedback}
            loading={loading}
            onSubmit={submitToVoiceAI}
            onCancel={cancelTransaction}
          />
        )}

        {currentScreen === 'confirmation' && (
          <Confirmation
            transactionType={transactionType}
            transactionAmount={transactionAmount}
            customerName={authenticatedCustomer?.name}
            aiMessage={aiResponse?.spoken_text}
            aiResponse={aiResponse}
            preferredLanguage={preferredLanguage}
            onConfirm={confirmTransaction}
            onCancel={cancelTransaction}
          />
        )}

        {currentScreen === 'success' && (
          <Success
            transactionType={transactionType}
            transactionIntent={transactionIntent}
            transactionAmount={transactionAmount}
            customerName={authenticatedCustomer?.name}
            preferredLanguage={preferredLanguage}
            tokenInfo={backendTokenInfo}
            onNewTransaction={startNewTransaction}
            onExit={exitKiosk}
          />
        )}

        {currentScreen === 'error' && (
          <ErrorScreen
            message={error}
            preferredLanguage={preferredLanguage}
            onRetry={retryFromError}
            onHome={exitKiosk}
          />
        )}
      </main>

      {inactivityWarning && (
        <div className="inactivity-warning" role="alertdialog" aria-live="assertive">
          <div className="inactivity-warning__panel">
            <p className="eyebrow">{translate(preferredLanguage || 'en', 'inactivityEyebrow')}</p>
            <h2 className="screen__title">{translate(preferredLanguage || 'en', 'inactivityTitle')}</h2>
            <p className="inactivity-warning__message">
              {translate(preferredLanguage || 'en', 'inactivityMessage')}
            </p>
            <p className="inactivity-warning__countdown">
              {translate(preferredLanguage || 'en', 'sessionExpires')(inactivitySeconds)}
            </p>
            <button
              className="btn btn--primary btn--lg"
              type="button"
              onClick={resetInactivityTimer}
              autoFocus
            >
              {translate(preferredLanguage || 'en', 'continueSession')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
