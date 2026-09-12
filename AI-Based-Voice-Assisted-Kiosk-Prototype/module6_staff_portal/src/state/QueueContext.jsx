import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { wsClient } from '../services/websocket/wsClient';

const BACKEND_URL = (typeof window !== 'undefined' && window.__BACKEND_URL__) || 'http://localhost:8000';

const QueueContext = createContext({
  queueMap: {}, // token_id -> entry
  queueList: [],
  selectedTokenId: null,
  setSelectedTokenId: () => {},
  auditLogs: [],
  addAuditLog: () => {},
  currentTellerId: 't_02',
  fetchActiveQueue: () => {},
});

const DEFAULT_MOCK_QUEUE = {
  'TXN-2026-008821': {
    token_id: 'TXN-2026-008821',
    customer_display_name: 'Arjun Kumar',
    transaction_type: 'deposit',
    amount: 25000,
    queue_position: 1,
    issued_at: new Date(Date.now() - 35 * 60000).toISOString(),
    ui_status: 'WAITING',
  },
  'TXN-2026-003277': {
    token_id: 'TXN-2026-003277',
    customer_display_name: 'Priya Nair',
    transaction_type: 'withdraw',
    amount: 10000,
    queue_position: 2,
    issued_at: new Date(Date.now() - 30 * 60000).toISOString(),
    ui_status: 'WAITING',
  },
  'TXN-2026-001104': {
    token_id: 'TXN-2026-001104',
    customer_display_name: 'Rahul Menon',
    transaction_type: 'transfer',
    amount: 50000,
    queue_position: 3,
    issued_at: new Date(Date.now() - 25 * 60000).toISOString(),
    ui_status: 'WAITING',
  },
  'TXN-2026-005590': {
    token_id: 'TXN-2026-005590',
    customer_display_name: 'Ananya Sharma',
    transaction_type: 'deposit',
    amount: 100000,
    queue_position: 4,
    issued_at: new Date(Date.now() - 20 * 60000).toISOString(),
    ui_status: 'WAITING',
  },
  'TXN-2026-007412': {
    token_id: 'TXN-2026-007412',
    customer_display_name: 'Karthik Raj',
    transaction_type: 'withdraw',
    amount: 5000,
    queue_position: 5,
    issued_at: new Date(Date.now() - 15 * 60000).toISOString(),
    ui_status: 'WAITING',
  },
  'TXN-2026-009823': {
    token_id: 'TXN-2026-009823',
    customer_display_name: 'Meera Krishnan',
    transaction_type: 'deposit',
    amount: 75000,
    queue_position: 6,
    issued_at: new Date(Date.now() - 10 * 60000).toISOString(),
    ui_status: 'WAITING',
  },
  'TXN-2026-004319': {
    token_id: 'TXN-2026-004319',
    customer_display_name: 'Aditya Verma',
    transaction_type: 'withdraw',
    amount: 15000,
    queue_position: 7,
    issued_at: new Date(Date.now() - 5 * 60000).toISOString(),
    ui_status: 'WAITING',
  },
  'TXN-2026-006745': {
    token_id: 'TXN-2026-006745',
    customer_display_name: 'Divya Iyer',
    transaction_type: 'balance_check',
    amount: 0,
    queue_position: 8,
    issued_at: new Date(Date.now() - 2 * 60000).toISOString(),
    ui_status: 'WAITING',
  },
};

