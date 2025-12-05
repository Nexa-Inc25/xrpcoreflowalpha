'use client';

import { useEffect, useRef, useState, useCallback } from 'react';

interface WebSocketOptions {
  url: string;
  onMessage?: (data: any) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  reconnectInterval?: number;
  maxRetries?: number;
}

interface WebSocketState {
  isConnected: boolean;
  lastMessage: any;
  error: Event | null;
  retryCount: number;
}

export function useWebSocket({
  url,
  onMessage,
  onOpen,
  onClose,
  onError,
  reconnectInterval = 3000,
  maxRetries = 10,
}: WebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();

  const [state, setState] = useState<WebSocketState>({
    isConnected: false,
    lastMessage: null,
    error: null,
    retryCount: 0,
  });

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      wsRef.current = new WebSocket(url);

      wsRef.current.onopen = () => {
        retryCountRef.current = 0;
        setState(prev => ({ ...prev, isConnected: true, error: null, retryCount: 0 }));
        onOpen?.();
      };

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setState(prev => ({ ...prev, lastMessage: data }));
          onMessage?.(data);
        } catch {
          // Handle non-JSON messages
          setState(prev => ({ ...prev, lastMessage: event.data }));
          onMessage?.(event.data);
        }
      };

      wsRef.current.onclose = () => {
        setState(prev => ({ ...prev, isConnected: false }));
        onClose?.();

        // Reconnect logic
        if (retryCountRef.current < maxRetries) {
          retryCountRef.current++;
          setState(prev => ({ ...prev, retryCount: retryCountRef.current }));
          reconnectTimeoutRef.current = setTimeout(connect, reconnectInterval);
        }
      };

      wsRef.current.onerror = (error) => {
        setState(prev => ({ ...prev, error }));
        onError?.(error);
      };
    } catch (err) {
      console.error('WebSocket connection error:', err);
    }
  }, [url, onMessage, onOpen, onClose, onError, reconnectInterval, maxRetries]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const send = useCallback((data: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data));
    }
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return {
    ...state,
    send,
    disconnect,
    reconnect: connect,
  };
}

// SSE fallback hook for environments that don't support WebSocket
export function useEventSource(url: string, onMessage?: (data: any) => void) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<any>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => setIsConnected(true);
    
    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLastMessage(data);
        onMessage?.(data);
      } catch {
        setLastMessage(event.data);
        onMessage?.(event.data);
      }
    };

    es.onerror = () => {
      setIsConnected(false);
      es.close();
    };

    return () => {
      es.close();
    };
  }, [url, onMessage]);

  return { isConnected, lastMessage };
}
