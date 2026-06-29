// src/pages/History.jsx
import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { dashboardService } from '../services/dashboardService';
import PageHeader from '../components/common/PageHeader';
import Spinner from '../components/common/Spinner';
import { fmt } from '../utils/formatters';
import styles from './History.module.css';

const ACTION_LABELS = {
  LOGIN: 'Connexion',
  LOGOUT: 'Déconnexion',
  CREATE_USER: 'Ajout utilisateur',
  UPDATE_USER: 'Modification utilisateur',
  DELETE_USER: 'Suppression utilisateur',
  UPLOAD_DATASET: 'Import dataset',
  TRAIN_MODEL: 'Entraînement modèle',
  MODEL_TRAINED: 'Modèle entraîné',
  CONSULT_CLIENT_PROFILE: 'Consultation profil client',
  CREATE_CLIENT: 'Ajout client',
  UPDATE_CLIENT: 'Modification client',
  DELETE_CLIENT: 'Suppression client',
};

const MOCK = [
  { id: 1, created_at: new Date().toISOString(), actor: 'Aya Admin', actor_role: 'ADMIN', action: 'LOGIN', description: "Aya Admin s'est authentifié." },
  { id: 2, created_at: new Date(Date.now() - 3600000).toISOString(), actor: 'Agent financier', actor_role: 'ANALYST', action: 'CONSULT_CLIENT_PROFILE', description: 'Agent financier a consulté le profil du client CLI-042.' },
];

export default function History() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    dashboardService.systemHistory(30)
      .then(r => setRows(r.data.data || []))
      .catch(() => setRows(MOCK))
      .finally(() => setLoading(false));
  }, []);

  const actions = Array.from(new Set(rows.map(r => r.action).filter(Boolean)));
  const filtered = filter ? rows.filter(r => r.action === filter) : rows;

  return (
    <div className={styles.page}>
      <PageHeader title="Historique système" subtitle="Actions effectuées par l'administrateur et le responsable financier" badge={`${rows.length} actions`} />

      <div className={styles.filterRow}>
        <button className={`${styles.filterTab} ${filter === '' ? styles.active : ''}`} onClick={() => setFilter('')}>Toutes <span className={styles.filterCount}>{rows.length}</span></button>
        {actions.map(a => (
          <button key={a} className={`${styles.filterTab} ${filter === a ? styles.active : ''}`} onClick={() => setFilter(a)}>
            {ACTION_LABELS[a] || a} <span className={styles.filterCount}>{rows.filter(r => r.action === a).length}</span>
          </button>
        ))}
      </div>

      <div className={styles.tableCard}>
        {loading ? (
          <div className={styles.loading}><Spinner /><span>Chargement…</span></div>
        ) : filtered.length === 0 ? (
          <div className={styles.empty}><p>Aucune action trouvée</p></div>
        ) : (
          <table className={styles.table}>
            <thead><tr><th>Date</th><th>Utilisateur</th><th>Rôle</th><th>Action</th><th>Description</th></tr></thead>
            <tbody>
              {filtered.map((h, i) => (
                <motion.tr key={h.id} className={styles.tr} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.02 }}>
                  <td style={{ fontSize: 13, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{fmt.datetime(h.created_at)}</td>
                  <td style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 600 }}>{h.actor || `Utilisateur #${h.user_id || '-'}`}</td>
                  <td><span className={styles.roleBadge}>{h.actor_role || '—'}</span></td>
                  <td><span className={styles.actionBadge}>{ACTION_LABELS[h.action] || h.action}</span></td>
                  <td style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{h.description || h.action}</td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
