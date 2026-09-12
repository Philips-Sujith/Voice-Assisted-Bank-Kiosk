// SCREEN 6: SUCCESS
// Confirms the request went through and displays signed token & teller queue info.
import { useEffect, useState } from 'react'
import { translate } from '../services/translations.js'
import { speakGuidance } from '../services/ttsService.js'
import { getTransactionLabel } from '../constants/transactions.js'
import { downloadReceiptPdf } from '../services/receiptService.js'

export default function Success({
  transactionType,
  transactionIntent,
  transactionAmount,
  preferredLanguage,
  tokenInfo,
  customerName,
  onNewTransaction,
  onExit,
}) {
  const [receiptState, setReceiptState] = useState('idle')
  const [receiptError, setReceiptError] = useState(null)

  useEffect(() => {
    speakGuidance(preferredLanguage || 'en', 'complete')
  }, [preferredLanguage])

  const transactionTypeLabel = transactionIntent
    ? getTransactionLabel(transactionIntent)
    : transactionType || getTransactionLabel('unknown')

  // Extract amount from tokenInfo if available
  const displayAmount = transactionAmount != null ? transactionAmount : tokenInfo?.amount

  const handleDownloadReceipt = async () => {
    if (receiptState === 'loading') return
    setReceiptState('loading')
    setReceiptError(null)
    try {
      await downloadReceiptPdf({
        customerName: customerName || tokenInfo?.customer_name,
        transactionType: transactionIntent || tokenInfo?.transaction_type,
        amount: displayAmount,
        tokenId: tokenInfo?.token_id,
        tokenNumber: tokenInfo?.token_number,
        queuePosition: tokenInfo?.queue_position,
        expiresAt: tokenInfo?.expires_at,
        qrPayload: tokenInfo?.qr_payload,
      })
      setReceiptState('ready')
    } catch (error) {
      console.error('[Kiosk] Receipt generation error:', error)
      setReceiptState('error')
      setReceiptError('We could not generate your secure receipt. Please try again.')
    }
  }

  return (
    <section className="screen screen--success">
      <div className="success-stage" aria-hidden="true">
        <span className="success-stage__ring" />
        <span className="success-stage__ring success-stage__ring--2" />
        <span className="success-stage__ring success-stage__ring--3" />
        <div className="success-stage__icon">
          <svg viewBox="0 0 64 64" width="52" height="52" fill="none">
            <circle cx="32" cy="32" r="24" stroke="#34d399" strokeWidth="3" />
            <path
              d="M22 33l7 7 14-14"
              stroke="#34d399"
              strokeWidth="3.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      </div>

      <p className="eyebrow">{translate(preferredLanguage, 'stepComplete')}</p>
      <h2 className="screen__title">{translate(preferredLanguage, 'transactionSuccessful')}</h2>
      <p className="success__lede">
        {translate(preferredLanguage, 'successLede')}
      </p>

      <div className="summary-inline">
        {(customerName || tokenInfo?.customer_name) && (
          <div className="summary-inline__block">
            <p className="summary-inline__label">{preferredLanguage === 'ta' ? 'வாடிக்கையாளர்' : 'Customer'}</p>
            <p className="summary-inline__value" style={{ color: '#38bdf8', fontWeight: 'bold' }}>
              {customerName || tokenInfo?.customer_name}
            </p>
          </div>
        )}
        <div className="summary-inline__block">
          <p className="summary-inline__label">{preferredLanguage === 'ta' ? 'பரிவர்த்தனை' : 'Transaction'}</p>
          <p className="summary-inline__value">{transactionTypeLabel}</p>
        </div>
        <div className="summary-inline__block">
          <p className="summary-inline__label">{preferredLanguage === 'ta' ? 'தொகை' : 'Amount'}</p>
          <p className="summary-inline__value summary-inline__value--amount">
            {displayAmount != null ? `₹${displayAmount.toLocaleString('en-IN')}` : '—'}
          </p>
        </div>
      </div>

      {tokenInfo?.qr_payload && (
        <div className="success-receipt-actions" style={{ margin: '1.2rem auto', textAlign: 'center' }}>
          <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.4rem' }}>
            {preferredLanguage === 'ta' ? 'ரசீதை பதிவிறக்கம் செய்து கேஷியரிடம் காண்பிக்கவும்' : 'Download the secure receipt and show it at the teller counter'}
          </p>
          <button className="btn btn--primary btn--lg" onClick={handleDownloadReceipt} disabled={receiptState === 'loading'}>
            {receiptState === 'loading' ? 'Preparing Receipt...' : 'Download Receipt PDF'}
          </button>
          {receiptError && <p className="mic-notice" role="alert">{receiptError}</p>}
          <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginTop: '0.4rem' }}>
            {preferredLanguage === 'ta' ? 'கேஷியரிடம் இந்த QR ஐ காண்பிக்கவும்' : 'Show this QR at the Teller Counter'}
          </p>
        </div>
      )}

      <p className="success__next-steps">
        {translate(preferredLanguage, 'successNextSteps')}
      </p>

      <div className="action-bar">
        <button className="btn btn--ghost btn--lg" onClick={onExit}>
          {translate(preferredLanguage, 'exitSession')}
        </button>
        <button className="btn btn--primary btn--lg" onClick={onNewTransaction}>
          {translate(preferredLanguage, 'newTransaction')}
        </button>
      </div>
    </section>
  )
}
