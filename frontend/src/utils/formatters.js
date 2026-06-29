// src/utils/formatters.js

export const fmt = {
  currency: (n, currency = 'TND') =>
    `${Number(n || 0).toLocaleString('fr-TN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })} ${currency}`,

  number: (n) => Number(n || 0).toLocaleString('fr-TN'),

  percent: (n, decimals = 1) => `${Number(n || 0).toFixed(decimals)}%`,

  date: (d) => {
    if (!d) return '—';
    return new Date(d).toLocaleDateString('fr-TN', { day: '2-digit', month: 'short', year: 'numeric' });
  },

  datetime: (d) => {
    if (!d) return '—';
    return new Date(d).toLocaleString('fr-TN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
  },

  relativeTime: (d) => {
    if (!d) return '—';
    const diff = Date.now() - new Date(d).getTime();
    const mins  = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days  = Math.floor(diff / 86400000);
    if (mins < 1)   return 'À l\'instant';
    if (mins < 60)  return `Il y a ${mins}min`;
    if (hours < 24) return `Il y a ${hours}h`;
    if (days < 7)   return `Il y a ${days}j`;
    return fmt.date(d);
  },

  score: (n) => Math.round(Number(n || 0)),

  fileSize: (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  },
};

export const getRiskColor = (level) => {
  if (!level) return 'var(--text-muted)';
  const l = level.toUpperCase();
  if (l === 'FAIBLE')  return 'var(--green)';
  if (l === 'MOYEN')   return 'var(--orange)';
  if (l === 'ÉLEVÉ' || l === 'ELEVE') return 'var(--red)';
  return 'var(--text-muted)';
};

export const getRiskBg = (level) => {
  if (!level) return 'var(--bg-elevated)';
  const l = level.toUpperCase();
  if (l === 'FAIBLE')  return 'var(--green-dim)';
  if (l === 'MOYEN')   return 'var(--orange-dim)';
  if (l === 'ÉLEVÉ' || l === 'ELEVE') return 'var(--red-dim)';
  return 'var(--bg-elevated)';
};

export const getScoreColor = (score) => {
  if (score <= 30) return 'var(--green)';
  if (score <= 60) return 'var(--orange)';
  return 'var(--red)';
};

export const truncate = (str, n = 30) =>
  str && str.length > n ? str.slice(0, n) + '…' : (str || '—');
