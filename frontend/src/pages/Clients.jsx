// src/pages/Clients.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';
import { clientService } from '../services/clientService';
import PageHeader from '../components/common/PageHeader';
import Btn        from '../components/common/Btn';
import Spinner    from '../components/common/Spinner';
import { fmt }    from '../utils/formatters';
import { useDebounce } from '../hooks/useDebounce';
import styles from './Clients.module.css';

const MOCK_CLIENTS = Array.from({ length: 20 }, (_, i) => ({
  id: i + 1,
  code_client: `CLI-${String(i + 1).padStart(3, '0')}`,
  nom: ['Bazar Médina','SuperMarché Sfax','Beauty Sousse','Parfum Palace','Cosmétic Star','GMS Tunis','Detail Shop','Grossiste Nord','Pharmacie Sud','Style Boutique','Beauté Ariana','Shop Bizerte','Market Nabeul','Espace Sfax','Cosmo Monastir','Brio Mahdia','Lux Gabès','Trend Médenine','Beautex Kef','Natura Béja'][i],
  score_actuel: Math.round(10 + Math.random() * 90),
  risk_level: ['FAIBLE','MOYEN','ÉLEVÉ'][Math.floor(Math.random() * 3)],
  solvabilite: Math.random() > 0.35 ? 'SOLVABLE' : 'NON-SOLVABLE',
}));

function solvabilityOf(c) {
  if (c.solvabilite) return c.solvabilite;
  if (c.risk_level === 'ÉLEVÉ') return 'NON-SOLVABLE';
  if (c.risk_level === 'FAIBLE' || c.risk_level === 'MOYEN') return 'SOLVABLE';
  return 'INCONNU';
}

function scoreColor(score) {
  if (score > 60) return 'var(--red)';
  if (score > 30) return 'var(--orange)';
  return 'var(--green)';
}

export default function Clients() {
  const [clients, setClients] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [topMode, setTopMode] = useState(false);
  const [exporting, setExporting] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const debouncedSearch = useDebounce(search, 400);
  const PER_PAGE = 20;

  const load = useCallback(() => {
    setLoading(true);
    const req = topMode
      ? clientService.topRisk(PER_PAGE)
      : clientService.list({ q: debouncedSearch, page, per_page: PER_PAGE, sort_by: 'score_actuel', sort_dir: 'desc' });

    req.then(r => {
      const rows = r.data.clients || [];
      setClients(rows);
      setTotal(r.data.total ?? rows.length ?? 0);
    }).catch(() => {
      let rows = [...MOCK_CLIENTS];
      if (debouncedSearch) {
        const q = debouncedSearch.toLowerCase();
        rows = rows.filter(c => c.nom?.toLowerCase().includes(q) || c.code_client?.toLowerCase().includes(q));
      }
      rows.sort((a, b) => (b.score_actuel || 0) - (a.score_actuel || 0));
      if (topMode) rows = rows.slice(0, 10);
      setClients(rows.slice((page - 1) * PER_PAGE, page * PER_PAGE));
      setTotal(rows.length);
    }).finally(() => setLoading(false));
  }, [debouncedSearch, page, topMode]);

  useEffect(() => {
    const view = searchParams.get('view');
    const risk = searchParams.get('risk_level');
    if (view === 'top' || risk === 'ÉLEVÉ') setTopMode(true);
  }, [searchParams]);

  useEffect(() => { setPage(1); }, [debouncedSearch, topMode]);
  useEffect(() => { load(); }, [load]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await clientService.exportExcel();
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'clients_solvai.xlsx';
      a.click();
      toast.success('Export Excel téléchargé');
    } catch { toast.error('Export échoué'); }
    finally { setExporting(false); }
  };

  const pages = Math.ceil(total / PER_PAGE);

  return (
    <div className={styles.page}>
      <PageHeader
        title="Clients"
        subtitle={topMode ? 'Top clients classés par score de risque' : 'Liste des clients avec solvabilité et score de risque'}
        badge={`${fmt.number(total)} clients`}
        actions={
          <>
            <Btn variant={topMode ? 'primary' : 'secondary'} size="sm" onClick={() => setTopMode(v => !v)}>
              {topMode ? 'Liste complète' : 'Top Client'}
            </Btn>
            <Btn variant="ghost" size="sm" loading={exporting} onClick={handleExport}>Exporter</Btn>
          </>
        }
      />

      <div className={styles.filters}>
        <div className={styles.searchBox}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <input className={styles.searchInput} placeholder="Rechercher par nom ou code client…" value={search} onChange={e => setSearch(e.target.value)} />
          {search && <button className={styles.clearBtn} onClick={() => setSearch('')}>×</button>}
        </div>
      </div>

      <div className={styles.tableCard}>
        {loading ? (
          <div className={styles.loadingRow}><Spinner /><span>Chargement des clients…</span></div>
        ) : clients.length === 0 ? (
          <div className={styles.empty}><p>Aucun client trouvé</p></div>
        ) : (
          <>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Client</th>
                  <th>Solvabilité</th>
                  <th>Score de risque</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {clients.map((c, i) => {
                  const solv = solvabilityOf(c);
                  const score = Number(c.score_risque ?? c.score_actuel ?? 0);
                  const color = scoreColor(score);
                  return (
                    <motion.tr key={c.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }} className={styles.tr} onClick={() => navigate(`/clients/${c.id}`)}>
                      <td>
                        <div className={styles.clientCell}>
                          <div className={styles.avatar} style={{ background: `${color}22`, color, borderColor: color }}>
                            {(c.nom || c.code_client || '?')?.[0]?.toUpperCase()}
                          </div>
                          <div>
                            <div className={styles.clientName}>{c.nom || '—'}</div>
                            <div className={styles.clientCode}>{c.code_client}</div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className={`${styles.solvBadge} ${solv === 'SOLVABLE' ? styles.solvOk : solv === 'NON-SOLVABLE' ? styles.solvKo : styles.solvUnknown}`}>
                          {solv}
                        </span>
                      </td>
                      <td>
                        <div className={styles.scoreCell}>
                          <span className={styles.scoreNum} style={{ color }}>{Math.round(score)}</span>
                          <div className={styles.scoreBar}><div style={{ width: `${Math.min(score, 100)}%`, background: color, height: '100%', borderRadius: 99 }} /></div>
                        </div>
                      </td>
                      <td onClick={e => e.stopPropagation()}>
                        <button className={styles.actionBtn} onClick={() => navigate(`/clients/${c.id}`)}>Voir profil</button>
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
            {!topMode && pages > 1 && (
              <div className={styles.pagination}>
                <span className={styles.paginInfo}>Page {page} sur {pages} — {fmt.number(total)} résultats</span>
                <div className={styles.paginBtns}>
                  <button className={styles.paginBtn} disabled={page === 1} onClick={() => setPage(p => p - 1)}>← Précédent</button>
                  <button className={styles.paginBtn} disabled={page === pages} onClick={() => setPage(p => p + 1)}>Suivant →</button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
