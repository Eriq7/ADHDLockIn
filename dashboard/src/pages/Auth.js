import React, { useState } from 'react';
import client from '../api/client';

function Auth({ onLogin }) {
  const [activeTab, setActiveTab] = useState('login');
  const [username, setUsername] = useState('');
  const [secretKey, setSecretKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Registration success state
  const [registered, setRegistered] = useState(false);
  const [regUsername, setRegUsername] = useState('');
  const [regSecretKey, setRegSecretKey] = useState('');
  const [copied, setCopied] = useState(false);
  const [copyButtonText, setCopyButtonText] = useState('Copy to Clipboard');

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await client.post('/users/login', { username, secretKey });
      const { userId, username: uname } = res.data.data;
      onLogin({ username: uname, userId });
    } catch (err) {
      if (err.response) {
        setError(err.response.data.error || 'Login failed.');
      } else {
        setError('Failed to connect to server. Make sure the API server is running on port 3001.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await client.post('/users/register', { username });
      setRegUsername(res.data.data.username);
      setRegSecretKey(res.data.data.secretKey);
      setRegistered(true);
    } catch (err) {
      if (err.response) {
        setError(err.response.data.error || 'Registration failed.');
      } else {
        setError('Failed to connect to server. Make sure the API server is running on port 3001.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    const text = `ADHDLockIn Credentials\nUsername: ${regUsername}\nSecret Key: ${regSecretKey}`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setCopyButtonText('✓ Copied!');
      setTimeout(() => setCopyButtonText('Copy to Clipboard'), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setCopyButtonText('✓ Copied!');
      setTimeout(() => setCopyButtonText('Copy to Clipboard'), 2000);
    }
  };

  const handleContinue = () => {
    onLogin({ username: regUsername, userId: regUsername });
  };

  // Registration success screen
  if (registered) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <h1 className="auth-title">Registration Successful!</h1>
          <div className="credentials-display">
            <div className="credential-row">
              <span className="credential-label">Username</span>
              <span className="credential-value">{regUsername}</span>
            </div>
            <div className="credential-row">
              <span className="credential-label">Secret Key</span>
              <span className="credential-value mono">{regSecretKey}</span>
            </div>
          </div>
          <div className="credentials-warning">
            ⚠️ Please save your username and secret key. You will need them to log in. This is the only time they will be shown.
          </div>
          <button className="btn btn-secondary" onClick={handleCopy}>
            {copyButtonText}
          </button>
          <button
            className={`btn btn-primary ${!copied ? 'btn-disabled' : ''}`}
            onClick={handleContinue}
            disabled={!copied}
          >
            I've saved my credentials — Continue
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">ADHDLockIn</h1>
        <p className="auth-subtitle">Focus Dashboard</p>

        <div className="auth-tabs">
          <button
            className={`auth-tab ${activeTab === 'login' ? 'active' : ''}`}
            onClick={() => { setActiveTab('login'); setError(''); }}
          >
            Login
          </button>
          <button
            className={`auth-tab ${activeTab === 'register' ? 'active' : ''}`}
            onClick={() => { setActiveTab('register'); setError(''); }}
          >
            Register
          </button>
        </div>

        {activeTab === 'login' ? (
          <form onSubmit={handleLogin}>
            <input
              type="text"
              className="auth-input"
              placeholder="Enter your username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            <input
              type="text"
              className="auth-input"
              placeholder="Enter your secret key"
              value={secretKey}
              onChange={(e) => setSecretKey(e.target.value)}
            />
            {error && <p className="auth-error">{error}</p>}
            <button className="btn btn-primary" type="submit" disabled={loading}>
              {loading ? 'Loading...' : 'Login'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleRegister}>
            <input
              type="text"
              className="auth-input"
              placeholder="Choose a username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            <p className="auth-hint">3-50 characters. Letters, numbers, and underscores only.</p>
            {error && <p className="auth-error">{error}</p>}
            <button className="btn btn-primary" type="submit" disabled={loading}>
              {loading ? 'Loading...' : 'Register'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

export default Auth;
