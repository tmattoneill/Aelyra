/**
 * Storage for the Spotify session.
 *
 * Everything lives under one key so the token, its expiry and the user profile
 * cannot drift apart.
 *
 * localStorage, so the session survives closing the tab and restarting the
 * browser. Access tokens last an hour, but the stored refresh token renews them
 * silently, so in practice you stay logged in until you disconnect or Spotify
 * revokes the grant. sessionStorage made you reconnect every time the tab
 * closed, for no security gain worth having: both are readable by any script on
 * the page, so the meaningful hardening is httpOnly cookies, not a shorter
 * lifetime on the same storage.
 */

const STORAGE_KEY = 'aelyra_auth';

// Where the session lives. Falls back to an in-memory shim when storage is
// unavailable (private mode, blocked cookies) so the app degrades to a
// single-page session rather than throwing on every read.
const memoryFallback = new Map();
const store = (() => {
  try {
    const probe = '__aelyra_probe__';
    window.localStorage.setItem(probe, '1');
    window.localStorage.removeItem(probe);
    return window.localStorage;
  } catch {
    return {
      getItem: (k) => memoryFallback.get(k) ?? null,
      setItem: (k, v) => memoryFallback.set(k, v),
      removeItem: (k) => memoryFallback.delete(k),
    };
  }
})();

// Refresh this far ahead of the real expiry so a request in flight when the
// token lapses does not fail.
const EXPIRY_SKEW_MS = 60 * 1000;

let listeners = [];

function read() {
  try {
    const raw = store.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    // Corrupt or unreadable storage should log the user out, not crash the app.
    return null;
  }
}

export function getSession() {
  return read();
}

export function getAccessToken() {
  return read()?.access_token ?? null;
}

export function getRefreshToken() {
  return read()?.refresh_token ?? null;
}

export function getUser() {
  return read()?.user ?? null;
}

export function isExpired() {
  const session = read();
  if (!session?.expires_at) return false;
  return Date.now() >= session.expires_at - EXPIRY_SKEW_MS;
}

/**
 * Store a session. `expires_in` is seconds from now, as the API returns it.
 */
export function saveSession({ access_token, refresh_token, expires_in, user }) {
  const existing = read();
  const session = {
    access_token,
    // Spotify only returns a refresh token sometimes; keep the old one if so.
    refresh_token: refresh_token ?? existing?.refresh_token ?? null,
    expires_at: Date.now() + (expires_in ?? 3600) * 1000,
    user: user ?? existing?.user ?? null,
  };
  store.setItem(STORAGE_KEY, JSON.stringify(session));
  return session;
}

/**
 * Merge changes into the stored user profile so edits survive a reload.
 */
export function updateUser(patch) {
  const session = read();
  if (!session) return null;
  session.user = { ...(session.user ?? {}), ...patch };
  store.setItem(STORAGE_KEY, JSON.stringify(session));
  return session.user;
}

export function clearSession() {
  store.removeItem(STORAGE_KEY);
}

/**
 * Subscribe to forced logouts (expired session, revoked refresh token).
 * Returns an unsubscribe function.
 */
export function onSessionExpired(callback) {
  listeners.push(callback);
  return () => {
    listeners = listeners.filter((l) => l !== callback);
  };
}

export function notifySessionExpired() {
  clearSession();
  listeners.forEach((l) => {
    try {
      l();
    } catch (err) {
      console.error('Session expiry handler failed', err);
    }
  });
}
