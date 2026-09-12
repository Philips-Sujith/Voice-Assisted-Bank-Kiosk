import React from 'react';
import { formatCurrency, maskCustomerId, formatDateTime } from '../../utils/formatters';
import { ShieldCheck, ShieldAlert, CheckCircle2, AlertCircle, Lock, Loader2, ArrowRight, Wallet, Ban, ScanLine, WifiOff, RefreshCw } from 'lucide-react';

export const VerificationPanel = ({ 
  verificationState, // READY, VERIFYING, VERIFIED, INVALID, EXPIRED, ALREADY_USED, BACKEND_UNAVAILABLE, INSUFFICIENT_FUNDS, ERROR
  verifiedData, 
  errorMessage,
  onConfirmClick,
  onCancelClick,
  onResetScan
}) => {
  const isWithdrawal = verifiedData?.transaction_type?.toLowerCase() === 'withdraw';
  const hasBalance = verifiedData?.account_balance !== undefined && verifiedData?.account_balance !== null;
  const isOverdraft = hasBalance && isWithdrawal && verifiedData.amount > verifiedData.account_balance;
  const remainingAfter = hasBalance && isWithdrawal && !isOverdraft
    ? verifiedData.account_balance - verifiedData.amount
    : null;

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '100%' }}>
      <div>
        <div className="card-title flex items-center justify-between">
          <span>Verification Workspace</span>
          <span style={{ fontSize: '0.78rem', color: '#64748B', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <Lock size={14} style={{ color: '#10B981' }} />
            <span>HMAC Active</span>
          </span>
        </div>
        <div className="card-subtitle">
          Backend security verification and staff authorization terminal.
        </div>

        {/* State 1: READY */}
        {verificationState === 'READY' && (
          <div className="flex flex-col items-center justify-center" style={{ padding: '3.5rem 1.5rem', textAlign: 'center' }}>
            <div 
              style={{ 
                width: 56, 
                height: 56, 
                borderRadius: '50%', 
                backgroundColor: '#F1F5F9', 
                color: '#64748B',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '1rem'
              }}
            >
              <Lock size={26} />
            </div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: '#17212B', marginBottom: '0.35rem' }}>
              Waiting for Scan
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#64748B', maxWidth: 320 }}>
              Scan a customer QR token or select an entry from the active queue to initiate backend verification.
            </p>
          </div>
        )}

        {/* State 2: VERIFYING */}
        {verificationState === 'VERIFYING' && (
          <div className="flex flex-col items-center justify-center" style={{ padding: '3.5rem 1.5rem', textAlign: 'center' }}>
            <Loader2 size={42} className="animate-spin" style={{ color: '#12355B', marginBottom: '1rem' }} />
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#12355B', marginBottom: '0.35rem' }}>
              VERIFYING SECURITY TOKEN
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#64748B' }}>
              Authenticating HMAC signature and verifying token non-expiry with backend server...
            </p>
          </div>
        )}

        {/* State 3: VERIFIED */}
        {verificationState === 'VERIFIED' && verifiedData && (
          <div style={{ animation: 'fadeIn 0.25s ease' }}>
            <div 
              style={{ 
                backgroundColor: '#ECFDF5', 
                border: '1px solid #A7F3D0', 
                borderRadius: 'var(--radius-sm)', 
                padding: '0.85rem 1rem', 
                marginBottom: '1.25rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem'
              }}
            >
              <CheckCircle2 size={22} style={{ color: '#059669' }} />
              <div>
                <div style={{ fontWeight: 700, color: '#065F46', fontSize: '0.9rem' }}>
                  ✓ TOKEN VERIFIED SUCCESSFULLY
                </div>
                <div style={{ fontSize: '0.78rem', color: '#047857' }}>
                  Backend HMAC signature authenticated. Token is valid and unexpired.
                </div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', fontSize: '0.88rem', marginBottom: '1.25rem' }}>
              <div>
                <div style={{ fontSize: '0.75rem', color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>
                  Customer
                </div>
                <div style={{ fontWeight: 700, color: '#17212B' }}>
                  {maskCustomerId(verifiedData.customer_display_name)}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>
                  Transaction
                </div>
                <div style={{ fontWeight: 700, color: '#17212B', textTransform: 'capitalize' }}>
                  {verifiedData.transaction_type || 'Withdrawal'}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>
                  Amount Requested
                </div>
                <div style={{ fontWeight: 700, color: '#12355B', fontSize: '1.1rem' }}>
                  {formatCurrency(verifiedData.amount)}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>
                  Queue Position
                </div>
                <div style={{ fontWeight: 700, color: '#17212B' }}>
                  #{String(verifiedData.queue_position || 1).padStart(2, '0')}
                </div>
              </div>

              {/* ── Account Balance — full-width row inside the grid ── */}
              {hasBalance && (
                <div
                  style={{
                    gridColumn: '1 / -1',
                    backgroundColor: isOverdraft ? '#FEF2F2' : '#EFF6FF',
                    border: `1.5px solid ${isOverdraft ? '#FCA5A5' : '#BFDBFE'}`,
                    borderRadius: 'var(--radius-sm)',
                    padding: '0.75rem 1rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '0.75rem'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Wallet size={18} style={{ color: isOverdraft ? '#DC2626' : '#2563EB', flexShrink: 0 }} />
                    <div>
                      <div style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: isOverdraft ? '#991B1B' : '#1D4ED8' }}>
                        Account Balance · Bank Only
                      </div>
                      {remainingAfter !== null && (
                        <div style={{ fontSize: '0.75rem', color: '#15803D', marginTop: '0.15rem' }}>
                          After withdrawal: <strong>{formatCurrency(remainingAfter)}</strong>
                        </div>
                      )}
                      {isOverdraft && (
                        <div style={{ fontSize: '0.75rem', color: '#DC2626', marginTop: '0.15rem' }}>
                          Shortfall: <strong>{formatCurrency(verifiedData.amount - verifiedData.account_balance)}</strong>
                        </div>
                      )}
                    </div>
                  </div>
                  <div style={{ fontWeight: 800, fontSize: '1.1rem', color: isOverdraft ? '#DC2626' : '#1D4ED8' }}>
                    {formatCurrency(verifiedData.account_balance)}
                  </div>
                </div>
              )}
            </div>

            {/* ── Overdraft warning banner ── */}
            {isOverdraft && (
              <div
                style={{
                  backgroundColor: '#FEF2F2',
                  border: '1.5px solid #FCA5A5',
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.75rem 1rem',
                  marginBottom: '1.25rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.65rem'
                }}
              >
                <Ban size={18} style={{ color: '#DC2626', flexShrink: 0 }} />
                <div style={{ fontSize: '0.82rem', color: '#991B1B', fontWeight: 600 }}>
                  Withdrawal exceeds available balance. Confirm Transaction is disabled until the customer adjusts the amount.
                </div>
              </div>
            )}

            <div style={{ fontSize: '0.78rem', color: '#64748B', borderTop: '1px solid #E2E8F0', paddingTop: '0.85rem', marginBottom: '1.25rem' }}>
              <div>Token ID: <span style={{ fontFamily: 'monospace', fontWeight: 600, color: '#17212B' }}>{verifiedData.token_id}</span></div>
              <div>Verified: {formatDateTime(new Date().toISOString())}</div>
            </div>
          </div>
        )}

        {/* State 4: ALREADY_USED — one-time token spent */}
        {verificationState === 'ALREADY_USED' && (
          <div style={{ animation: 'fadeIn 0.25s ease' }}>
            <div
              style={{
                backgroundColor: '#F5F3FF',
                border: '1.5px solid #C4B5FD',
                borderRadius: 'var(--radius-sm)',
                padding: '1rem',
                marginBottom: '1.25rem',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.75rem'
              }}
            >
              <ScanLine size={24} style={{ color: '#7C3AED', flexShrink: 0, marginTop: '0.1rem' }} />
              <div>
                <div style={{ fontWeight: 700, color: '#4C1D95', fontSize: '0.95rem', marginBottom: '0.2rem' }}>
                  ✕ QR ALREADY USED — ONE-TIME TOKEN SPENT
                </div>
                <div style={{ fontSize: '0.82rem', color: '#6D28D9' }}>
                  {errorMessage || 'This QR token was already scanned and the transaction completed in this session. One-time tokens are invalidated immediately after staff confirmation and cannot be reused.'}
                </div>
              </div>
            </div>
            <div
              style={{
                backgroundColor: '#FAFAFA',
                border: '1px solid #E2E8F0',
                borderRadius: 'var(--radius-sm)',
                padding: '0.75rem 1rem',
                fontSize: '0.8rem',
                color: '#64748B'
              }}
            >
              <strong style={{ color: '#17212B' }}>Action required:</strong> Ask the customer to request a fresh QR token from the kiosk. This token ID is permanently invalidated for this session.
            </div>
          </div>
        )}

        {/* State 5: INVALID / EXPIRED */}
        {(verificationState === 'INVALID' || verificationState === 'EXPIRED') && (
          <div style={{ animation: 'fadeIn 0.25s ease' }}>
            <div 
              style={{ 
                backgroundColor: '#FEF2F2', 
                border: '1px solid #FCA5A5', 
                borderRadius: 'var(--radius-sm)', 
                padding: '1rem', 
                marginBottom: '1.25rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem'
              }}
            >
              <AlertCircle size={24} style={{ color: '#EF4444', flexShrink: 0 }} />
              <div>
                <div style={{ fontWeight: 700, color: '#991B1B', fontSize: '0.95rem' }}>
                  ✕ VERIFICATION FAILED
                </div>
                <div style={{ fontSize: '0.82rem', color: '#B91C1C' }}>
                  {errorMessage || (verificationState === 'EXPIRED' 
                    ? 'Security token has expired according to backend policy. Please request customer to generate a fresh QR token.' 
                    : 'Invalid security signature or tampered HMAC token detected.')}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* State 6: BACKEND_UNAVAILABLE */}
        {verificationState === 'BACKEND_UNAVAILABLE' && (
          <div style={{ animation: 'fadeIn 0.25s ease' }}>
            <div 
              style={{ 
                backgroundColor: '#FFFBEB', 
                border: '1px solid #FCD34D', 
                borderRadius: 'var(--radius-sm)', 
                padding: '1rem', 
                marginBottom: '1.25rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem'
              }}
            >
              <WifiOff size={24} style={{ color: '#D97706', flexShrink: 0 }} />
              <div>
                <div style={{ fontWeight: 700, color: '#92400E', fontSize: '0.95rem' }}>
                  ⚠ BACKEND SERVICE UNAVAILABLE
                </div>
                <div style={{ fontSize: '0.82rem', color: '#B45309' }}>
                  {errorMessage || 'Unable to connect to the central banking backend to verify the secure QR token. Please verify server connectivity and scan again.'}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* State 7: Generic ERROR or unexpected state (prevents any blank screen) */}
        {verificationState !== 'READY' &&
         verificationState !== 'VERIFYING' &&
         verificationState !== 'VERIFIED' &&
         verificationState !== 'ALREADY_USED' &&
         verificationState !== 'INVALID' &&
         verificationState !== 'EXPIRED' &&
         verificationState !== 'BACKEND_UNAVAILABLE' && (
          <div style={{ animation: 'fadeIn 0.25s ease' }}>
            <div 
              style={{ 
                backgroundColor: '#FEF2F2', 
                border: '1px solid #FCA5A5', 
                borderRadius: 'var(--radius-sm)', 
                padding: '1rem', 
                marginBottom: '1.25rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem'
              }}
            >
              <AlertCircle size={24} style={{ color: '#EF4444', flexShrink: 0 }} />
              <div>
                <div style={{ fontWeight: 700, color: '#991B1B', fontSize: '0.95rem' }}>
                  Unable to process this QR code
                </div>
                <div style={{ fontSize: '0.82rem', color: '#B91C1C' }}>
                  {errorMessage || 'The QR token could not be verified. Please check the code and scan again.'}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Action Footer — ALWAYS shows Scan Again when not currently verifying or standby */}
      <div style={{ borderTop: '1px solid #E2E8F0', paddingTop: '1.25rem', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', flexWrap: 'wrap' }}>
        {verificationState !== 'READY' && verificationState !== 'VERIFYING' && (
          <button className="btn btn-secondary" onClick={onResetScan}>
            <RefreshCw size={14} />
            <span>Scan Again</span>
          </button>
        )}

        {verificationState === 'VERIFIED' && verifiedData && (
          <>
            <button
              className="btn"
              onClick={onCancelClick}
              style={{
                backgroundColor: '#FEF2F2',
                color: '#DC2626',
                border: '1px solid #FCA5A5'
              }}
              title="Cancel transaction and permanently invalidate this QR token"
            >
              <Ban size={16} />
              <span>Cancel Transaction</span>
            </button>

            <button
              className="btn btn-success"
              onClick={onConfirmClick}
              disabled={isOverdraft}
              title={isOverdraft ? 'Cannot confirm: withdrawal amount exceeds available balance' : ''}
              style={isOverdraft ? { opacity: 0.45, cursor: 'not-allowed' } : {}}
            >
              <span>Confirm Transaction</span>
              <ArrowRight size={16} />
            </button>
          </>
        )}
      </div>
    </div>
  );
};
