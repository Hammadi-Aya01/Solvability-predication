// src/components/common/ScoreGauge.jsx
import React, { useEffect, useRef } from 'react';
import { getScoreColor } from '../../utils/formatters';

export default function ScoreGauge({ score = 0, size = 140 }) {
  const color = getScoreColor(score);
  const r     = (size / 2) - 12;
  const cx    = size / 2;
  const cy    = size / 2;

  // Arc: 225° start, 270° sweep
  const startAngle = 225;
  const endAngle   = 225 + (score / 100) * 270;

  const polarToCartesian = (angle) => {
    const rad = (angle - 90) * Math.PI / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  };

  const describeArc = (start, end) => {
    const s = polarToCartesian(start);
    const e = polarToCartesian(end);
    const large = end - start > 180 ? 1 : 0;
    return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`;
  };

  const trackD  = describeArc(225, 495);
  const fillD   = describeArc(startAngle, endAngle);

  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg width={size} height={size}>
        <defs>
          <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"   stopColor={color} stopOpacity="0.4" />
            <stop offset="100%" stopColor={color} />
          </linearGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
            <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
        </defs>

        {/* Track */}
        <path
          d={trackD} fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth="8"
          strokeLinecap="round"
        />
        {/* Fill */}
        <path
          d={fillD} fill="none"
          stroke="url(#gaugeGrad)"
          strokeWidth="8"
          strokeLinecap="round"
          filter="url(#glow)"
          style={{ transition: 'all 1s cubic-bezier(0.16,1,0.3,1)' }}
        />
      </svg>

      {/* Center text */}
      <div style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        marginTop: 8,
      }}>
        <span style={{
          fontFamily: 'var(--font-display)',
          fontSize: size * 0.22,
          fontWeight: 800,
          color,
          lineHeight: 1,
        }}>{score}</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>/100</span>
      </div>
    </div>
  );
}
