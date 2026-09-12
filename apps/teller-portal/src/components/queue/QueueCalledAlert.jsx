import React from 'react';
import { useQueue } from '../../state/QueueContext';
import { Bell, ArrowRight } from 'lucide-react';

export const QueueCalledAlert = ({ onProceedToVerification }) => {
  const { queueList, currentTellerId } = useQueue();

  // Find latest entry called for this teller
  const calledEntry = queueList.find(
    (q) => q.ui_status === 'CALLED' && q.called_teller_id === currentTellerId
  );

  if (!calledEntry) return null;

  return (
    <div 
      className="card flex items-center justify-between"
      style={{ 
        backgroundColor: '#FFFBEB', 
        borderColor: '#FCD34D',
        marginBottom: '1.5rem',
        padding: '1rem 1.5rem'
      }}
    >
      <div className="flex items-center gap-3">
        <div 
          style={{ 
            width: 40, 
            height: 40, 
            borderRadius: '50%', 
            backgroundColor: '#F59E0B', 
            color: '#FFFFFF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          <Bell size={20} />
        </div>
        <div>
          <div style={{ fontWeight: 700, color: '#92400E', fontSize: '0.95rem' }}>
            CUSTOMER CALLED: {calledEntry.customer_display_name}
          </div>
          <div style={{ fontSize: '0.82rem', color: '#B45309' }}>
            Position #{calledEntry.queue_position} · {calledEntry.transaction_type?.toUpperCase()} · Please proceed with token QR verification. (Teller: {currentTellerId})
          </div>
        </div>
      </div>

      <button 
        className="btn btn-primary"
        style={{ backgroundColor: '#D97706' }}
        onClick={() => onProceedToVerification && onProceedToVerification(calledEntry)}
      >
        <span>Verify Token</span>
        <ArrowRight size={16} />
      </button>
    </div>
  );
};
