import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const TIME_LABELS = {
  morning: 'Morning',
  afternoon: 'Afternoon',
  evening: 'Evening',
  night: 'Night',
};

function TimeOfDayChart({ sessions }) {
  if (!sessions || sessions.length === 0) return null;

  // Group by timeOfDay
  const groups = {};
  sessions.forEach(s => {
    const tod = s.timeOfDay || s.time_of_day;
    if (!tod) return;
    if (!groups[tod]) groups[tod] = { completed: 0, total: 0 };
    groups[tod].total++;
    if (s.completed) groups[tod].completed++;
  });

  const data = ['morning', 'afternoon', 'evening', 'night'].map(key => ({
    name: TIME_LABELS[key] || key,
    rate: groups[key] ? Math.round((groups[key].completed / groups[key].total) * 100) : 0,
    total: groups[key] ? groups[key].total : 0,
  }));

  const maxRate = Math.max(...data.map(d => d.rate));

  return (
    <div className="chart-container">
      <h3 className="chart-title">Performance by Time of Day</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
          <XAxis dataKey="name" stroke="#a0a0b0" />
          <YAxis domain={[0, 100]} stroke="#a0a0b0" label={{ value: '%', angle: -90, position: 'insideLeft', fill: '#a0a0b0' }} />
          <Tooltip
            contentStyle={{ backgroundColor: '#16213e', border: '1px solid #0f3460', color: '#fff' }}
            formatter={(value, name, props) => [`${value}% (${props.payload.total} sessions)`, 'Completion Rate']}
          />
          <Bar dataKey="rate" radius={[4, 4, 0, 0]}>
            {data.map((entry, index) => (
              <Cell key={index} fill={entry.rate === maxRate && entry.rate > 0 ? '#4ecca3' : '#0f3460'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default TimeOfDayChart;
