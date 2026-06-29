// src/pages/Dashboard.jsx
import React, { useState, useEffect } from 'react';
import StatCard   from '../components/common/StatCard';
import PageHeader from '../components/common/PageHeader';
import Spinner    from '../components/common/Spinner';
import { dashboardService } from '../services/dashboardService';
import { fmt } from '../utils/formatters';
import styles from './Dashboard.module.css';

const MOCK = {
  kpis: {
    clients: { total: 847, actifs: 712, inactifs: 135, avg_score: 42 },
    risk_distribution: { FAIBLE: 423, MOYEN: 248, 'ÉLEVÉ': 176, INCONNU: 0 },
    financials: { total_impaye: 2840000, total_credit_utilise: 7200000 },
    activity: { predictions_this_month: 134, active_alerts: 23, critical_alerts: 7, relances_pending: 41 },
  },
};

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboardService.overview(30)
      .then(r => setData(r.data))
      .catch(() => setData({ kpis: MOCK.kpis }))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className={styles.loadingState}>
      <Spinner size={36} />
      <span>Chargement du dashboard…</span>
    </div>
  );

  const kpis = data?.kpis || MOCK.kpis;
  const rd = kpis.risk_distribution || {};
  const acts = kpis.activity || {};
  const fin = kpis.financials || {};
  const totalClients = Number(kpis.clients?.total || 0);

  const statCards = [
    {
      title: 'Total Clients',
      value: fmt.number(totalClients),
      sub: `${fmt.number(kpis.clients?.actifs || 0)} actifs`,
      color: 'var(--cyan)',
      icon: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>,
    },
    {
      title: 'Clients Solvables',
      value: fmt.number((rd.FAIBLE || 0) + (rd.MOYEN || 0)),
      sub: totalClients ? fmt.percent((((rd.FAIBLE || 0) + (rd.MOYEN || 0)) / totalClients) * 100) : '0%',
      color: 'var(--green)',
      icon: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>,
    },
    {
      title: 'Risque Élevé',
      value: fmt.number(rd['ÉLEVÉ'] || 0),
      sub: 'Clients à surveiller',
      color: 'var(--red)',
      icon: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>,
    },
    {
      title: 'Total Impayé',
      value: fmt.currency(fin.total_impaye || 0),
      sub: 'Toutes créances',
      color: 'var(--orange)',
      icon: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>,
    },
    {
      title: 'Analyses ce mois',
      value: fmt.number(acts.predictions_this_month || 0),
      sub: 'Prédictions ML',
      color: 'var(--purple)',
      icon: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>,
    },
    {
      title: 'Alertes Actives',
      value: fmt.number(acts.active_alerts || 0),
      sub: `${fmt.number(acts.critical_alerts || 0)} critiques`,
      color: 'var(--red)',
      icon: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>,
    },
  ];

  return (
    <div className={styles.page}>
      <PageHeader
        title="Dashboard"
        subtitle="Vue d'ensemble de votre portefeuille crédit"
        badge="Live"
      />

      <div className={styles.statsGrid}>
        {statCards.map((card, i) => (
          <StatCard key={card.title} {...card} delay={i * 0.06} />
        ))}
      </div>
    </div>
  );
}
