import axios from 'axios';

import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  isExpired,
  notifySessionExpired,
  saveSession,
} from './auth/authStore';

/**
 * Base URL for the API.
 *
 * Empty by default so requests are relative: in development that routes them
 * through the Vite proxy (see vite.config.js), and in production the frontend
 * is served from the same origin as the API. Set VITE_API_BASE_URL to point
 * elsewhere. Note the VITE_ prefix is required; Vite does not expose
 * REACT_APP_ variables.
 */
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export const api = axios.create({
  baseURL: API_BASE_URL,
  // Generation can legitimately take a while, but not forever; without this a
  // hung backend left the UI spinning with no way out.
  timeout: 120000,
});

/**
 * Exchange the one-time code from the OAuth redirect for a real session.
 */
export async function exchangeAuthCode(code) {
  const { data } = await axios.post(`${API_BASE_URL}/api/spotify/session`, { code });
  return saveSession(data);
}

// A single refresh in flight, shared by every request that needs it, so a burst
// of concurrent 401s produces one refresh rather than one each.
let refreshPromise = null;

async function refreshSession() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) throw new Error('No refresh token available');

  if (!refreshPromise) {
    refreshPromise = axios
      .post(`${API_BASE_URL}/api/spotify/refresh`, { refresh_token: refreshToken })
      .then(({ data }) => saveSession(data))
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

api.interceptors.request.use(async (config) => {
  // Renew proactively when the stored token is at or near its expiry, rather
  // than waiting for the request to come back 401.
  if (isExpired() && getRefreshToken() && !config._skipRefresh) {
    try {
      await refreshSession();
    } catch {
      notifySessionExpired();
    }
  }

  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;

    // One retry after a refresh; if that also 401s the session is genuinely gone.
    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true;
      if (getRefreshToken()) {
        try {
          await refreshSession();
          original.headers.Authorization = `Bearer ${getAccessToken()}`;
          return api(original);
        } catch {
          // fall through to logout
        }
      }
      clearSession();
      notifySessionExpired();
    }

    return Promise.reject(error);
  },
);

/**
 * Authorization header for fetch-based calls (the SSE stream), which do not
 * pass through the axios interceptors above.
 */
export async function authHeader() {
  if (isExpired() && getRefreshToken()) {
    try {
      await refreshSession();
    } catch {
      notifySessionExpired();
    }
  }
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Human-readable message from an axios error, without leaking internals.
 */
export function errorMessage(error, fallback = 'Something went wrong. Please try again.') {
  if (error?.code === 'ECONNABORTED') return 'The request timed out. Please try again.';
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string' && detail) return detail;
  if (error?.response?.status === 429) return 'Too many requests right now. Please wait a moment.';
  if (!error?.response) return 'Could not reach the server. Check your connection and try again.';
  return fallback;
}
