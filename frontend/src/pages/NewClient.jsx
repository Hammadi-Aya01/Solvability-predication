// src/pages/NewClient.jsx
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { predictionService } from '../services/predictionService';
import PageHeader from '../components/common/PageHeader';
import RiskBadge  from '../components/common/RiskBadge';
import ScoreGauge from '../components/common/ScoreGauge';
import Btn        from '../components/common/Btn';
import { fmt }    from '../utils/formatters';
import { GOUVERNORATS, NATURE_CLIENTS } from '../utils/constants';
import toast from 'react-hot-toast';
import styles from './NewClient.module.css';

const INITIAL = {
  CODE_CLIENT:'',NB_FACTURES:0,TOTAL_MONTANT_TTC:0,TOTAL_MONTANT_REG:0,
  NB_REGLEMENTS:0,RETARD_PONDERE:0,NB_RETARDS:0,RETARD_MAX:0,
  ANCIENNETE_CLIENT:0,GOUVERNORAT:'',NATURE_CLIENT:'',nom:'',
};

const FIELDS = [
  { section: 'Identification', fields: [
    { key: 'CODE_CLIENT',    label: 'Code Client',     type: 'text',   required: true, placeholder: 'ex: CLI-001' },
    { key: 'nom',            label: 'Nom',             type: 'text',   placeholder: 'Nom du client' },
    { key: 'GOUVERNORAT',    label: 'Gouvernorat',     type: 'select', options: GOUVERNORATS },
    { key: 'NATURE_CLIENT',  label: 'Nature',          type: 'select', options: NATURE_CLIENTS },
    { key: 'ANCIENNETE_CLIENT', label: 'Ancienneté (mois)', type: 'number', min: 0, placeholder: '36' },
  ]},
  { section: 'Facturation', fields: [
    { key: 'NB_FACTURES',      label: 'Nb Factures',      type: 'number', min: 0 },
    { key: 'TOTAL_MONTANT_TTC',label: 'Total Facturé (TND)', type: 'number', min: 0 },
    { key: 'TOTAL_MONTANT_REG',label: 'Total Réglé (TND)',   type: 'number', min: 0 },
    { key: 'NB_REGLEMENTS',    label: 'Nb Règlements',    type: 'number', min: 0 },
  ]},
  { section: 'Retards', fields: [
    { key: 'RETARD_PONDERE', label: 'Retard Pondéré (jours)', type: 'number', min: 0 },
    { key: 'NB_RETARDS',     label: 'Nb Incidents Retard',    type: 'number', min: 0 },
    { key: 'RETARD_MAX',     label: 'Retard Maximum (jours)', type: 'number', min: 0 },
  ]},
];

