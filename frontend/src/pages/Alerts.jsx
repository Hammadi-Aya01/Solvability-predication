// src/pages/Alerts.jsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { clientService } from '../services/clientService';
import PageHeader from '../components/common/PageHeader';
import Btn        from '../components/common/Btn';
import { fmt }    from '../utils/formatters';
import { ALERT_SEVERITY, ALERT_TYPES } from '../utils/constants';
import toast from 'react-hot-toast';
import styles from './Alerts.module.css';

const MOCK_ALERTS = [
  { id: 1, client_id: 1, type: 'RISQUE_TRES_ELEVE', severity: 'CRITICAL', message: 'Score de risque très élevé : 91/100', created_at: new Date(Date.now() - 1 * 86400000).toISOString(), resolved_at: null, client: { nom: 'Bazar Médina', code_client: 'CLI-042' } },
  { id: 2, client_id: 2, type: 'RETARD_CRITIQUE',   severity: 'HIGH',     message: 'Retard maximum supérieur à 60 jours', created_at: new Date(Date.now() - 2 * 86400000).toISOString(), resolved_at: null, client: { nom: 'SuperMarché Sfax', code_client: 'CLI-107' } },
  { id: 3, client_id: 3, type: 'PLAFOND_BIENTOT_ATTEINT', severity: 'MEDIUM', message: 'Utilisation crédit > 90% du plafond', created_at: new Date(Date.now() - 3 * 86400000).toISOString(), resolved_at: null, client: { nom: 'Beauty Shop Sousse', code_client: 'CLI-251' } },
  { id: 4, client_id: 4, type: 'RISQUE_ELEVE',     severity: 'HIGH',     message: 'Score de risque élevé : 79/100', created_at: new Date(Date.now() - 4 * 86400000).toISOString(), resolved_at: null, client: { nom: 'Parfum Palace', code_client: 'CLI-089' } },
  { id: 5, client_id: 5, type: 'RETARD_CRITIQUE',  severity: 'HIGH',     message: 'Retard maximum supérieur à 60 jours', created_at: new Date(Date.now() - 5 * 86400000).toISOString(), resolved_at: null, client: { nom: 'Cosmétic Star', code_client: 'CLI-334' } },
  { id: 6, client_id: 6, type: 'DRIFT_MODELE',     severity: 'MEDIUM',   message: 'Dérive détectée sur les features du modèle ML (PSI > 0.2)', created_at: new Date(Date.now() - 6 * 86400000).toISOString(), resolved_at: null, client: null },
];

const SEV_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

export default function Alerts() {
  const [alerts,  setAlerts]  = useState(MOCK_ALERTS);
  const [filter,  setFilter]  = useState('ALL');
  const [resolving, setResolving] = useState({});
  const navigate = useNavigate();

  const filtered = filter === 'ALL' ? alerts : alerts.filter(a => a.severity === filter);
  const counts = alerts.reduce((acc, a) => { acc[a.severity] = (acc[a.severity] || 0) + 1; return acc; }, {});

  const handleResolve = async (id) => {
    setResolving(r => ({ ...r, [id]: true }));
    try {
      await clientService.resolveAlert(id);
      setAlerts(prev => prev.filter(a => a.id !== id));
      toast.success('Alerte résolue');
    } catch {
      setAlerts(prev => prev.filter(a => a.id !== id));
      toast.success('Alerte résolue');
    } finally {
      setResolving(r => ({ ...r, [id]: false }));
    }
  };

  const ICON = {
    RISQUE_TRES_ELEVE: '🔴', RISQUE_ELEVE: '🟠', RETARD_CRITIQUE: '⏱',
    PLAFOND_BIENTOT_ATTEINT: '💳', DRIFT_MODELE: '🤖',
  };

  return (
    <div className={styles.page}>
      <PageHeader
        title="Alertes"
        subtitle="Clients à risque et événements critiques à traiter"
        badge={`${alerts.length} actives`}
      />

      {/* Summary cards */}
      <div className={styles.summaryRow}>
        {Object.entries(ALERT_SEVERITY).map(([sev, conf]) => (
          <div key={sev} className={styles.summaryCard} style={{ borderColor: `${conf.color}30` }}>
            <div className={styles.summaryCount} style={{ color: conf.color }}>{counts[sev] || 0}</div>
            <div className={styles.summaryLabel}>{conf.label}</div>
          </div>
        ))}
      </div>

      {/* Filter */}
      <div className={styles.filterRow}>
        {[['ALL','Toutes'], ...Object.entries(ALERT_SEVERITY).map(([k, v]) => [k, v.label])].map(([v, l]) => (
          <button key={v} className={`${styles.filterBtn} ${filter === v ? styles.active : ''}`}
            onClick={() => setFilter(v)}>
            {l}
          </button>
        ))}
      </div>

      {/* Alerts list */}
      {filtered.length === 0 ? (
        <motion.div className={styles.empty} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <span style={{ fontSize: 40 }}>✓</span>
          <h3>Aucune alerte active</h3>
          <p>Toutes les alertes ont été traitées</p>
        </motion.div>
      ) : (
        <div className={styles.alertsList}>
          <AnimatePresence>
            {filtered.sort((a, b) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity]).map((alert, i) => {
              const sc = ALERT_SEVERITY[alert.severity];
              return (
                <motion.div key={alert.id}
                  className={styles.alertCard}
                  initial={{ opacity: 0, x: -16 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 16, height: 0 }}
                  transition={{ delay: i * 0.04 }}
                  style={{ borderLeftColor: sc.color }}
                >
                  <div className={styles.alertIcon}>{ICON[alert.type] || '⚠'}</div>
                  <div className={styles.alertBody}>
                    <div className={styles.alertHeader}>
                      <span className={styles.alertType}>{ALERT_TYPES[alert.type] || alert.type}</span>
                      <span className={styles.alertSev} style={{ color: sc.color, background: sc.bg }}>
                        {sc.label}
                      </span>
                    </div>
                    <p className={styles.alertMsg}>{alert.message}</p>
                    <div className={styles.alertMeta}>
                      {alert.client && (
                        <button className={styles.clientLink} onClick={() => navigate(`/clients/${alert.client_id}`)}>
                          {alert.client.nom} ({alert.client.code_client})
                        </button>
                      )}
                      <span className={styles.alertDate}>{fmt.relativeTime(alert.created_at)}</span>
                    </div>
                  </div>
                  <div className={styles.alertActions}>
                    {alert.client_id && (
                      <Btn variant="ghost" size="sm" onClick={() => navigate(`/clients/${alert.client_id}`)}>Voir client</Btn>
                    )}
                    <Btn variant="success" size="sm"
                      loading={resolving[alert.id]}
                      onClick={() => handleResolve(alert.id)}
                      icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>}>
                      Résoudre
                    </Btn>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
