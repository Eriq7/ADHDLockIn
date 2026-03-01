import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

function SessionChart({ sessions }) {
  if (!sessions || sessions.length === 0) return null;

  // Group sessions by date and sum durations (convert to minutes)
  const dailyMap = {};
  sessions.forEach(s => {
    const date = (s.startTime || s.start_time || '').slice(0, 10);
    if (!date) return;
    if (!dailyMap[date]) dailyMap[date] = 0;
    dailyMap[date] += (s.durationSeconds || s.duration_seconds || 0);
  });

  const data = Object.entries(dailyMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, seconds]) => {
      const d = new Date(date);
      const label = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      return { date: label, minutes: Math.round(seconds / 60) };
    });

  return (
    <div className="chart-container">
      <h3 className="chart-title">Daily Study Time</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
          <XAxis dataKey="date" stroke="#a0a0b0" />
          <YAxis stroke="#a0a0b0" label={{ value: 'Minutes', angle: -90, position: 'insideLeft', fill: '#a0a0b0' }} />
          <Tooltip
            contentStyle={{ backgroundColor: '#16213e', border: '1px solid #0f3460', color: '#fff' }}
            formatter={(value) => [`${value} min`, 'Study Time']}
          />
          <Bar dataKey="minutes" fill="#4ecca3" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default SessionChart;
