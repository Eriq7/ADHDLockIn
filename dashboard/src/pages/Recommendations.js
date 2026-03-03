import React, { useState, useEffect, useCallback } from 'react';
import client from '../api/client';
import RecommendationCard from '../components/RecommendationCard';

function getLocalTimeOfDay() {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return 'morning';
  if (hour >= 12 && hour < 17) return 'afternoon';
  if (hour >= 17 && hour < 21) return 'evening';
  return 'night';
}

function Recommendations({ user }) {
  const [personal, setPersonal] = useState(null);
  const [population, setPopulation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const timeOfDay = getLocalTimeOfDay();
      const sessionDepth = 'early';
      const [personalRes, populationRes] = await Promise.all([
        client.get(`/recommendations/${user.username}?timeOfDay=${timeOfDay}&sessionDepth=${sessionDepth}`),
        client.get(`/recommendations/population?timeOfDay=${timeOfDay}&sessionDepth=${sessionDepth}`),
      ]);
      setPersonal(personalRes.data.data);
      setPopulation(populationRes.data.data);
    } catch (err) {
      setError('Failed to load data. Make sure the API server is running on port 3001.');
    } finally {
      setLoading(false);
    }
  }, [user.username]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) return <div className="page-container"><p className="loading-text">Loading...</p></div>;
  if (error) return <div className="page-container"><p className="error-text">{error}</p></div>;

  const personalRec = personal?.recommended;
  const populationRec = population?.recommended;

  let comparison = '';
  if (personalRec && populationRec) {
    if (personalRec === populationRec) {
      comparison = 'Your preference matches the community!';
    } else if (personalRec > populationRec) {
      comparison = 'You prefer longer intervals than most users.';
    } else {
      comparison = 'You prefer shorter intervals than most users.';
    }
  }

  const personalSource = personal?.source === 'personal'
    ? 'Based on your data'
    : 'Based on community data (not enough personal data yet)';

  return (
    <div className="page-container">
      <div className="recommendations-grid">
        <RecommendationCard
          title="Your Personal Recommendation"
          data={personal}
          sourceLabel={personalSource}
        />
        <RecommendationCard
          title="Community Recommendations"
          data={population}
        />
      </div>

      {personalRec && populationRec && (
        <div className="comparison-section">
          <h3 className="chart-title">Comparison</h3>
          <div className="comparison-row">
            <span>Your recommended interval: <strong>{personalRec}s</strong></span>
            <span>Community recommended interval: <strong>{populationRec}s</strong></span>
          </div>
          <p className="comparison-result">{comparison}</p>
        </div>
      )}

    </div>
  );
}

export default Recommendations;
