// context/WSContext.tsx
import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import { AppState } from 'react-native';
import { MarketData, WSMessage } from '../types';

interface WSContextType {
  isConnected: boolean;
  marketData: MarketData | null;
  error: string | null;
  requestData: (key: string) => Promise<any>;
}

const WSContext = createContext<WSContextType | undefined>(undefined);

export const useWS = () => {
  const context = useContext(WSContext);
  if (!context) throw new Error('useWS must be used within WSProvider');
  return context;
};

interface WSProviderProps {
  children: React.ReactNode;
  wsUrl?: string;
}

export default function WSProvider({ 
  children, 
  wsUrl = 'ws://localhost:5001' 
}: WSProviderProps) {
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [marketData, setMarketData] = useState<MarketData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const appState = useRef(AppState.currentState);

  const connect = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log('✓ WebSocket connected');
        setIsConnected(true);
        setError(null);
        wsRef.current?.send(JSON.stringify({
          type: 'subscribe',
          channel: 'market_data',
        }));
      };

      wsRef.current.onmessage = (event) => {
        const message: WSMessage = JSON.parse(event.data);
        
        if (message.type === 'market_update' && message.data) {
          setMarketData(message.data);
        } else if (message.type === 'error') {
          setError(message.message || 'Unknown error');
        }
      };

      wsRef.current.onerror = (err) => {
        console.error('WebSocket error:', err);
        setError('Connection error');
        setIsConnected(false);
      };

      wsRef.current.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        // Attempt reconnect in 5 seconds
        setTimeout(connect, 5000);
      };
    } catch (err) {
      console.log('WebSocket unavailable, using mock data');
      setError('WebSocket unavailable');
      setIsConnected(false);
    }
  };

  const requestData = async (key: string): Promise<any> => {
    return new Promise((resolve) => {
      const messageId = `${Date.now()}`;
      wsRef.current?.send(JSON.stringify({
        type: 'request_data',
        key,
        id: messageId,
      }));

      const timeout = setTimeout(() => {
        resolve(null);
      }, 5000);

      // In real implementation, would use messageId to match response
      setTimeout(() => clearTimeout(timeout), 5000);
    });
  };

  const keepAlive = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'ping' }));
    }
  };

  useEffect(() => {
    // Initial connection
    connect();

    // Setup keep-alive
    const keepAliveInterval = setInterval(keepAlive, 30000);

    // App lifecycle
    const subscription = AppState.addEventListener('change', (newState) => {
      if (newState === 'active' && appState.current !== 'active') {
        console.log('Reconnecting after app resume...');
        connect();
      }
      appState.current = newState;
    });

    return () => {
      clearInterval(keepAliveInterval);
      subscription.remove();
      wsRef.current?.close();
    };
  }, []);

  return (
    <WSContext.Provider value={{ isConnected, marketData, error, requestData }}>
      {children}
    </WSContext.Provider>
  );
}
