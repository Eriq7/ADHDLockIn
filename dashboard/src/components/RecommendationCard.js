import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const ARM_LABELS = ['180s', '210s', '240s', '270s', '300s', '330s'];

function RecommendationCard({ title, data, sourceLabel }) {
  if (!data) return null;

  const recommended = data.recommended;
  const arms = data.allScores || data.arms || [];

  const chartData = arms.map((arm, i) => ({
    name: ARM_LABELS[i] || `${arm.arm}s`,
    score: parseFloat(arm.score.toFixed(3)),
    alpha: arm.alpha || arm.totalAlpha || 1,
    beta: arm.beta || arm.totalBeta || 1,
    arm: arm.arm,
  }));

  const contextLabel = data.contextKey
    ? data.contextKey
        .replace('_', ' - ')
        .replace('morning', 'Morning')
        .replace('afternoon', 'Afternoon')
        .replace('evening', 'Evening')
        .replace('night', 'Night')
        .replace('early', 'Early Session')
        .replace('mid', 'Mid Session')
        .replace('late', 'Late Session')
    : '';

  const recommendedMinutes = recommended ? `${recommended} seconds (${(recommended / 60).toFixed(1)} min)` : 'N/A';

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const d = payload[0].payload;
      const alphaLabel = d.alpha !== undefined ? d.alpha : 'N/A';
      const betaLabel = d.beta !== undefined ? d.beta : 'N/A';
      return (
        <div style={{ backgroundColor: '#16213e', border: '1px solid #0f3460', padding: '10px', borderRadius: '8px', color: '#fff' }}>
          <p>{d.name}</p>
          <p>Score: {d.score}</p>
          <p>Alpha (successes): {alphaLabel}</p>
          <p>Beta (failures): {betaLabel}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="recommendation-card">
      <h3 className="chart-title">{title}</h3>
      {contextLabel && <p className="rec-context">Context: {contextLabel}</p>}
      <p className="rec-interval">Recommended: <strong>{recommendedMinutes}</strong></p>
      {sourceLabel && <p className="rec-source">{sourceLabel}</p>}
      {data.totalUsers && <p className="rec-source">Based on {data.totalUsers} users</p>}

      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
          <XAxis dataKey="name" stroke="#a0a0b0" />
          <YAxis stroke="#a0a0b0" domain={[0, 1]} />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="score" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, index) => (
              <Cell key={index} fill={entry.arm === recommended ? '#4ecca3' : '#0f3460'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div className="arm-details">
        {chartData.map((arm, i) => (
          <div key={i} className="arm-detail">
            <span className="arm-label">{arm.name}</span>
            <span className="arm-stats">✓{arm.alpha} ✗{arm.beta}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default RecommendationCard;
