// src/pages/ClientProfile.jsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { clientService } from '../services/clientService';
import PageHeader from '../components/common/PageHeader';
import RiskBadge  from '../components/common/RiskBadge';
import ScoreGauge from '../components/common/ScoreGauge';
import Btn        from '../components/common/Btn';
import Spinner    from '../components/common/Spinner';
import { fmt, getRiskColor } from '../utils/formatters';
import toast from 'react-hot-toast';
import styles from './ClientProfile.module.css';

const MOCK_PROFILE = {
  client: { id: 1, code_client: 'CLI-042', nom: 'Bazar Médina', email: 'contact@bazarmedina.tn', telephone: '+216 71 234 567', gouvernorat: 'Tunis', nature_client: 'GMS', statut: 'ACTIF', score_actuel: 78, risk_level: 'ÉLEVÉ', total_impaye: 84200, credit_utilise: 42000, plafond_credit: 50000, anciennete: 36, derniere_analyse: new Date(Date.now() - 2 * 86400000).toISOString() },
  score_history: Array.from({ length: 12 }, (_, i) => ({ predicted_at: new Date(Date.now() - (11 - i) * 7 * 86400000).toISOString(), risk_score: Math.round(50 + Math.sin(i * 0.6) * 20 + Math.random() * 8), risk_level: 'MOYEN' })),
  payment_stats: { total_regle: 218000, avg_delai: 18, nb_retards: 7, total_factures: 302200, total_impaye: 84200, nb_impayes: 3, taux_recouvrement: 72.1 },
  commercial_behavior: { profil: 'Client à risque élevé', recommandation: 'Limiter les facilités de paiement et suivre les retards.', ratio_paiement: 0.72, nb_factures: 5, nb_paiements: 3, montant_moy_facture: 60440, retard_moyen: 18, total_achats: 302200, total_paiements: 218000, total_retards: 7 },
  recent_payments: [
    { id: 1, montant: 12000, mode: 'VIREMENT', date: new Date(Date.now() - 5 * 86400000).toISOString(), delai: 12 },
    { id: 2, montant: 8500,  mode: 'CHÈQUE',   date: new Date(Date.now() - 18 * 86400000).toISOString(), delai: 0 },
    { id: 3, montant: 15000, mode: 'VIREMENT', date: new Date(Date.now() - 32 * 86400000).toISOString(), delai: 25 },
  ],
  recent_invoices: [
    { id: 1, numero_facture: 'FAC-2026-0042', montant_facture: 18000, montant_regle: 12000, reste_a_payer: 6000, date_facture: new Date(Date.now() - 10 * 86400000).toISOString(), statut: 'PARTIELLEMENT_PAYEE' },
    { id: 2, numero_facture: 'FAC-2026-0031', montant_facture: 22000, montant_regle: 22000, reste_a_payer: 0, date_facture: new Date(Date.now() - 25 * 86400000).toISOString(), statut: 'PAYEE' },
    { id: 3, numero_facture: 'FAC-2026-0018', montant_facture: 15000, montant_regle: 0, reste_a_payer: 15000, date_facture: new Date(Date.now() - 45 * 86400000).toISOString(), statut: 'IMPAYEE' },
  ],
  active_alerts: [
    { id: 1, type: 'RISQUE_TRES_ELEVE', severity: 'CRITICAL', message: 'Score de risque très élevé : 78/100', created_at: new Date(Date.now() - 2 * 86400000).toISOString() },
    { id: 2, type: 'RETARD_CRITIQUE', severity: 'HIGH', message: 'Retard maximum supérieur à 60 jours', created_at: new Date(Date.now() - 5 * 86400000).toISOString() },
  ],
  last_predictions: [{ label: 'NON-SOLVABLE', risk_score: 78, risk_level: 'ÉLEVÉ', ai_summary: 'Ce client présente un profil de risque élevé (score 78/100). Facteurs aggravants principaux : retard pondéré, taux de retard, total impayé. Une vérification approfondie et une relance proactive sont recommandées.', shap_factors: [{ feature: 'RETARD_PONDERE', shap_value: 0.42, feature_value: 28, impact: 'positif' }, { feature: 'TAUX_RETARD', shap_value: 0.31, feature_value: 0.7, impact: 'positif' }, { feature: 'RATIO_PAIEMENT', shap_value: -0.18, feature_value: 0.72, impact: 'negatif' }, { feature: 'ANCIENNETE_CLIENT', shap_value: -0.12, feature_value: 36, impact: 'negatif' }, { feature: 'TOTAL_IMPAYE', shap_value: 0.28, feature_value: 84200, impact: 'positif' }] }],
  timeline: [],
};

