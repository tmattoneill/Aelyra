import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  getUser,
  isExpired,
  saveSession,
  updateUser,
} from '../authStore';

describe('authStore', () => {
  it('stores a session and converts expires_in into an absolute expiry', () => {
    saveSession({ access_token: 'abc', refresh_token: 'refresh', expires_in: 3600, user: { id: 'matt' } });

    expect(getAccessToken()).toBe('abc');
    expect(getRefreshToken()).toBe('refresh');
    expect(getUser()).toEqual({ id: 'matt' });
    expect(isExpired()).toBe(false);
  });

  it('reports expiry ahead of the real deadline so in-flight requests survive', () => {
    // 30s left is inside the 60s skew, so this counts as expired.
    saveSession({ access_token: 'abc', expires_in: 30 });
    expect(isExpired()).toBe(true);
  });

  it('keeps the existing refresh token when a refresh response omits one', () => {
    saveSession({ access_token: 'first', refresh_token: 'long-lived', expires_in: 3600 });
    saveSession({ access_token: 'second', expires_in: 3600 });

    expect(getAccessToken()).toBe('second');
    expect(getRefreshToken()).toBe('long-lived');
  });

  it('persists profile edits so they survive a reload', () => {
    saveSession({ access_token: 'abc', expires_in: 3600, user: { id: 'matt', first_name: 'Matt' } });
    updateUser({ first_name: 'Matthew', location: 'GB' });

    expect(getUser()).toEqual({ id: 'matt', first_name: 'Matthew', location: 'GB' });
  });

  it('clears everything on logout', () => {
    saveSession({ access_token: 'abc', expires_in: 3600 });
    clearSession();

    expect(getAccessToken()).toBeNull();
    expect(getUser()).toBeNull();
  });

  it('treats corrupt storage as no session rather than throwing', () => {
    sessionStorage.setItem('aelyra_auth', '{not valid json');
    expect(getAccessToken()).toBeNull();
  });
});
