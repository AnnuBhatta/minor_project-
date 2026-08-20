import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
} from 'react';

/**
 * WebSocketContext
 *
 * Manages the browser's connection to the backend alert WebSocket:
 *   ws://localhost:8000/ws/alerts/?token=<access_token>
 *
 * The backend AlertConsumer authenticates via the `?token=` query param,
 * then joins the caller's own group plus (for guardians) their linked
 * patients' alert groups. It pushes every engine alert as a `new_alert`
 * message:  { type: 'new_alert', alert: { id, tier, title, message,
 * severity, status, location, user_id, user_name, ... } }
 *
 * Robustness:
 *  - A 3s watchdog watches localStorage for the access token. When a token
 *    appears (e.g. the user logs in AFTER the app mounted), it connects.
 *    When it disappears (logout), it closes the socket. This is why the
 *    provider works even though Login.jsx writes tokens directly to
 *    localStorage without dispatching any event.
 *  - If the socket drops with an abnormal close code (token expired, server
 *    restart), it refreshes the JWT via /api/auth/refresh/ before the next
 *    reconnect, so a 5-minute access token can't silently kill the channel.
 *  - Everything is logged to the browser console with a [WS] prefix for
 *    debugging.
 */
const WebSocketContext = createContext(null);

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/alerts/';

const readToken = () => localStorage.getItem('access_token');
const readRefresh = () => localStorage.getItem('refresh_token');

async function refreshAccessToken() {
  const refresh = readRefresh();
  if (!refresh) return null;
  try {
    const res = await fetch('/api/auth/refresh/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    });
    if (!res.ok) throw new Error(`refresh failed: ${res.status}`);
    const data = await res.json();
    localStorage.setItem('access_token', data.access);
    return data.access;
  } catch (e) {
    console.warn('[WS] Token refresh failed — logging out sockets:', e);
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    return null;
  }
}

export const WebSocketProvider = ({ children }) => {
  const [status, setStatus] = useState('idle'); // idle | connecting | open | closed | error
  const [lastAlert, setLastAlert] = useState(null);

  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const listenersRef = useRef(new Set());

  const connect = useCallback(async () => {
    const token = readToken();
    if (!token) {
      // No token → make sure the socket is closed and stay idle.
      if (wsRef.current) {
        const ws = wsRef.current;
        wsRef.current = null;
        try { ws.close(); } catch { /* noop */ }
      }
      setStatus('idle');
      return;
    }

    if (
      wsRef.current &&
      wsRef.current.readyState === WebSocket.OPEN ||
      wsRef.current && wsRef.current.readyState === WebSocket.CONNECTING
    ) {
      return; // already connected or connecting
    }

    const url = `${WS_URL}?token=${encodeURIComponent(token)}`;
    console.log(`[WS] Connecting to ${url}`);
    const ws = new WebSocket(url);
    wsRef.current = ws;
    setStatus('connecting');

    ws.onopen = () => {
      console.log('[WS] Connected to /ws/alerts/');
      setStatus('open');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'new_alert' && data.alert) {
          console.log('[WS] 📨 New alert received:', data.alert);
          setLastAlert(data.alert);
          listenersRef.current.forEach((fn) => fn(data.alert));
        } else {
          console.log('[WS] Message:', data);
        }
      } catch (err) {
        console.error('[WS] Failed to parse message:', err);
      }
    };

    ws.onerror = (err) => {
      console.error('[WS] WebSocket error:', err);
      setStatus('error');
    };

    ws.onclose = async (e) => {
      console.warn(
        `[WS] Disconnected (code=${e.code}, reason=${e.reason || 'none'})`
      );
      setStatus('closed');
      if (wsRef.current !== ws) return; // superseded
      clearTimeout(reconnectTimerRef.current);
      if (e.code !== 1000 && readToken()) {
        // Abnormal close (expired token / server restart) → refresh the JWT
        // before the watchdog reconnects with a valid token.
        await refreshAccessToken();
      }
      reconnectTimerRef.current = setTimeout(connect, 3000);
    };
  }, []);

  /** Subscribe to every incoming alert. Returns an unsubscribe fn. */
  const subscribe = useCallback((fn) => {
    listenersRef.current.add(fn);
    return () => listenersRef.current.delete(fn);
  }, []);

  useEffect(() => {
    connect();

    // Watchdog: re-sync the token and (re)connect whenever the auth state
    // changes — covers login-after-mount and logout without touching
    // Login.jsx / AuthContext.
    const watchdog = setInterval(() => {
      if (readToken()) {
        connect();
      } else if (wsRef.current) {
        const ws = wsRef.current;
        wsRef.current = null;
        try { ws.close(); } catch { /* noop */ }
        setStatus('idle');
      }
    }, 3000);

    const onFocus = () => connect();
    window.addEventListener('focus', onFocus);

    return () => {
      clearInterval(watchdog);
      clearTimeout(reconnectTimerRef.current);
      window.removeEventListener('focus', onFocus);
      const ws = wsRef.current;
      wsRef.current = null;
      if (ws) ws.close();
    };
  }, [connect]);

  return (
    <WebSocketContext.Provider value={{ status, lastAlert, subscribe, connect }}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useAlertsSocket = () => {
  const ctx = useContext(WebSocketContext);
  if (!ctx) {
    throw new Error('useAlertsSocket must be used within a WebSocketProvider');
  }
  return ctx;
};