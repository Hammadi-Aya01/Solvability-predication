// src/pages/Datasets.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  BarChart, Bar, Legend,
} from 'recharts';
import { datasetService } from '../services/datasetService';
import { dashboardService } from '../services/dashboardService';
import PageHeader from '../components/common/PageHeader';
import Btn        from '../components/common/Btn';
import Spinner    from '../components/common/Spinner';
import { fmt } from '../utils/formatters';
import styles from './Datasets.module.css';

const STATUS_CONFIG = {
  UPLOADED:   { label: 'Uploadé',    color: 'var(--cyan)',   bg: 'var(--cyan-dim)' },
  VALIDATING: { label: 'Validation', color: 'var(--orange)', bg: 'var(--orange-dim)' },
  PROCESSING: { label: 'Entraîn.',   color: 'var(--purple)', bg: 'var(--purple-dim)' },
  COMPLETED:  { label: 'Terminé',    color: 'var(--green)',  bg: 'var(--green-dim)' },
  FAILED:     { label: 'Échoué',     color: 'var(--red)',    bg: 'var(--red-dim)' },
  INVALID:    { label: 'Invalide',   color: 'var(--red)',    bg: 'var(--red-dim)' },
};

const MOCK_DATASETS = [
  { id: 1, filename: 'clients_mai_2026.xlsx', nb_rows: 847, nb_cols: 18, status: 'COMPLETED', training_progress: 100, file_size: 204800, created_at: new Date(Date.now() - 5 * 86400000).toISOString(), validation_report: { is_valid: true, warnings: [] } },
];

const RISK_COLORS = ['#00e096', '#ffaa2c', '#ff4d6a'];

function ChartCard({ title, subtitle, children }) {
  return (
    <div className={styles.resultChartCard}>
      <div className={styles.resultChartHead}>
        <h3>{title}</h3>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className={styles.tooltip}>
      {label && <div className={styles.tooltipLabel}>{label}</div>}
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color, fontSize: 12 }}>
          {p.name}: <strong>{p.value}</strong>
        </div>
      ))}
    </div>
  );
};

function normaliseModels(models = []) {
  return models.map(m => ({
    name: m.name || m.model_name || `Modèle ${m.id || ''}`,
    accuracy: Number(m.metrics?.accuracy ?? m.accuracy ?? 0),
    precision: Number(m.metrics?.precision ?? m.precision ?? 0),
    recall: Number(m.metrics?.recall ?? m.recall ?? 0),
    f1: Number(m.metrics?.f1 ?? m.metrics?.f1_score ?? m.f1_score ?? 0),
    roc_auc: Number(m.metrics?.roc_auc ?? m.roc_auc ?? 0),
  }));
}

