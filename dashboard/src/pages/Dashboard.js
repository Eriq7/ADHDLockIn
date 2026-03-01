import React, { useState, useEffect } from 'react';
import client from '../api/client';
import StatsOverview from '../components/StatsOverview';
import SessionChart from '../components/SessionChart';
import CompletionRate from '../components/CompletionRate';
import TimeOfDayChart from '../components/TimeOfDayChart';

function Dashboard({ user }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function fetchSessions() {
      try {
        const res = await client.get(`/sessions/${user.username}?limit=9999`);
        setSessions(res.data.data.sessions || []);
      } catch (err) {
        setError('Failed to load data. Make sure the API server is running on port 3001.');
      } finally {
        setLoading(false);
      }
    }
    fetchSessions();
  }, [user.username]);

  if (loading) return <div className="page-container"><p className="loading-text">Loading...</p></div>;
  if (error) return <div className="page-container"><p className="error-text">{error}</p></div>;

  if (sessions.length === 0) {
    return (
      <div className="page-container">
        <StatsOverview sessions={[]} />
        <div className="empty-state">
          <p>No session data yet. Start studying with the desktop app to see your stats here!</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <StatsOverview sessions={sessions} />
      <div className="charts-row">
        <SessionChart sessions={sessions} />
        <CompletionRate sessions={sessions} />
      </div>
      <TimeOfDayChart sessions={sessions} />
    </div>
  );
}

export default Dashboard;
