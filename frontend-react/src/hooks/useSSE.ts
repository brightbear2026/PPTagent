/* ============================================================
   PPT Agent — SSE Hook for real-time progress
   ============================================================ */

import { useEffect, useRef, useState, useCallback } from 'react';
import type { SSEProgressEvent, TaskStatusEnum } from '../types';

interface UseSSEOptions {
  /** Auto-reconnect on error */
  reconnect?: boolean;
  /** Max reconnect attempts */
  maxRetries?: number;
}

interface UseSSEReturn {
  events: SSEProgressEvent[];
  latest: SSEProgressEvent | null;
  status: TaskStatusEnum | null;
  progress: number;
  isFinished: boolean;
  error: string | null;
  connect: (taskId: string) => void;
  disconnect: () => void;
}

export function useSSE(options: UseSSEOptions = {}): UseSSEReturn {
  const { reconnect = true, maxRetries = 5 } = options;

  const [events, setEvents] = useState<SSEProgressEvent[]>([]);
  const [latest, setLatest] = useState<SSEProgressEvent | null>(null);
  const [error, setError] = useState<string | null>(null);

  const esRef = useRef<EventSource | null>(null);
  const retriesRef = useRef(0);
  const taskIdRef = useRef<string | null>(null);

  const isFinished = latest
    ? ['completed', 'failed', 'cancelled'].includes(latest.status)
    : false;

  const disconnect = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    taskIdRef.current = null;
    retriesRef.current = 0;
  }, []);

  const connect = useCallback((taskId: string) => {
    disconnect();
    taskIdRef.current = taskId;
    retriesRef.current = 0;
    setError(null);
    setEvents([]);
    setLatest(null);

    const apiBase = import.meta.env.VITE_API_BASE || '/api';
    const url = `${apiBase}/status/${taskId}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const data: SSEProgressEvent = JSON.parse(e.data);
        setLatest(data);
        setEvents((prev) => [...prev.slice(-50), data]);
        retriesRef.current = 0;

        if (['completed', 'failed', 'cancelled'].includes(data.status)) {
          es.close();
          esRef.current = null;
        }
      } catch {
        // ignore malformed events
      }
    };

    es.onerror = () => {
      if (reconnect && retriesRef.current < maxRetries) {
        retriesRef.current++;
        // EventSource auto-reconnects, but we track retries
      } else if (!reconnect || retriesRef.current >= maxRetries) {
        setError('连接中断');
        es.close();
        esRef.current = null;
      }
    };
  }, [disconnect, reconnect, maxRetries]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (esRef.current) {
        esRef.current.close();
      }
    };
  }, []);

  return {
    events,
    latest,
    status: latest?.status ?? null,
    progress: latest?.progress ?? 0,
    isFinished,
    error,
    connect,
    disconnect,
  };
}