export default function Datasets() {
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [training, setTraining] = useState({});
  const [resultOpen, setResultOpen] = useState(false);
  const [resultLoading, setResultLoading] = useState(false);
  const [resultData, setResultData] = useState(null);

  const load = useCallback(() => {
    datasetService.list()
      .then(r => setDatasets(r.data.datasets || []))
      .catch(() => setDatasets(MOCK_DATASETS))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const processing = datasets.filter(d => d.status === 'PROCESSING');
    if (!processing.length) return;
    const interval = setInterval(() => {
      processing.forEach(d => {
        datasetService.status(d.id)
          .then(r => {
            const updated = r.data.dataset;
            setDatasets(prev => prev.map(x => x.id === d.id ? updated : x));
            if (updated.status !== 'PROCESSING') {
              if (updated.status === 'COMPLETED') toast.success(`✓ Entraînement terminé pour ${updated.filename}`);
              if (updated.status === 'FAILED') toast.error(`Entraînement échoué: ${updated.error_message}`);
            }
          })
          .catch(() => {});
      });
    }, 3000);
    return () => clearInterval(interval);
  }, [datasets]);

  const onDrop = useCallback(async (files) => {
    const file = files[0];
    if (!file) return;
    setUploading(true);
    setProgress(0);
    try {
      const { data } = await datasetService.upload(file, setProgress);
      toast.success(`Dataset "${file.name}" uploadé avec succès`);
      setDatasets(prev => [data.dataset, ...prev]);
      if (data.validation?.warnings?.length) data.validation.warnings.forEach(w => toast(w, { icon: '⚠️' }));
    } catch (err) {
      toast.error(err.response?.data?.error || 'Upload échoué');
    } finally {
      setUploading(false);
      setProgress(0);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'], 'application/vnd.ms-excel': ['.xls'] },
    multiple: false,
    disabled: uploading,
  });

  const handleTrain = async (dataset) => {
    setTraining(t => ({ ...t, [dataset.id]: true }));
    try {
      await datasetService.train(dataset.id, 8);
      toast.success('Entraînement démarré en arrière-plan');
      setDatasets(prev => prev.map(d => d.id === dataset.id ? { ...d, status: 'PROCESSING', training_progress: 0 } : d));
    } catch (err) {
      toast.error(err.response?.data?.error || err.response?.data?.message || err.message || 'Impossible de démarrer');
    } finally {
      setTraining(t => ({ ...t, [dataset.id]: false }));
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Supprimer ce dataset ?')) return;
    try {
      await datasetService.delete(id);
      setDatasets(prev => prev.filter(d => d.id !== id));
      toast.success('Dataset supprimé');
      if (resultData?.dataset?.id === id) setResultData(null);
    } catch (err) {
      toast.error(err.response?.data?.error || 'Erreur suppression');
    }
  };

  const handleViewResults = async (dataset) => {
    setResultOpen(true);
    setResultLoading(true);
    try {
      const [detail, overview] = await Promise.all([
        datasetService.get(dataset.id),
        dashboardService.overview(30).catch(() => ({ data: {} })),
      ]);
      const models = detail.data.models || [];
      const model = models[0] || null;
      setResultData({ dataset: detail.data.dataset || dataset, models, model, overview: overview.data || {} });
    } catch (err) {
      toast.error('Impossible de charger les résultats');
    } finally {
      setResultLoading(false);
    }
  };

  const selectedModel = resultData?.model;
  const comparison = normaliseModels(selectedModel?.all_models_results || resultData?.models || []);
  const bestMetrics = selectedModel?.metrics || {};
  const featureImportance = Object.entries(selectedModel?.feature_importances || {})
    .map(([feature, importance]) => ({ feature: feature.replace(/_/g, ' '), importance: Number(importance || 0) }))
    .sort((a, b) => b.importance - a.importance)
    .slice(0, 12);
  const scoreEvo = resultData?.overview?.score_evolution || [];
  const predHist = resultData?.overview?.pred_history || [];
  const rd = resultData?.overview?.kpis?.risk_distribution || {};
  const pieData = [
    { name: 'Faible', value: rd.FAIBLE || 0 },
    { name: 'Moyen', value: rd.MOYEN || 0 },
    { name: 'Élevé', value: rd['ÉLEVÉ'] || 0 },
  ];

  return (
    <div className={styles.page}>
      <PageHeader title="Datasets" subtitle="Uploadez, entraînez et visualisez les résultats ML" badge={`${datasets.length} datasets`} />

      <motion.div {...getRootProps()} className={`${styles.dropzone} ${isDragActive ? styles.dragActive : ''} ${uploading ? styles.uploading : ''}`} whileHover={{ borderColor: 'var(--cyan)' }} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        <input {...getInputProps()} />
        {uploading ? (
          <div className={styles.uploadProgress}>
            <Spinner size={32} />
            <p>Upload en cours… {progress}%</p>
            <div className={styles.progressBar}><motion.div className={styles.progressFill} animate={{ width: `${progress}%` }} /></div>
          </div>
        ) : (
          <div className={styles.dropContent}>
            <div className={styles.dropIcon}><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg></div>
            <h3>{isDragActive ? 'Déposez ici…' : 'Glissez-déposez votre dataset'}</h3>
            <p>CSV, Excel (.xlsx, .xls) — max 50 MB</p>
            <Btn variant="secondary" size="sm" style={{ marginTop: 8 }}>Parcourir les fichiers</Btn>
          </div>
        )}
      </motion.div>

      <div className={styles.tableCard}>
        <div className={styles.tableHeader}>
          <h2 className={styles.tableTitle}>Historique des Datasets</h2>
          <Btn variant="ghost" size="sm" onClick={load}>Actualiser</Btn>
        </div>

        {loading ? (
          <div className={styles.loadingRow}><Spinner /><span>Chargement…</span></div>
        ) : datasets.length === 0 ? (
          <div className={styles.empty}><p>Aucun dataset uploadé</p></div>
        ) : (
          <table className={styles.table}>
            <thead><tr><th>Fichier</th><th>Taille</th><th>Lignes</th><th>Statut</th><th>Progression</th><th>Date</th><th>Actions</th></tr></thead>
            <tbody>
              {datasets.map((d, i) => {
                const sc = STATUS_CONFIG[d.status] || STATUS_CONFIG.UPLOADED;
                return (
                  <motion.tr key={d.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.04 }} className={styles.tr}>
                    <td><div className={styles.fileName}><div className={styles.fileIcon}>{d.filename?.endsWith('.csv') ? 'CSV' : 'XLS'}</div><div><div className={styles.fileNameText}>{d.filename}</div>{d.validation_report?.errors?.length > 0 && <div className={styles.fileError}>{d.validation_report.errors[0]}</div>}</div></div></td>
                    <td><span className={styles.cell}>{fmt.fileSize(d.file_size || 0)}</span></td>
                    <td><span className={styles.cell}>{fmt.number(d.nb_rows || 0)}</span></td>
                    <td><span className={styles.statusBadge} style={{ color: sc.color, background: sc.bg }}>{d.status === 'PROCESSING' && <span className={styles.pulse} />}{sc.label}</span></td>
                    <td>{d.status === 'PROCESSING' ? <div className={styles.progressMini}><div><div className={styles.progressMiniFill} style={{ width: `${d.training_progress || 0}%` }} /></div><span>{d.training_progress || 0}%</span></div> : d.status === 'COMPLETED' ? <span style={{ color: 'var(--green)', fontSize: 12 }}>✓ 100%</span> : '—'}</td>
                    <td><span className={styles.cell}>{fmt.relativeTime(d.created_at)}</span></td>
                    <td><div className={styles.actions}>
                      {(d.status === 'UPLOADED' || d.status === 'FAILED' || d.status === 'INVALID') && <Btn variant="primary" size="sm" loading={training[d.id]} onClick={() => handleTrain(d)}>Entraîner</Btn>}
                      {d.status === 'COMPLETED' && <Btn variant="secondary" size="sm" onClick={() => handleViewResults(d)}>Visualiser les résultats</Btn>}
                      {d.status === 'PROCESSING' && <div className={styles.processing}><Spinner size={14} /><span>En cours…</span></div>}
                      <Btn variant="danger" size="sm" onClick={() => handleDelete(d.id)} disabled={d.status === 'PROCESSING'} />
                    </div></td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {resultOpen && (
        <div className={styles.resultsPanel}>
          <div className={styles.resultsHeader}>
            <div>
              <h2>Visualiser les résultats</h2>
              <p>{resultData?.dataset?.filename || 'Résultats du dernier entraînement'}</p>
            </div>
            <button className={styles.closeResults} onClick={() => setResultOpen(false)}>×</button>
          </div>

          {resultLoading ? (
            <div className={styles.loadingRow}><Spinner /><span>Chargement des résultats…</span></div>
          ) : !selectedModel ? (
            <div className={styles.empty}><p>Aucun résultat d'entraînement disponible pour ce dataset.</p></div>
          ) : (
            <>
              <div className={styles.metricGrid}>
                <div><span>Accuracy</span><strong>{fmt.percent((bestMetrics.accuracy || 0) * 100)}</strong></div>
                <div><span>Précision</span><strong>{fmt.percent((bestMetrics.precision || 0) * 100)}</strong></div>
                <div><span>Recall</span><strong>{fmt.percent((bestMetrics.recall || 0) * 100)}</strong></div>
                <div><span>F1-score</span><strong>{fmt.percent((bestMetrics.f1_score || bestMetrics.f1 || 0) * 100)}</strong></div>
                <div><span>ROC-AUC</span><strong>{fmt.percent((bestMetrics.roc_auc || 0) * 100)}</strong></div>
              </div>

              <div className={styles.resultsGrid}>
                {comparison.length > 0 && <ChartCard title="Comparaison des modèles" subtitle="Métriques obtenues pendant l'entraînement">
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={comparison} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="name" tick={{ fill: '#7a8baa', fontSize: 11 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill: '#7a8baa', fontSize: 11 }} axisLine={false} tickLine={false} domain={[0, 1]} />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend />
                      <Bar dataKey="accuracy" name="Accuracy" fill="#00d4ff" radius={[3,3,0,0]} />
                      <Bar dataKey="precision" name="Précision" fill="#00e096" radius={[3,3,0,0]} />
                      <Bar dataKey="recall" name="Recall" fill="#ffaa2c" radius={[3,3,0,0]} />
                      <Bar dataKey="f1" name="F1-score" fill="#9b5cff" radius={[3,3,0,0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartCard>}

                {featureImportance.length > 0 && <ChartCard title="Importance des variables" subtitle="Variables utilisées par le modèle">
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={featureImportance} layout="vertical" margin={{ top: 5, right: 20, left: 80, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis type="number" tick={{ fill: '#7a8baa', fontSize: 11 }} axisLine={false} tickLine={false} />
                      <YAxis type="category" dataKey="feature" tick={{ fill: '#7a8baa', fontSize: 10 }} axisLine={false} tickLine={false} width={120} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="importance" name="Importance" fill="#00d4ff" radius={[0,4,4,0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartCard>}

                {scoreEvo.length > 0 && <ChartCard title="Évolution du risque" subtitle="Graphique déplacé depuis le dashboard">
                  <ResponsiveContainer width="100%" height={240}>
                    <AreaChart data={scoreEvo} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                      <defs><linearGradient id="scoreGradResult" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#00d4ff" stopOpacity="0.3"/><stop offset="95%" stopColor="#00d4ff" stopOpacity="0"/></linearGradient></defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="day" tick={{ fill: '#7a8baa', fontSize: 11 }} axisLine={false} tickLine={false} interval={4} />
                      <YAxis tick={{ fill: '#7a8baa', fontSize: 11 }} axisLine={false} tickLine={false} domain={[0,100]} />
                      <Tooltip content={<CustomTooltip />} />
                      <Area type="monotone" dataKey="avg_score" name="Score" stroke="#00d4ff" strokeWidth={2.5} fill="url(#scoreGradResult)" dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </ChartCard>}

                {pieData.some(x => x.value > 0) && <ChartCard title="Distribution des risques" subtitle="Portefeuille après entraînement">
                  <ResponsiveContainer width="100%" height={240}>
                    <PieChart><Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={92} paddingAngle={3} dataKey="value">{pieData.map((entry, i) => <Cell key={i} fill={RISK_COLORS[i]} />)}</Pie><Tooltip formatter={(v) => [fmt.number(v), 'Clients']} /></PieChart>
                  </ResponsiveContainer>
                </ChartCard>}

                {predHist.length > 0 && <ChartCard title="Historique des analyses" subtitle="Graphique déplacé depuis le dashboard">
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={predHist} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="day" tick={{ fill: '#7a8baa', fontSize: 11 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill: '#7a8baa', fontSize: 11 }} axisLine={false} tickLine={false} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="SOLVABLE" name="Solvable" fill="#00e096" radius={[3,3,0,0]} />
                      <Bar dataKey="NON-SOLVABLE" name="Non solvable" fill="#ff4d6a" radius={[3,3,0,0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartCard>}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
