// src/components/common/Btn.jsx
import React from 'react';
import Spinner from './Spinner';
import styles from './Btn.module.css';

export default function Btn({
  children, variant = 'primary', size = 'md',
  loading, icon, onClick, type = 'button',
  style, disabled, className = ''
}) {
  return (
    <button
      type={type}
      className={`${styles.btn} ${styles[variant]} ${styles[size]} ${className}`}
      onClick={onClick}
      disabled={disabled || loading}
      style={style}
    >
      {loading ? <Spinner size={16} color="currentColor" /> : icon && <span className={styles.icon}>{icon}</span>}
      {children && <span>{children}</span>}
    </button>
  );
}