export default function NewClient() {
  const [form,    setForm]    = useState(INITIAL);
  const [result,  setResult]  = useState(null);
  const [loading, setLoading] = useState(false);
  const [errors,  setErrors]  = useState({});

  const set = (k, v) => { setForm(f => ({ ...f, [k]: v })); setErrors(e => ({ ...e, [k]: '' })); };

  const validate = () => {
    const errs = {};
    if (!form.CODE_CLIENT.trim()) errs.CODE_CLIENT = 'Requis';
    if (form.NB_FACTURES <= 0)    errs.NB_FACTURES = 'Doit être > 0';
    return errs;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); toast.error('Vérifiez les champs requis'); return; }

    setLoading(true);
    try {
      const payload = { ...form, NB_FACTURES: Number(form.NB_FACTURES), TOTAL_MONTANT_TTC: Number(form.TOTAL_MONTANT_TTC), TOTAL_MONTANT_REG: Number(form.TOTAL_MONTANT_REG), NB_REGLEMENTS: Number(form.NB_REGLEMENTS), RETARD_PONDERE: Number(form.RETARD_PONDERE), NB_RETARDS: Number(form.NB_RETARDS), RETARD_MAX: Number(form.RETARD_MAX), ANCIENNETE_CLIENT: Number(form.ANCIENNETE_CLIENT) };
      const { data } = await predictionService.single(payload);
      setResult(data.prediction);
      toast.success('Analyse terminée !');
    } catch (err) {
      if (err.response?.status === 503) {
        // Demo result when no model loaded
        setResult({
          label: form.NB_RETARDS > 3 || form.RETARD_MAX > 30 ? 'NON-SOLVABLE' : 'SOLVABLE',
          risk_score: form.NB_RETARDS > 3 ? 72 : 28,
          risk_level: form.NB_RETARDS > 3 ? 'ÉLEVÉ' : 'FAIBLE',
          probability: form.NB_RETARDS > 3 ? 28 : 82,
          probability_risk: form.NB_RETARDS > 3 ? 72 : 18,
          ai_summary: 'Analyse basée sur les règles métier (aucun modèle ML actif). Uploadez un dataset pour activer le scoring ML.',
          top_factors: [
            { feature: 'NB_RETARDS', shap_value: 0.35, feature_value: form.NB_RETARDS, impact: 'positif' },
            { feature: 'RETARD_MAX', shap_value: 0.28, feature_value: form.RETARD_MAX, impact: 'positif' },
            { feature: 'TOTAL_MONTANT_REG', shap_value: -0.22, feature_value: form.TOTAL_MONTANT_REG, impact: 'negatif' },
          ],
        });
        toast('Résultat estimé — pas de modèle ML actif', { icon: '⚠️' });
      } else {
        toast.error(err.response?.data?.error || 'Erreur analyse');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => { setForm(INITIAL); setResult(null); setErrors({}); };

  return (
    <div className={styles.page}>
      <PageHeader
        title="Nouveau Client"
        subtitle="Analysez un client via formulaire manuel et obtenez un score de risque instantané"
      />
      <div className={styles.layout}>
        {/* Form */}
        <form onSubmit={handleSubmit} className={styles.formCard}>
          {FIELDS.map(section => (
            <div key={section.section} className={styles.section}>
              <h3 className={styles.sectionTitle}>{section.section}</h3>
              <div className={styles.fieldsGrid}>
                {section.fields.map(f => (
                  <div key={f.key} className={styles.field}>
                    <label className={styles.label}>
                      {f.label}
                      {f.required && <span className={styles.required}>*</span>}
                    </label>
                    {f.type === 'select' ? (
                      <select
                        className={`input-base ${errors[f.key] ? styles.inputError : ''}`}
                        value={form[f.key]}
                        onChange={e => set(f.key, e.target.value)}
                      >
                        <option value="">Choisir…</option>
                        {f.options.map(o => <option key={o} value={o}>{o}</option>)}
                      </select>
                    ) : (
                      <input
                        type={f.type}
                        min={f.min}
                        placeholder={f.placeholder}
                        className={`input-base ${errors[f.key] ? styles.inputError : ''}`}
                        value={form[f.key]}
                        onChange={e => set(f.key, f.type === 'number' ? Number(e.target.value) : e.target.value)}
                      />
                    )}
                    {errors[f.key] && <span className={styles.errorMsg}>{errors[f.key]}</span>}
                  </div>
                ))}
              </div>
            </div>
          ))}

          <div className={styles.formFooter}>
            <Btn type="button" variant="ghost" onClick={handleReset}>Réinitialiser</Btn>
            <Btn type="submit" variant="primary" size="lg" loading={loading}
              icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>}>
              Analyser le Client
            </Btn>
          </div>
        </form>

        {/* Results panel */}
        <div className={styles.resultsPanel}>
          <AnimatePresence mode="wait">
            {!result ? (
              <motion.div key="empty" className={styles.emptyResult} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className={styles.emptyIcon}>
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                  </svg>
                </div>
                <h3>Prêt à analyser</h3>
                <p>Remplissez le formulaire et cliquez sur "Analyser" pour obtenir le score de risque ML</p>
              </motion.div>
            ) : (
              <motion.div key="result" initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.4 }}>
                {/* Main score */}
                <div className={styles.scoreCard}>
                  <ScoreGauge score={result.risk_score} size={160} />
                  <div className={styles.scoreInfo}>
                    <div className={styles.scoreLabel} style={{ color: result.label === 'SOLVABLE' ? 'var(--green)' : 'var(--red)' }}>
                      {result.label}
                    </div>
                    <RiskBadge level={result.risk_level} />
                    <div className={styles.probRow}>
                      <div className={styles.probItem}>
                        <span className={styles.probVal} style={{ color: 'var(--green)' }}>{fmt.percent(result.probability)}</span>
                        <span className={styles.probLabel}>Solvabilité</span>
                      </div>
                      <div className={styles.probItem}>
                        <span className={styles.probVal} style={{ color: 'var(--red)' }}>{fmt.percent(result.probability_risk)}</span>
                        <span className={styles.probLabel}>Risque</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* AI Summary */}
                <div className={styles.aiBox}>
                  <div className={styles.aiHeader}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                    <span>Analyse IA</span>
                  </div>
                  <p className={styles.aiText}>{result.ai_summary}</p>
                </div>

                {/* SHAP factors */}
                {result.top_factors?.length > 0 && (
                  <div className={styles.shapBox}>
                    <h4 className={styles.shapTitle}>Facteurs de Risque Principaux</h4>
                    {result.top_factors.map((f, i) => (
                      <motion.div key={i} className={styles.shapRow}
                        initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.1 }}>
                        <div className={styles.shapLeft}>
                          <span className={styles.shapDir} style={{ color: f.impact === 'positif' ? 'var(--red)' : 'var(--green)' }}>
                            {f.impact === 'positif' ? '↑' : '↓'}
                          </span>
                          <span className={styles.shapName}>{f.feature.replace(/_/g,' ')}</span>
                        </div>
                        <div className={styles.shapRight}>
                          <span className={styles.shapFv}>{typeof f.feature_value === 'number' ? f.feature_value.toFixed(1) : f.feature_value}</span>
                          <div className={styles.shapBar}>
                            <div style={{ width: `${Math.abs(f.shap_value) / 0.5 * 100}%`, background: f.impact === 'positif' ? 'var(--red)' : 'var(--green)', height: '100%', borderRadius: 99 }} />
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                )}

                {/* Recommendations */}
                <div className={styles.recoBox}>
                  <h4 className={styles.recoTitle}>Recommandations</h4>
                  {result.risk_score >= 60 ? (
                    <ul className={styles.recoList}>
                      <li style={{ color: 'var(--red)' }}>⚠ Limiter ou suspendre le crédit</li>
                      <li style={{ color: 'var(--orange)' }}>📞 Relance téléphonique immédiate</li>
                      <li style={{ color: 'var(--orange)' }}>📋 Demander des garanties supplémentaires</li>
                    </ul>
                  ) : result.risk_score >= 30 ? (
                    <ul className={styles.recoList}>
                      <li style={{ color: 'var(--orange)' }}>👁 Suivi régulier conseillé</li>
                      <li style={{ color: 'var(--cyan)' }}>📊 Révision du plafond crédit dans 90j</li>
                    </ul>
                  ) : (
                    <ul className={styles.recoList}>
                      <li style={{ color: 'var(--green)' }}>✓ Profil faible risque — crédit accordé</li>
                      <li style={{ color: 'var(--green)' }}>✓ Possibilité d'augmenter le plafond</li>
                    </ul>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