const INVOICE_STATUS = { PAYEE: { label: 'Payée', color: 'var(--green)' }, EN_ATTENTE: { label: 'En attente', color: 'var(--orange)' }, PARTIELLEMENT_PAYEE: { label: 'Partielle', color: 'var(--orange)' }, IMPAYEE: { label: 'Impayée', color: 'var(--red)' }, EN_RETARD: { label: 'En retard', color: 'var(--red)' } };

export default function ClientProfile() {
  const { id }    = useParams();
  const navigate  = useNavigate();
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab,     setTab]     = useState('overview');
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    clientService.profile(id)
      .then(r => setData(r.data))
      .catch(() => setData(MOCK_PROFILE))
      .finally(() => setLoading(false));
  }, [id]);

  const handlePdf = async () => {
    setDownloading(true);
    try {
      const res = await clientService.reportPdf(id);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a'); a.href = url; a.download = `rapport_${id}.pdf`; a.click();
    } catch { toast.error('PDF indisponible'); }
    finally { setDownloading(false); }
  };

  if (loading) return <div className={styles.loading}><Spinner size={36} /><span>Chargement profil…</span></div>;
  if (!data) return <div className={styles.loading}><span>Client introuvable</span></div>;

  const { client, score_history, payment_stats, commercial_behavior, recent_payments, active_alerts, last_predictions } = data;
  const hasValue = (v) => v !== null && v !== undefined && v !== '' && v !== '—' && v !== 'null' && v !== 'undefined';
  const pred = last_predictions?.[0];
  const creditPct = Math.min((client.credit_utilise / client.plafond_credit) * 100, 100);

  return (
    <div className={styles.page}>
      <PageHeader
        title={client.nom || client.code_client}
        subtitle={`${client.code_client} · ${client.gouvernorat} · ${client.nature_client}`}
        actions={
          <>
            <Btn variant="ghost" size="sm" onClick={() => navigate('/clients')}>← Retour</Btn>
            <Btn variant="secondary" size="sm" loading={downloading} onClick={handlePdf}
              icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>}>
              Rapport PDF
            </Btn>
            <Btn variant="primary" size="sm" onClick={() => navigate('/new-client')}>Nouvelle Analyse</Btn>
          </>
        }
      />

      {/* Alerts banner */}
      {active_alerts?.length > 0 && (
        <motion.div className={styles.alertBanner} initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          <span>{active_alerts.length} alerte(s) active(s) — {active_alerts[0]?.message}</span>
        </motion.div>
      )}

      {/* Top row: Score + Info + Credit */}
      <div className={styles.topRow}>
        {/* Score card */}
        <div className={styles.scoreCard}>
          <div className={styles.cardLabel}>Score de Risque</div>
          <ScoreGauge score={client.score_actuel} size={160} />
          <RiskBadge level={client.risk_level} />
          <div className={styles.solvLabel} style={{ color: pred?.label === 'SOLVABLE' ? 'var(--green)' : 'var(--red)' }}>
            {pred?.label || '—'}
          </div>
        </div>

        {/* Client info */}
        <div className={styles.infoCard}>
          <div className={styles.cardLabel}>Informations Client</div>
          <div className={styles.infoGrid}>
            {[
              ['Nom', client.nom], ['Code', client.code_client],
              ['Email', client.email], ['Téléphone', client.telephone],
              ['Gouvernorat', client.gouvernorat], ['Nature', client.nature_client],
              ['Ancienneté', `${client.anciennete} mois`], ['Statut', client.statut],
              ['Dernière analyse', fmt.relativeTime(client.derniere_analyse)],
            ].filter(([, v]) => hasValue(v)).map(([k, v]) => (
              <div key={k} className={styles.infoRow}>
                <span className={styles.infoKey}>{k}</span>
                <span className={styles.infoVal}>{v}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Credit */}
        <div className={styles.creditCard}>
          <div className={styles.cardLabel}>Crédit & Paiements</div>
          <div className={styles.creditStats}>
            <div className={styles.creditStat}>
              <span className={styles.creditStatVal}>{fmt.currency(client.plafond_credit)}</span>
              <span className={styles.creditStatLabel}>Plafond Crédit</span>
            </div>
            <div className={styles.creditStat}>
              <span className={styles.creditStatVal} style={{ color: 'var(--cyan)' }}>{fmt.currency(client.credit_utilise)}</span>
              <span className={styles.creditStatLabel}>Utilisé</span>
            </div>
            <div className={styles.creditStat}>
              <span className={styles.creditStatVal} style={{ color: 'var(--red)' }}>{fmt.currency(client.total_impaye)}</span>
              <span className={styles.creditStatLabel}>Impayé</span>
            </div>
          </div>
          <div className={styles.creditBarWrap}>
            <div className={styles.creditBarLabel}>
              <span>Utilisation crédit</span>
              <span style={{ color: creditPct > 80 ? 'var(--red)' : 'var(--text-secondary)' }}>{fmt.percent(creditPct)}</span>
            </div>
            <div className={styles.creditBarBg}>
              <motion.div className={styles.creditBarFill}
                initial={{ width: 0 }}
                animate={{ width: `${creditPct}%` }}
                transition={{ duration: 1, delay: 0.3 }}
                style={{ background: creditPct > 80 ? 'var(--red)' : creditPct > 60 ? 'var(--orange)' : 'var(--cyan)' }}
              />
            </div>
          </div>
          {payment_stats && (
            <div className={styles.payStatsGrid}>
              {[
                ['Total réglé', fmt.currency(payment_stats.total_regle)],
                ['Délai moyen', `${payment_stats.avg_delai} jours`],
                ['Nb retards', payment_stats.nb_retards],
                ['Recouvrement', fmt.percent(payment_stats.taux_recouvrement)],
              ].map(([k, v]) => (
                <div key={k} className={styles.payStat}>
                  <span className={styles.payStatVal}>{v}</span>
                  <span className={styles.payStatLabel}>{k}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className={styles.tabs}>
        {[['overview','Vue d\'ensemble'],['payments','Historique paiement'],['commercial','Comportement commercial'],['ai','Analyse IA']].map(([t, label]) => (
          <button key={t} className={`${styles.tab} ${tab === t ? styles.tabActive : ''}`} onClick={() => setTab(t)}>
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className={styles.tabContent}>
        {tab === 'overview' && (
          <div className={styles.overviewGrid}>
            {/* Score history chart */}
            <div className={styles.chartCard}>
              <h3 className={styles.chartTitle}>Évolution du Score de Risque</h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={score_history} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="predicted_at" tickFormatter={d => fmt.date(d).split(' ')[0]} tick={{ fill: '#7a8baa', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fill: '#7a8baa', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip formatter={(v) => [`${v}/100`, 'Score']} labelFormatter={fmt.date} contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                  <Line type="monotone" dataKey="risk_score" stroke={getRiskColor(client.risk_level)} strokeWidth={2.5} dot={{ r: 3, fill: getRiskColor(client.risk_level) }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            {/* Alerts */}
            <div className={styles.alertsCard}>
              <h3 className={styles.chartTitle}>Alertes Actives</h3>
              {active_alerts?.length === 0 ? <p className={styles.noAlerts}>Aucune alerte active ✓</p> : (
                active_alerts?.map(a => (
                  <div key={a.id} className={styles.alertItem} style={{ borderColor: a.severity === 'CRITICAL' ? 'var(--red)' : 'var(--orange)' }}>
                    <div className={styles.alertDot} style={{ background: a.severity === 'CRITICAL' ? 'var(--red)' : 'var(--orange)' }} />
                    <div>
                      <div className={styles.alertMsg}>{a.message}</div>
                      <div className={styles.alertDate}>{fmt.relativeTime(a.created_at)}</div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {tab === 'payments' && (
          <div className={styles.tableCard}>
            <table className={styles.miniTable}>
              <thead><tr><th>Montant</th><th>Mode</th><th>Date</th><th>Délai (j)</th></tr></thead>
              <tbody>
                {recent_payments?.map(p => (
                  <tr key={p.id}>
                    <td style={{ fontWeight: 600, color: 'var(--green)' }}>{fmt.currency(p.montant)}</td>
                    <td><span className={styles.modeBadge}>{p.mode}</span></td>
                    <td style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{fmt.date(p.date)}</td>
                    <td><span style={{ color: p.delai > 0 ? 'var(--red)' : 'var(--green)', fontWeight: 600 }}>{p.delai > 0 ? `+${p.delai}j` : '✓'}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}


        {tab === 'commercial' && (
          <div className={styles.overviewGrid}>
            <div className={styles.chartCard}>
              <h3 className={styles.chartTitle}>Comportement commercial</h3>
              <div className={styles.infoGrid}>
                {[
                  ['Profil', commercial_behavior?.profil],
                  ['Total achats', fmt.currency(commercial_behavior?.total_achats)],
                  ['Total paiements', fmt.currency(commercial_behavior?.total_paiements)],
                  ['Ratio paiement', fmt.percent((commercial_behavior?.ratio_paiement || 0) * 100)],
                  ['Nombre de factures', commercial_behavior?.nb_factures],
                  ['Nombre de paiements', commercial_behavior?.nb_paiements],
                  ['Retards', commercial_behavior?.total_retards],
                  ['Retard moyen', `${commercial_behavior?.retard_moyen ?? 0} jours`],
                  ['Montant moyen facture', fmt.currency(commercial_behavior?.montant_moy_facture)],
                ].filter(([, v]) => hasValue(v)).map(([k, v]) => (
                  <div key={k} className={styles.infoRow}>
                    <span className={styles.infoKey}>{k}</span>
                    <span className={styles.infoVal}>{v}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className={styles.alertsCard}>
              <h3 className={styles.chartTitle}>Recommandation</h3>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                {commercial_behavior?.recommandation || 'Aucune recommandation disponible.'}
              </p>
            </div>
          </div>
        )}


        {tab === 'ai' && pred && (
          <div className={styles.aiPanel}>
            <div className={styles.aiSummaryCard}>
              <div className={styles.aiIcon}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
              </div>
              <div>
                <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>Analyse IA</h3>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7 }}>{pred.ai_summary}</p>
              </div>
            </div>
            <div className={styles.shapCard}>
              <h3 className={styles.chartTitle}>Facteurs SHAP — Impact sur le Score</h3>
              <div className={styles.shapList}>
                {pred.shap_factors?.map((f, i) => (
                  <div key={i} className={styles.shapRow}>
                    <span className={styles.shapFeature}>{f.feature.replace(/_/g,' ')}</span>
                    <div className={styles.shapBarWrap}>
                      <motion.div className={styles.shapBar}
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.abs(f.shap_value) / 0.45 * 100}%` }}
                        transition={{ delay: i * 0.08 }}
                        style={{ background: f.impact === 'positif' ? 'var(--red)' : 'var(--green)' }}
                      />
                    </div>
                    <span className={styles.shapVal} style={{ color: f.impact === 'positif' ? 'var(--red)' : 'var(--green)' }}>
                      {f.impact === 'positif' ? '↑' : '↓'} {Math.abs(f.shap_value).toFixed(3)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
