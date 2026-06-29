// src/components/common/RiskBadge.jsx
import React from 'react';
import { getRiskColor, getRiskBg } from '../../utils/formatters';

export default function RiskBadge({ level, label }) {
  if (!level && !label) return <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>—</span>;
  const display = label || level;
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 5,
      padding: '3px 10px',
      borderRadius: 99,
      fontSize: 12,
      fontWeight: 600,
      color: getRiskColor(level),
      background: getRiskBg(level),
      border: `1px solid ${getRiskColor(level)}30`,
      textTransform: 'uppercase',
      letterSpacing: '0.4px',
      whiteSpace: 'nowrap',
    }}>
      <span style={{
        width: 5, height: 5,
        borderRadius: '50%',
        background: getRiskColor(level),
        flexShrink: 0,
      }} />
      {display}
    </span>
  );
}
