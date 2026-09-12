import React from 'react';
import { formatCurrency, maskCustomerId } from '../../utils/formatters';
import { AlertTriangle, Check, X, Wallet, Ban } from 'lucide-react';

export const ConfirmationModal = ({ isOpen, transactionData, onCancel, onCancelAndDelete, onConfirm }) => {
  if (!isOpen || !transactionData) return null;

  const isWithdrawal = transactionData.transaction_type?.toLowerCase() === 'withdraw';
  const hasBalance = transactionData.account_balance !== undefined && transactionData.account_balance !== null;
  const remainingAfter = hasBalance && isWithdrawal
    ? transactionData.account_balance - transactionData.amount
    : null;

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <div className="modal-header">
          <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#12355B' }}>
            Confirm Transaction Execution?
          </h2>
          <p style={{ fontSize: '0.8rem', color: '#64748B' }}>
            Staff authorization required prior to core banking ledger entry.
          </p>
        </div>

        <div className="modal-body">
          <div 
            style={{ 
              backgroundColor: '#FEF3C7', 
              border: '1px solid #FCD34D', 
              borderRadius: 'var(--radius-sm)', 
              padding: '0.75rem 1rem', 
              marginBottom: '1.25rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.65rem'
            }}
          >
            <AlertTriangle size={18} style={{ color: '#D97706' }} />
            <div style={{ fontSize: '0.82rem', color: '#92400E' }}>
              Warning: Confirming will mark transaction as completed and lock token against duplicate use.
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.88rem' }}>
            <div className="flex justify-between" style={{ borderBottom: '1px solid #E2E8F0', paddingBottom: '0.5rem' }}>
              <span style={{ color: '#64748B' }}>Token ID:</span>
              <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>{transactionData.token_id}</span>
            </div>

            <div className="flex justify-between" style={{ borderBottom: '1px solid #E2E8F0', paddingBottom: '0.5rem' }}>
              <span style={{ color: '#64748B' }}>Customer:</span>
              <span style={{ fontWeight: 700 }}>{maskCustomerId(transactionData.customer_display_name)}</span>
            </div>

            <div className="flex justify-between" style={{ borderBottom: '1px solid #E2E8F0', paddingBottom: '0.5rem' }}>
              <span style={{ color: '#64748B' }}>Service / Type:</span>
              <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>{transactionData.transaction_type}</span>
            </div>

            <div className="flex justify-between" style={{ borderBottom: hasBalance ? '1px solid #E2E8F0' : 'none', paddingBottom: hasBalance ? '0.5rem' : '0.25rem' }}>
              <span style={{ color: '#64748B' }}>Amount:</span>
              <span style={{ fontWeight: 700, color: '#12355B', fontSize: '1.1rem' }}>{formatCurrency(transactionData.amount)}</span>
            </div>

            {/* ── BANK-INTERNAL: Account Balance ─── Never printed on customer receipt ── */}
            {hasBalance && (
              <div
                style={{
                  backgroundColor: '#EFF6FF',
                  border: '1.5px solid #BFDBFE',
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.75rem 1rem',
                  marginTop: '0.25rem'
                }}
              >
                <div style={{ fontSize: '0.7rem', color: '#1D4ED8', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <Wallet size={13} />
                  Bank-Internal · Not Printed on Receipt
                </div>
                <div className="flex justify-between" style={{ marginBottom: '0.3rem' }}>
                  <span style={{ color: '#1E40AF', fontWeight: 500 }}>Available Balance:</span>
                  <span style={{ fontWeight: 800, color: '#1D4ED8' }}>{formatCurrency(transactionData.account_balance)}</span>
                </div>
                {isWithdrawal && remainingAfter !== null && (
                  <div className="flex justify-between">
                    <span style={{ color: '#15803D', fontWeight: 500 }}>Balance After Withdrawal:</span>
                    <span style={{ fontWeight: 700, color: '#15803D' }}>{formatCurrency(remainingAfter)}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="modal-footer" style={{ gap: '0.5rem', flexWrap: 'wrap' }}>
          <button className="btn btn-secondary" onClick={onCancel}>
            <X size={16} />
            <span>Close Window</span>
          </button>

          {onCancelAndDelete && (
            <button
              className="btn"
              onClick={onCancelAndDelete}
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
          )}

          <button className="btn btn-success" onClick={onConfirm}>
            <Check size={16} />
            <span>Confirm &amp; Complete</span>
          </button>
        </div>
      </div>
    </div>
  );
};
