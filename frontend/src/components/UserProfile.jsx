import React, { useEffect, useState } from 'react';

import { api, errorMessage } from '../config';

export default function UserProfile({ userInfo, onProfileUpdate, onLogout }) {
  const [form, setForm] = useState({ first_name: '', last_name: '', location: '' });
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [hasStoredKey, setHasStoredKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    setForm({
      first_name: userInfo?.first_name ?? '',
      last_name: userInfo?.last_name ?? '',
      location: userInfo?.location ?? '',
    });
    setHasStoredKey(Boolean(userInfo?.has_openai_key));
  }, [userInfo]);

  const update = (field) => (e) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
    setMessage(null);
  };

  const save = async (extra = {}) => {
    setSaving(true);
    setMessage(null);
    try {
      const payload = {
        first_name: form.first_name || null,
        last_name: form.last_name || null,
        // Country codes are stored uppercase regardless of how they were typed;
        // the field used to only *look* uppercase via CSS.
        location: form.location ? form.location.toUpperCase() : null,
        ...extra,
      };
      if (apiKeyInput.trim() && !extra.remove_openai_api_key) {
        payload.openai_api_key = apiKeyInput.trim();
      }

      const { data } = await api.put('/api/user-profile', payload);
      setHasStoredKey(Boolean(data.has_openai_key));
      setApiKeyInput('');
      onProfileUpdate?.({
        first_name: data.first_name,
        last_name: data.last_name,
        location: data.location,
        has_openai_key: data.has_openai_key,
      });
      setMessage({ type: 'success', text: 'Profile saved.' });
    } catch (err) {
      setMessage({ type: 'error', text: errorMessage(err, 'Could not save your profile.') });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card">
      <h2>Account</h2>

      <div style={{ display: 'flex', alignItems: 'center', gap: 15, margin: '20px 0' }}>
        {userInfo?.images?.[0]?.url && (
          <img
            src={userInfo.images[0].url}
            alt=""
            style={{ width: 64, height: 64, borderRadius: '50%', objectFit: 'cover' }}
          />
        )}
        <div>
          <div style={{ fontWeight: 600 }}>{userInfo?.display_name ?? userInfo?.id}</div>
          {userInfo?.email && <div className="text-faint">{userInfo.email}</div>}
        </div>
      </div>

      {message && (
        <div className={message.type === 'error' ? 'error' : 'success'} role={message.type === 'error' ? 'alert' : 'status'}>
          {message.text}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          save();
        }}
      >
        <div className="profile-grid">
          <div className="form-group">
            <label htmlFor="first-name">First name</label>
            <input
              id="first-name"
              className="form-input"
              value={form.first_name}
              onChange={update('first_name')}
              maxLength={100}
            />
          </div>
          <div className="form-group">
            <label htmlFor="last-name">Last name</label>
            <input
              id="last-name"
              className="form-input"
              value={form.last_name}
              onChange={update('last_name')}
              maxLength={100}
            />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="location">Country code</label>
          <input
            id="location"
            className="form-input"
            value={form.location}
            onChange={update('location')}
            maxLength={2}
            placeholder="GB"
            style={{ textTransform: 'uppercase', maxWidth: 120 }}
          />
        </div>

        <div className="form-group">
          <label htmlFor="openai-key">Your OpenAI API key (optional)</label>
          <input
            id="openai-key"
            className="form-input"
            type="password"
            value={apiKeyInput}
            onChange={(e) => setApiKeyInput(e.target.value)}
            placeholder={hasStoredKey ? 'A key is saved. Type a new one to replace it.' : 'sk-…'}
            autoComplete="off"
          />
          <p className="form-hint">
            {hasStoredKey
              ? 'Leave blank to keep the saved key.'
              : 'Leave blank to use the shared key.'}
          </p>
          {hasStoredKey && (
            <button
              type="button"
              className="btn btn-danger btn-small"
              style={{ marginTop: 10 }}
              onClick={() => save({ remove_openai_api_key: true })}
              disabled={saving}
            >
              Remove saved key
            </button>
          )}
        </div>

        <div className="btn-row">
          <button type="submit" className="btn" disabled={saving}>
            {saving ? 'Saving…' : 'Save profile'}
          </button>
          <button type="button" className="btn btn-danger" onClick={onLogout}>
            Disconnect Spotify
          </button>
        </div>
      </form>
    </div>
  );
}
