// src/components/layout/Navbar.jsx
import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../../context/AuthContext';
import { NAV_LINKS } from '../../utils/constants';
import styles from './Navbar.module.css';

const ICONS = {
  grid: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>,
  database: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>,
  users: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/></svg>,
  clock: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>,
  bell: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>,
  settings: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>,
};

const isAdminRole = (role) => String(role || '').toUpperCase() === 'ADMIN';
const roleLabel = (role) => {
  const r = String(role || '').toUpperCase();
  if (r === 'ADMIN') return 'ADMIN';
  return 'AGENT';
};

export default function Navbar() {
  const { user, company, logout } = useAuth();
  const navigate = useNavigate();
  const [showUser, setShowUser] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const initials = user
    ? `${user.prenom?.[0] || ''}${user.nom?.[0] || ''}`.toUpperCase() || user.email?.[0]?.toUpperCase()
    : '?';
  const isAdmin = isAdminRole(user?.role);
  const visibleLinks = NAV_LINKS.filter(link => !link.adminOnly || isAdmin);

  return (
    <header className={styles.navbar}>
      <button className={styles.brand} onClick={() => navigate('/')}>
        <span className={styles.logoMark}>
          <svg width="24" height="24" viewBox="0 0 32 32" fill="none">
            <path d="M4 16 L16 4 L28 16 L16 28 Z" fill="currentColor" opacity="0.18"/>
            <path d="M8 16 L16 8 L24 16 L16 24 Z" fill="currentColor" opacity="0.45"/>
            <circle cx="16" cy="16" r="4" fill="currentColor"/>
          </svg>
        </span>
        <span className={styles.brandText}>Solv<span>AI</span></span>
      </button>

      <nav className={styles.topNav}>
        {visibleLinks.map((link) => (
          <NavLink
            key={link.path}
            to={link.path}
            end={link.path === '/'}
            className={({ isActive }) => `${styles.navItem} ${isActive ? styles.active : ''}`}
          >
            <span className={styles.navIcon}>{ICONS[link.icon]}</span>
            <span>{link.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className={styles.right}>
        <div className={styles.statusPill}>
          <span className={styles.statusDot} />
          <span>Modèle actif</span>
        </div>

        {isAdmin && (
          <button className={styles.iconBtn} onClick={() => navigate('/alerts')}>
            {ICONS.bell}
            <span className={styles.notifBadge}>3</span>
          </button>
        )}

        <div className={styles.userArea}>
          <button className={styles.userBtn} onClick={() => setShowUser(!showUser)}>
            <div className={styles.avatar}>{initials}</div>
            <div className={styles.userInfo}>
              <span className={styles.userName}>{user?.prenom || user?.email || 'User'}</span>
              <span className={styles.userRole}>{roleLabel(user?.role)}</span>
            </div>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>

          <AnimatePresence>
            {showUser && (
              <motion.div
                className={styles.dropdown}
                initial={{ opacity: 0, y: -8, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -8, scale: 0.96 }}
                transition={{ duration: 0.15 }}
              >
                <div className={styles.dropdownHeader}>
                  <div className={styles.avatarLg}>{initials}</div>
                  <div>
                    <div className={styles.dropName}>{user?.prenom} {user?.nom}</div>
                    <div className={styles.dropEmail}>{user?.email}</div>
                    <div className={styles.dropCompany}>{company?.name}</div>
                  </div>
                </div>
                <div className={styles.dropDivider} />
                <button className={styles.dropItem} onClick={() => { navigate('/settings'); setShowUser(false); }}>Mon profil</button>
                <button className={styles.dropItem} onClick={handleLogout} style={{ color: 'var(--red)' }}>Déconnexion</button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {showUser && <div className={styles.overlay} onClick={() => setShowUser(false)} />}
    </header>
  );
}
