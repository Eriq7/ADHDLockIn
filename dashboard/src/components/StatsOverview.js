import React from 'react';

function StatsOverview({ sessions }) {
  if (!sessions || sessions.length === 0) {
    return (
      <div className="stats-overview">
        <div className="stat-card"><h3>Total Sessions</h3><p className="stat-value">0</p></div>
        <div className="stat-card"><h3>Completion Rate</h3><p className="stat-value">N/A</p></div>
        <div className="stat-card"><h3>Total Study Time</h3><p className="stat-value">0 hrs 0 mins</p></div>
        <div className="stat-card"><h3>Average Interval</h3><p className="stat-value">N/A</p></div>
      </div>
    );
  }

  const total = sessions.length;
  const completed = sessions.filter(s => s.completed).length;
  const completionRate = ((completed / total) * 100).toFixed(1);
  const totalSeconds = sessions.reduce((sum, s) => sum + (s.durationSeconds || s.duration_seconds || 0), 0);
  const hours = Math.floor(totalSeconds / 3600);
  const mins = Math.floor((totalSeconds % 3600) / 60);

  const intervals = sessions
    .map(s => s.intervalSelected || s.interval_selected)
    .filter(v => v != null);
  const avgInterval = intervals.length > 0
    ? Math.round(intervals.reduce((a, b) => a + b, 0) / intervals.length)
    : 'N/A';

  return (
    <div className="stats-overview">
      <div className="stat-card">
        <h3>Total Sessions</h3>
        <p className="stat-value">{total}</p>
      </div>
      <div className="stat-card">
        <h3>Completion Rate</h3>
        <p className="stat-value">{completionRate}%</p>
      </div>
      <div className="stat-card">
        <h3>Total Study Time</h3>
        <p className="stat-value">{hours} hrs {mins} mins</p>
      </div>
      <div className="stat-card">
        <h3>Average Interval</h3>
        <p className="stat-value">{avgInterval}{avgInterval !== 'N/A' ? 's' : ''}</p>
      </div>
    </div>
  );
}

export default StatsOverview;
