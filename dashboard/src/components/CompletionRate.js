import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

function CompletionRate({ sessions }) {
  if (!sessions || sessions.length === 0) return null;

  // Group by date
  const dailyMap = {};
  sessions.forEach(s => {
    const date = (s.startTime || s.start_time || '').slice(0, 10);
    if (!date) return;
    if (!dailyMap[date]) dailyMap[date] = { completed: 0, total: 0 };
    dailyMap[date].total++;
    if (s.completed) dailyMap[date].completed++;
  });

  const data = Object.entries(dailyMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, { completed, total }]) => {
      const d = new Date(date);
      const label = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      return {
        date: label,
        rate: Math.round((completed / total) * 100),
        completed,
        total,
      };
    });

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const d = payload[0].payload;
      return (
        <div style={{ backgroundColor: '#16213e', border: '1px solid #0f3460', padding: '10px', borderRadius: '8px', color: '#fff' }}>
          <p>{label}</p>
          <p>Completion Rate: {d.rate}%</p>
          <p>Completed: {d.completed} / {d.total}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="chart-container">
      <h3 className="chart-title">Completion Rate Trend</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
          <XAxis dataKey="date" stroke="#a0a0b0" />
          <YAxis domain={[0, 100]} stroke="#a0a0b0" label={{ value: '%', angle: -90, position: 'insideLeft', fill: '#a0a0b0' }} />
          <Tooltip content={<CustomTooltip />} />
          <Line type="monotone" dataKey="rate" stroke="#e94560" strokeWidth={2} dot={{ fill: '#e94560', r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default CompletionRate;
