import React, { useState, useEffect, useRef } from 'react';
import { useQueue } from '../../state/QueueContext';
import { verifyToken, markTokenUsed, markTokenCancelled, completeBackendTransaction } from '../../services/verification/verificationService';
import { TokenScanner } from '../../components/scanner/TokenScanner';
import { VerificationPanel } from '../../components/verification/VerificationPanel';
import { SecurityStatusCard } from '../../components/verification/SecurityStatusCard';
import { ConfirmationModal } from '../../components/receipt/ConfirmationModal';
import { ReceiptPreviewModal } from '../../components/receipt/ReceiptPreviewModal';
import { QueueCalledAlert } from '../../components/queue/QueueCalledAlert';
import { ErrorBoundary } from '../../components/common/ErrorBoundary';
import { wsClient } from '../../services/websocket/wsClient';

export const VerificationPage = ({ simulatedQrPayload, onClearSimulatedPayload }) => {
  const { queueMap, addAuditLog } = useQueue();
  // READY, VERIFYING, VERIFIED, INVALID, EXPIRED, ALREADY_USED, BACKEND_UNAVAILABLE, INSUFFICIENT_FUNDS, ERROR
  const [verificationState, setVerificationState] = useState('READY');
  const [verificationError, setVerificationError] = useState('');
  const [verifiedData, setVerifiedData] = useState(null);
  const [lastVerifiedTime, setLastVerifiedTime] = useState('');
  const [resetScanCounter, setResetScanCounter] = useState(0);

  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [isReceiptModalOpen, setIsReceiptModalOpen] = useState(false);
  const [completedReceiptData, setCompletedReceiptData] = useState(null);

  // Concurrency lock to guarantee one physical QR scan results in exactly ONE verification request
  const isVerifyingRef = useRef(false);
  const lastProcessedPayloadRef = useRef(null);

  const handleResetScan = () => {
    setVerificationState('READY');
    setVerificationError('');
    setVerifiedData(null);
    lastProcessedPayloadRef.current = null;
    setResetScanCounter((prev) => prev + 1);
  };

  const handleScanSuccess = async (scannedRawText) => {
    if (!scannedRawText) return;

    // Prevent duplicate concurrent verification runs
    if (isVerifyingRef.current) {
      console.warn('[VerificationPage] Ignored concurrent scan callback while verification is in progress.');
      return;
    }
    isVerifyingRef.current = true;

    try {
      setVerificationState('VERIFYING');
      setVerificationError('');
      addAuditLog('QR Scanned', `Scanned raw token payload: ${scannedRawText.slice(0, 25)}...`);

      const result = await verifyToken(scannedRawText);

      if (result && result.status === 'VERIFIED') {
        const existingInQueue = Object.values(queueMap || {}).find(
          (q) => q && q.token_id === result.token_id
        );

        // Safely extract transaction amount without throwing
        let finalAmount = 0;
        if (result.amount !== undefined && result.amount !== null) {
          finalAmount = Number(result.amount);
        } else if (existingInQueue?.amount !== undefined && existingInQueue?.amount !== null) {
          finalAmount = Number(existingInQueue.amount);
        }

        const customerName = result.customer_name || result.customer_display_name || existingInQueue?.customer_name || existingInQueue?.customer_display_name || 'Authenticated Customer';

        // Explicitly extract and declare rawTokenId from the verification result or existing queue
        const rawTokenId = result.token_id || existingInQueue?.token_id || '';

        const matchingQueue = {
          token_id: rawTokenId,
          token: result.token || existingInQueue?.token || scannedRawText,
          customer_name: customerName,
          customer_display_name: customerName,
          transaction_type: result.transaction_type || existingInQueue?.transaction_type || 'withdraw',
          amount: finalAmount,
          // account_balance is bank-internal only — never forwarded to receipt
          account_balance: result.account_balance !== undefined ? Number(result.account_balance) : (existingInQueue?.account_balance !== undefined ? Number(existingInQueue.account_balance) : 150000),
          // Do NOT default to 1 — let QueueContext's nextPosition() assign a proper unique number
          queue_position: result.queue_position || existingInQueue?.queue_position || undefined,
          issued_at: result.issued_at || existingInQueue?.issued_at || new Date().toISOString(),
          expires_at: result.expires_at || existingInQueue?.expires_at || null,
          status: 'VERIFIED',
        };

        setVerifiedData(matchingQueue);
        setVerificationState('VERIFIED');
        setLastVerifiedTime(new Date().toLocaleTimeString());
        addAuditLog('Token Verified', `HMAC verified signature for token ${matchingQueue.token_id}`);
      } else if (result) {
        let userErrorMessage = result.message || 'Token verification failed.';
        if (result.status === 'EXPIRED') {
          userErrorMessage = 'This token has expired.';
        } else if (result.status === 'ALREADY_USED') {
          userErrorMessage = 'This token has already been used.';
        } else if (result.status === 'INVALID' || result.status === 'PAYLOAD_ERROR') {
          userErrorMessage = result.message || 'Token verification failed.';
        }

        setVerificationState(result.status || 'INVALID');
        setVerificationError(userErrorMessage);
        addAuditLog('Verification Failed', userErrorMessage);

        if (result.status === 'EXPIRED' && result.token_id) {
          wsClient.emitDevEvent({
            event: 'token_expired',
            token_id: result.token_id
          });
        }
      } else {
        setVerificationState('BACKEND_UNAVAILABLE');
        setVerificationError('Unable to reach backend verification service.');
      }
    } catch (err) {
      console.error('[VerificationPage handleScanSuccess Error]:', err);
      setVerificationState('ERROR');
      setVerificationError('Unable to process this QR code. Please scan again.');
      addAuditLog('Verification Error', err.message || 'Unexpected exception during QR verification.');
    } finally {
      isVerifyingRef.current = false;
    }
  };

  useEffect(() => {
    if (simulatedQrPayload && simulatedQrPayload !== lastProcessedPayloadRef.current) {
      lastProcessedPayloadRef.current = simulatedQrPayload;
      handleScanSuccess(simulatedQrPayload);
      if (onClearSimulatedPayload) {
        onClearSimulatedPayload();
      }
    }
  }, [simulatedQrPayload]);

  const handleSelectFromQueueAlert = (queueEntry) => {
    handleScanSuccess(JSON.stringify({ token_id: queueEntry.token_id, token: 'VALID_HMAC_SIG' }));
  };

  const handleConfirmTransaction = async () => {
    setIsConfirmModalOpen(false);
    if (!verifiedData) return;

    try {
      // Emit transaction_completed event via WS with full details so QueueContext updates ledger/receipts/dashboard
      const eventPayload = {
        event: 'transaction_completed',
        token_id: verifiedData.token_id,
        customer_display_name: verifiedData.customer_display_name,
        transaction_type: verifiedData.transaction_type,
        amount: verifiedData.amount,
      };
      if (verifiedData.queue_position) {
        eventPayload.queue_position = verifiedData.queue_position;
      }
      await wsClient.emitDevEvent(eventPayload);
      await completeBackendTransaction(verifiedData.token_id);

      // Mark the token as spent — any future scan of the same QR will be rejected as ALREADY_USED
      markTokenUsed(verifiedData);
      addAuditLog('Staff Confirmed', `Transaction ${verifiedData.token_id} authorized by Teller ST-042. Token invalidated for reuse.`);

      // Explicitly strip account_balance — it is bank-internal and must NEVER appear on the customer receipt
      // eslint-disable-next-line no-unused-vars
      const { account_balance: _stripped, ...receiptSafeData } = verifiedData;
      setCompletedReceiptData(receiptSafeData);
      setIsReceiptModalOpen(true);
      handleResetScan();
    } catch (err) {
      console.error('[VerificationPage handleConfirmTransaction Error]:', err);
      alert(`Error completing transaction: ${err.message}`);
    }
  };

  const handleCancelAndInvalidateTransaction = async () => {
    if (!verifiedData) return;

    try {
      const cancelledTokenId = verifiedData.token_id;

      // 1. Mark token as cancelled in sessionStorage registry so scanning it again returns status: 'INVALID'
      markTokenCancelled(verifiedData);

      // 2. Add Audit log entry
      addAuditLog('Transaction Cancelled', `Transaction ${cancelledTokenId} cancelled by teller ST-042. QR token permanently cancelled & invalidated.`);

      // 3. Emit Dev Event / WS event so queue entry is removed/expired
      await wsClient.emitDevEvent({
        event: 'token_expired',
        token_id: cancelledTokenId
      });

      // 4. Reset Verification Panel state cleanly
      setIsConfirmModalOpen(false);
      handleResetScan();
    } catch (err) {
      console.error('[VerificationPage handleCancel Error]:', err);
      handleResetScan();
    }
  };

  return (
    <ErrorBoundary onReset={handleResetScan}>
      <div>
        <QueueCalledAlert onProceedToVerification={handleSelectFromQueueAlert} />

        <div className="verification-grid">
          <TokenScanner 
            onScanSuccess={handleScanSuccess} 
            onScanError={(err) => addAuditLog('Camera Error', err?.message || String(err))}
            resetTrigger={resetScanCounter}
          />

          <VerificationPanel 
            verificationState={verificationState}
            verifiedData={verifiedData}
            errorMessage={verificationError}
            onConfirmClick={() => setIsConfirmModalOpen(true)}
            onCancelClick={handleCancelAndInvalidateTransaction}
            onResetScan={handleResetScan}
          />
        </div>

        <SecurityStatusCard 
          lastVerifiedTime={lastVerifiedTime}
          isTokenVerified={verificationState === 'VERIFIED'}
        />

        <ConfirmationModal 
          isOpen={isConfirmModalOpen}
          transactionData={verifiedData}
          onCancel={() => setIsConfirmModalOpen(false)}
          onCancelAndDelete={handleCancelAndInvalidateTransaction}
          onConfirm={handleConfirmTransaction}
        />

        <ReceiptPreviewModal 
          isOpen={isReceiptModalOpen}
          receiptData={completedReceiptData}
          onClose={() => setIsReceiptModalOpen(false)}
        />
      </div>
    </ErrorBoundary>
  );
};
