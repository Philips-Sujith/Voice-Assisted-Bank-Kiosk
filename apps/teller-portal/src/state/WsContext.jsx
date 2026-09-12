import React, { createContext, useContext, useEffect, useState } from 'react';
import { wsClient } from '../services/websocket/wsClient';

const WsContext = createContext({
  status: 'DISCONNECTED',
  connect: () => {},
  disconnect: () => {},
  emitDevEvent: async () => {}
});

export const WsProvider = ({ children }) => {
  const [status, setStatus] = useState('DISCONNECTED');

  useEffect(() => {
    const unsubscribe = wsClient.onStatusChange((newStatus) => {
      setStatus(newStatus);
    });

    // Auto connect on mount
    wsClient.connect();

    return () => {
      unsubscribe();
    };
  }, []);

  return (
    <WsContext.Provider
      value={{
        status,
        connect: () => wsClient.connect(),
        disconnect: () => wsClient.disconnect(),
        emitDevEvent: (eventData) => wsClient.emitDevEvent(eventData)
      }}
    >
      {children}
    </WsContext.Provider>
  );
};

export const useWs = () => useContext(WsContext);
