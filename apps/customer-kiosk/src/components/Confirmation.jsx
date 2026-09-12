// SCREEN 5: TRANSACTION CONFIRMATION
// Shows the parsed transaction back to the customer for a final
// yes/no before it's treated as confirmed. The displayed Voice AI response
// can also be replayed before the customer confirms the transaction.
import { useEffect, useRef, useState } from 'react'
import { replayVoiceResponse, speakText } from '../services/ttsService.js'
import { translate } from '../services/translations.js'

const SpeechRecognitionAPI =
  typeof window !== 'undefined'
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : null

export default function Confirmation({
  transactionType,
  transactionAmount,
  aiMessage,
  aiResponse,
  preferredLanguage,
  customerName,
  onConfirm,
  onCancel,
}) {
  const [voiceListening, setVoiceListening] = useState(false)
  const [heardText, setHeardText] = useState(null)
  const recognitionRef = useRef(null)
  const onConfirmRef = useRef(onConfirm)
  const onCancelRef = useRef(onCancel)
  const questionRef = useRef('')
  const languageRef = useRef(preferredLanguage)
  const listeningRef = useRef(false)
  const cancelledRef = useRef(false)
  const retryCountRef = useRef(0)
  const heardTimeoutRef = useRef(null)
  const flowIdRef = useRef(0)
  const suppressEndRetryRef = useRef(false)

  useEffect(() => {
    onConfirmRef.current = onConfirm
    onCancelRef.current = onCancel
  }, [onConfirm, onCancel])

  const stopConfirmationRecognition = () => {
    listeningRef.current = false
    setVoiceListening(false)
    recognitionRef.current?.stop()
    recognitionRef.current = null
  }

  // This listener starts only after the short confirmation prompt finishes.
  // It is guarded so a repeat command or rerender cannot create two sessions.
  const listenForConfirmation = () => {
    if (!SpeechRecognitionAPI || listeningRef.current || cancelledRef.current) return

    const recognition = new SpeechRecognitionAPI()
    recognition.lang = languageRef.current === 'ta' ? 'ta-IN' : 'en-IN'
    recognition.interimResults = false
    recognition.maxAlternatives = 1
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript.trim()
      const normalized = transcript.toLowerCase().replace(/[.!?,]+$/g, '').trim()
      setHeardText(transcript)
      clearTimeout(heardTimeoutRef.current)
      heardTimeoutRef.current = setTimeout(() => setHeardText(null), 2500)

      if (/^(yes|continue|confirm)$/i.test(normalized) || ['ஆம்', 'தொடரவும்', 'உறுதிப்படுத்தவும்'].includes(normalized)) {
        suppressEndRetryRef.current = true
        stopConfirmationRecognition()
        onConfirmRef.current()
      } else if (/^(no|cancel|stop|cancel transaction)$/i.test(normalized) || ['இல்லை', 'ரத்து', 'ரத்து செய்', 'வேண்டாம்'].includes(normalized)) {
        suppressEndRetryRef.current = true
        stopConfirmationRecognition()
        onCancelRef.current()
      } else if (/^(repeat|listen again)$/i.test(normalized) || normalized === 'மீண்டும் கேட்கவும்') {
        suppressEndRetryRef.current = true
        stopConfirmationRecognition()
        speakAndListen(true)
      }
    }
    recognition.onerror = (event) => {
      setVoiceListening(false)
      listeningRef.current = false
      if (event.error !== 'no-speech') retryListening()
    }
    recognition.onend = () => {
      recognitionRef.current = null
      listeningRef.current = false
      setVoiceListening(false)
      if (!suppressEndRetryRef.current && !cancelledRef.current) retryListening()
      suppressEndRetryRef.current = false
    }

    recognitionRef.current = recognition
    listeningRef.current = true
    setVoiceListening(true)
    try {
      recognition.start()
    } catch (error) {
      console.warn('[Confirmation] voice command listener could not start', error)
      recognitionRef.current = null
      setVoiceListening(false)
    }
  }

  const retryListening = () => {
    if (retryCountRef.current >= 1 || cancelledRef.current) return
    retryCountRef.current += 1
    speakAndListen(true)
  }

  const speakAndListen = async (isRetry = false) => {
    if (cancelledRef.current) return
    const flowId = ++flowIdRef.current
    stopConfirmationRecognition()
    if (!isRetry) retryCountRef.current = 0
    const textToSpeak = aiMessage || questionRef.current
    await speakText(textToSpeak, languageRef.current)
    if (cancelledRef.current || flowId !== flowIdRef.current) return
    window.setTimeout(() => {
      if (!cancelledRef.current && flowId === flowIdRef.current) listenForConfirmation()
    }, 300)
  }

  const handleConfirm = () => {
    cancelledRef.current = true
    flowIdRef.current += 1
    stopConfirmationRecognition()
    onConfirmRef.current()
  }

  const handleCancel = () => {
    cancelledRef.current = true
    flowIdRef.current += 1
    stopConfirmationRecognition()
    onCancelRef.current()
  }

  const questionBuilder = translate(preferredLanguage, 'confirmationQuestion')
  const confirmationQuestion = typeof questionBuilder === 'function'
    ? questionBuilder(transactionType, transactionAmount)
    : questionBuilder

  useEffect(() => {
    questionRef.current = confirmationQuestion
    languageRef.current = preferredLanguage
    cancelledRef.current = false
    if (SpeechRecognitionAPI) speakAndListen()

    return () => {
      cancelledRef.current = true
      flowIdRef.current += 1
      clearTimeout(heardTimeoutRef.current)
      stopConfirmationRecognition()
    }
  }, [confirmationQuestion, preferredLanguage])

  const transactionTypeLabel =
    transactionType === 'Cash Withdrawal' || transactionType === 'Withdrawal' || transactionType === 'withdraw'
      ? translate(preferredLanguage, 'labelWithdraw')
      : transactionType === 'Cash Deposit' || transactionType === 'Deposit' || transactionType === 'deposit'
        ? translate(preferredLanguage, 'labelDeposit')
        : transactionType === 'Money Transfer' || transactionType === 'send_money'
          ? translate(preferredLanguage, 'labelSend')
          : transactionType === 'Balance Inquiry' || transactionType === 'balance_check'
            ? translate(preferredLanguage, 'labelBalance')
            : transactionType || translate(preferredLanguage, 'labelUnknown')

  return (
    <section className="screen screen--confirmation">
      <div className="confirm-split">
        <div className="confirm-left">
          <p className="eyebrow">{translate(preferredLanguage, 'confirmationPrompt')}</p>
          <h2 className="screen__title">{translate(preferredLanguage, 'confirmTitle')}</h2>
          <p className="confirm-left__note">
            {translate(preferredLanguage, 'confirmNote')}
          </p>
          {aiMessage && (
            <>
              <p className="confirm-card__ai-note">“{aiMessage}”</p>
              <button
                className="listen-again-button"
                type="button"
                onClick={() => replayVoiceResponse(aiResponse || { spoken_text: aiMessage }, preferredLanguage)}
                aria-label="Listen again to the AI response"
              >
                🔊 {translate(preferredLanguage, 'listenAgain')}
              </button>
            </>
          )}
          {heardText && <p className="mic-notice" role="status">I heard: {heardText}</p>}
        </div>

        <div className="summary-card">
          <p className="summary-card__type">{transactionTypeLabel}</p>
          <p className="summary-card__amount">
            {transactionAmount != null ? `₹${transactionAmount.toLocaleString('en-IN')}` : '—'}
          </p>

          <div className="summary-card__divider" />

          {customerName && (
            <div className="summary-row">
              <span className="summary-row__label">{preferredLanguage === 'ta' ? 'வாடிக்கையாளர்' : 'Customer'}</span>
              <span className="summary-row__value" style={{ color: '#38bdf8', fontWeight: 'bold' }}>{customerName}</span>
            </div>
          )}
          <div className="summary-row">
            <span className="summary-row__label">{translate(preferredLanguage, 'fromLabel')}</span>
            <span className="summary-row__value">{translate(preferredLanguage, 'primaryAccount')}</span>
          </div>
          <div className="summary-row">
            <span className="summary-row__label">{translate(preferredLanguage, 'statusLabel')}</span>
            <span className="summary-row__value summary-row__value--pending">
              {translate(preferredLanguage, 'awaitingConfirmation')}
            </span>
          </div>
        </div>
      </div>

      <div className="action-bar">
        <button className="btn btn--danger btn--lg" onClick={handleCancel} aria-label="Cancel transaction">
          {translate(preferredLanguage, 'cancelTransaction')}
        </button>
        <button className="btn btn--primary btn--lg" onClick={handleConfirm} id="btn-confirm-transaction">
          {translate(preferredLanguage, 'confirmTransaction') || translate(preferredLanguage, 'continue')}
        </button>
      </div>
      <button
        className="cancel-voice-button"
        type="button"
        onClick={() => speakAndListen()}
        disabled={!SpeechRecognitionAPI || voiceListening}
        aria-label={translate(preferredLanguage, 'sayCancel')}
      >
        {voiceListening ? translate(preferredLanguage, 'listeningForCancel') : `🎙 ${translate(preferredLanguage, 'sayCancel')}`}
      </button>
    </section>
  )
}
