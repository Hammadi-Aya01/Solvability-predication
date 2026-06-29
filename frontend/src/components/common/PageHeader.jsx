// src/components/common/PageHeader.jsx
import React from 'react';
import styles from './PageHeader.module.css';

export default function PageHeader({ title, subtitle, actions, badge }) {
  return (
    <div className={styles.header}>
      <div>
        <div className={styles.titleRow}>
          <h1 className={styles.title}>{title}</h1>
          {badge && <span className={styles.badge}>{badge}</span>}
        </div>
        {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
      </div>
      {actions && <div className={styles.actions}>{actions}</div>}
    </div>
  );
}
