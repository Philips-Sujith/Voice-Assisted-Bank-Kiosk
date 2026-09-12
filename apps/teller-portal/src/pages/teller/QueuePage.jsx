import React from 'react';
import { QueueTable } from '../../components/queue/QueueTable';
import { QueueCalledAlert } from '../../components/queue/QueueCalledAlert';
import { QrCode } from 'lucide-react';

export const QueuePage = ({ onNavigateToVerification }) => {
  return (
    <div>
      <QueueCalledAlert onProceedToVerification={onNavigateToVerification} />

      <div className="card">
        <div className="card-title flex items-center justify-between">
          <span>Real-Time Customer Token Queue</span>
          <button 
            className="btn btn-primary"
            onClick={() => onNavigateToVerification && onNavigateToVerification()}
          >
            <QrCode size={16} />
            <span>Go to QR Verification Workspace</span>
          </button>
        </div>
        <div className="card-subtitle">
          Updates automatically as new_queue_entry, queue_called, transaction_completed, and token_expired events arrive over WebSocket.
        </div>

        <QueueTable onSelectTokenForScan={onNavigateToVerification} />
      </div>
    </div>
  );
};
