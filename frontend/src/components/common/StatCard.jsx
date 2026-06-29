// src/components/common/StatCard.jsx
import React from 'react';
import { motion } from 'framer-motion';
import styles from './StatCard.module.css';

export default function StatCard({ title, value, sub, icon, color = 'var(--cyan)', trend, delay = 0 }) {
  return (
    <motion.div
      className={styles.card}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: [0.16, 1, 0.3, 1] }}
      whileHover={{ translateY: -3 }}
      style={{ '--accent': color }}
    >
      <div className={styles.header}>
        <span className={styles.title}>{title}</span>
        {icon && <div className={styles.icon} style={{ color, background: `${color}18` }}>{icon}</div>}
      </div>
      <div className={styles.value}>{value}</div>
      {(sub || trend !== undefined) && (
        <div className={styles.footer}>
          {sub && <span className={styles.sub}>{sub}</span>}
          {trend !== undefined && (
            <span className={styles.trend} style={{ color: trend >= 0 ? 'var(--green)' : 'var(--red)' }}>
              {trend >= 0 ? '↑' : '↓'} {Math.abs(trend)}%
            </span>
          )}
        </div>
      )}
      <div className={styles.glow} />
    </motion.div>
  );
}
