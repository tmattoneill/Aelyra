import React, { useState, useEffect } from 'react';
import axios from 'axios';

const UserProfile = ({ spotifyToken, userInfo, onProfileUpdate }) => {
  const [profile, setProfile] = useState({
    first_name: '',
    last_name: '',
    location: '',
    openai_api_key: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showOpenAIKey, setShowOpenAIKey] = useState(false);

  useEffect(() => {
    // Load existing profile data
    if (userInfo) {
      setProfile({
        first_name: userInfo.first_name || '',
        last_name: userInfo.last_name || '',
        location: userInfo.location || '',
        openai_api_key: userInfo.has_openai_key ? '••••••••••••' : ''
      });
    }
  }, [userInfo]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setProfile(prev => ({
      ...prev,
      [name]: value
    }));
    setError('');
    setSuccess('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const updateData = {
        spotify_access_token: spotifyToken,
        first_name: profile.first_name || null,
        last_name: profile.last_name || null,
        location: profile.location || null
      };

      // Only include OpenAI key if it's been changed (not the masked version)
      if (profile.openai_api_key && !profile.openai_api_key.includes('••')) {
        updateData.openai_api_key = profile.openai_api_key;
      }

      const response = await axios.put('http://127.0.0.1:5988/api/user-profile', updateData);
      
      setSuccess('Profile updated successfully!');
      
      // Update the parent component with new profile data
      if (onProfileUpdate) {
        onProfileUpdate(response.data);
      }

      // Update local state to show masked key if one was set
      if (response.data.has_openai_key && profile.openai_api_key && !profile.openai_api_key.includes('••')) {
        setProfile(prev => ({
          ...prev,
          openai_api_key: '••••••••••••'
        }));
      }

    } catch (error) {
      console.error('Error updating profile:', error);
      setError(error.response?.data?.detail || 'Failed to update profile');
    } finally {
      setLoading(false);
    }
  };

  const toggleOpenAIKeyVisibility = () => {
    if (showOpenAIKey) {
      setShowOpenAIKey(false);
      // Reset to masked if it was masked before
      if (userInfo?.has_openai_key && profile.openai_api_key.includes('••')) {
        setProfile(prev => ({
          ...prev,
          openai_api_key: '••••••••••••'
        }));
      }
    } else {
      setShowOpenAIKey(true);
      // Clear the field to allow new input
      if (profile.openai_api_key.includes('••')) {
        setProfile(prev => ({
          ...prev,
          openai_api_key: ''
        }));
      }
    }
  };

  return (
    <div className="card">
      <h2 style={{ color: '#1BD760', marginBottom: '20px' }}>Account Information</h2>
      
      <div style={{ marginBottom: '20px', padding: '15px', background: '#181818', borderRadius: '6px' }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '10px' }}>
          {userInfo?.images?.[0] && (
            <img 
              src={userInfo.images[0].url} 
              alt="Profile" 
              style={{ 
                width: '60px', 
                height: '60px', 
                borderRadius: '50%', 
                marginRight: '15px' 
              }}
            />
          )}
          <div>
            <h3 style={{ color: '#EFEFEF', margin: '0' }}>{userInfo?.display_name}</h3>
            <p style={{ color: '#B3B3B3', margin: '0', fontSize: '14px' }}>{userInfo?.email}</p>
            <p style={{ color: '#B3B3B3', margin: '0', fontSize: '12px' }}>Spotify ID: {userInfo?.id}</p>
          </div>
        </div>
      </div>

      {error && <div className="error">{error}</div>}
      {success && <div className="success">{success}</div>}

      <form onSubmit={handleSubmit}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginBottom: '20px' }}>
          <div className="form-group">
            <label>First Name</label>
            <input
              type="text"
              name="first_name"
              value={profile.first_name}
              onChange={handleChange}
              className="form-input"
              placeholder="Enter your first name"
            />
          </div>
          
          <div className="form-group">
            <label>Last Name</label>
            <input
              type="text"
              name="last_name"
              value={profile.last_name}
              onChange={handleChange}
              className="form-input"
              placeholder="Enter your last name"
            />
          </div>
        </div>

        <div className="form-group">
          <label>Location (Country Code)</label>
          <input
            type="text"
            name="location"
            value={profile.location}
            onChange={handleChange}
            className="form-input"
            placeholder="e.g., US, GB, FR"
            maxLength="2"
            style={{ textTransform: 'uppercase' }}
          />
        </div>

        <div className="form-group">
          <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            OpenAI API Key (Optional)
            <button
              type="button"
              onClick={toggleOpenAIKeyVisibility}
              className="btn-secondary"
              style={{ padding: '5px 10px', fontSize: '12px' }}
            >
              {showOpenAIKey ? 'Hide' : 'Edit'}
            </button>
          </label>
          <input
            type={showOpenAIKey ? "text" : "password"}
            name="openai_api_key"
            value={profile.openai_api_key}
            onChange={handleChange}
            className="form-input"
            placeholder="sk-..."
            disabled={!showOpenAIKey && profile.openai_api_key.includes('••')}
          />
          <small style={{ color: '#B3B3B3', fontSize: '12px', marginTop: '5px', display: 'block' }}>
            Store your personal OpenAI API key to use for playlist generation. Leave blank to use the system default.
          </small>
        </div>

        <button 
          type="submit" 
          className="btn" 
          disabled={loading}
          style={{ marginTop: '20px' }}
        >
          {loading ? 'Updating...' : 'Update Profile'}
        </button>
      </form>
    </div>
  );
};

export default UserProfile;