export const QueueProvider = ({ children }) => {
  const [queueMap, setQueueMap] = useState(DEFAULT_MOCK_QUEUE);
  const [selectedTokenId, setSelectedTokenId] = useState(null);
  const [auditLogs, setAuditLogs] = useState([
    {
      id: Date.now(),
      time: new Date().toLocaleTimeString(),
      event: 'System Init',
      details: 'Teller Terminal ST-042 initialized. Connected to backend queue service.',
    }
  ]);
  const currentTellerId = 't_02';

  const addAuditLog = (event, details) => {
    const newEntry = {
      id: Date.now() + Math.random(),
      time: new Date().toLocaleTimeString(),
      event,
      details,
    };
    setAuditLogs((prev) => [newEntry, ...prev.slice(0, 99)]);
  };

  // Fetch real active queue from backend database
  const fetchActiveQueue = useCallback(async () => {
    try {
      const resp = await fetch(`${BACKEND_URL}/api/v1/teller/queue`);
      if (!resp.ok) return;
      const data = await resp.json();
      if (data && Array.isArray(data.queue)) {
        if (data.queue.length === 0) {
          setQueueMap(DEFAULT_MOCK_QUEUE);
          return;
        }
        const freshMap = {};
        data.queue.forEach((item) => {
          freshMap[item.token_id] = {
            token_id: item.token_id,
            customer_display_name: item.customer_display_name || `Customer #${item.token_number || item.token_id.slice(-4)}`,
            transaction_type: item.transaction_type || 'deposit',
            amount: item.amount !== null && item.amount !== undefined ? item.amount : 0,
            queue_position: item.queue_position,
            issued_at: item.issued_at || item.created_at || new Date().toISOString(),
            ui_status: item.status || 'WAITING',
          };
        });
        setQueueMap(freshMap);
        console.log(`[QueueContext] Loaded ${data.count} active queue entries from database.`);
      }
    } catch (err) {
      console.warn('[QueueContext] Failed to fetch active queue from backend (using default demo queue):', err);
    }
  }, []);

  useEffect(() => {
    // Initial fetch from database
    fetchActiveQueue();

    // Subscribe to live WebSocket events
    const unsubscribe = wsClient.onMessage((data) => {
      if (!data || !data.event) return;

      const eventType = data.event;
      const tokenId = data.token_id;

      if (!tokenId) {
        console.warn('[QueueContext] Event missing token_id:', data);
        return;
      }

      setQueueMap((prevMap) => {
        const nextMap = { ...prevMap };
        const existing = nextMap[tokenId] || {};

        const nextPosition = () => {
          const maxPos = Object.values(nextMap).reduce((m, e) => Math.max(m, e.queue_position || 0), 0);
          return maxPos + 1;
        };

        if (eventType === 'new_queue_entry') {
          const pos = data.queue_position || existing.queue_position || nextPosition();
          nextMap[tokenId] = {
            ...existing,
            token_id: data.token_id,
            customer_display_name: data.customer_display_name || existing.customer_display_name || `Customer #${tokenId.slice(-4)}`,
            transaction_type: data.transaction_type || existing.transaction_type || 'deposit',
            amount: data.amount !== undefined && data.amount !== null ? data.amount : (existing.amount || 0),
            queue_position: pos,
            issued_at: data.issued_at || new Date().toISOString(),
            ui_status: 'WAITING',
          };
          addAuditLog('New Queue Entry', `${data.customer_display_name || tokenId} joined queue at position #${pos}`);
        } else if (eventType === 'queue_called') {
          const pos = existing.queue_position || nextPosition();
          nextMap[tokenId] = {
            ...existing,
            token_id: tokenId,
            customer_display_name: data.customer_display_name || existing.customer_display_name || `Customer #${tokenId.slice(-4)}`,
            transaction_type: existing.transaction_type || 'deposit',
            amount: existing.amount || 0,
            queue_position: pos,
            issued_at: existing.issued_at || new Date().toISOString(),
            ui_status: 'CALLED',
            called_teller_id: data.teller_id || 't_02',
          };
          addAuditLog('Queue Called', `Customer token ${tokenId.slice(0, 8)} called by Teller ${data.teller_id || 't_02'}`);
        } else if (eventType === 'transaction_completed') {
          const pos = data.queue_position || existing.queue_position || nextPosition();
          nextMap[tokenId] = {
            ...existing,
            token_id: tokenId,
            customer_display_name: existing.customer_display_name || `Customer #${tokenId.slice(-4)}`,
            transaction_type: existing.transaction_type || 'deposit',
            amount: existing.amount || 0,
            queue_position: pos,
            issued_at: existing.issued_at || new Date().toISOString(),
            ui_status: 'COMPLETED',
            completed_at: new Date().toISOString(),
          };
          addAuditLog('Transaction Completed', `Token ${tokenId.slice(0, 8)} completed successfully.`);
        } else if (eventType === 'token_expired') {
          const pos = existing.queue_position || nextPosition();
          nextMap[tokenId] = {
            ...existing,
            token_id: tokenId,
            customer_display_name: existing.customer_display_name || `Customer #${tokenId.slice(-4)}`,
            transaction_type: existing.transaction_type || 'deposit',
            amount: existing.amount || 0,
            queue_position: pos,
            issued_at: existing.issued_at || new Date().toISOString(),
            ui_status: 'EXPIRED',
          };
          addAuditLog('Token Expired', `Token ${tokenId.slice(0, 8)} marked EXPIRED by backend.`);
        }

        return nextMap;
      });
    });

    return () => unsubscribe();
  }, [fetchActiveQueue]);

  const queueList = Object.values(queueMap).sort((a, b) => (a.queue_position || 99) - (b.queue_position || 99));

  return (
    <QueueContext.Provider
      value={{
        queueMap,
        queueList,
        selectedTokenId,
        setSelectedTokenId,
        auditLogs,
        addAuditLog,
        currentTellerId,
        fetchActiveQueue,
      }}
    >
      {children}
    </QueueContext.Provider>
  );
};

export const useQueue = () => useContext(QueueContext);
