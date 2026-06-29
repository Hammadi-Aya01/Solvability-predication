// src/utils/constants.js
export const API_BASE = process.env.REACT_APP_API_URL || '/api';

export const RISK_LEVELS = { FAIBLE: 'FAIBLE', MOYEN: 'MOYEN', ELEVE: 'ÉLEVÉ' };

export const ALERT_SEVERITY = {
  CRITICAL: { label: 'Critique',  color: 'var(--red)',    bg: 'var(--red-dim)' },
  HIGH:     { label: 'Élevé',    color: 'var(--orange)', bg: 'var(--orange-dim)' },
  MEDIUM:   { label: 'Moyen',    color: 'var(--cyan)',   bg: 'var(--cyan-dim)' },
  LOW:      { label: 'Faible',   color: 'var(--green)',  bg: 'var(--green-dim)' },
};

export const ALERT_TYPES = {
  RISQUE_TRES_ELEVE:       'Risque Très Élevé',
  RISQUE_ELEVE:            'Risque Élevé',
  RETARD_CRITIQUE:         'Retard Critique',
  PLAFOND_BIENTOT_ATTEINT: 'Plafond Crédit',
  DRIFT_MODELE:            'Drift Modèle ML',
};

export const NAV_LINKS = [
  { path: '/',             label: 'Dashboard',      icon: 'grid' },
  { path: '/datasets',     label: 'Datasets',       icon: 'database', adminOnly: true },
  { path: '/clients',      label: 'Clients',        icon: 'users' },
  { path: '/history',      label: 'Historique',     icon: 'clock', adminOnly: true },
  { path: '/alerts',       label: 'Alertes',        icon: 'bell', adminOnly: true },
  { path: '/settings',     label: 'Paramètres',     icon: 'settings', adminOnly: true },
];

export const GOUVERNORATS = [
  'Tunis','Ariana','Ben Arous','Manouba','Nabeul','Zaghouan','Bizerte',
  'Béja','Jendouba','Kef','Siliana','Sousse','Monastir','Mahdia',
  'Sfax','Kairouan','Kasserine','Sidi Bouzid','Gabès','Medenine',
  'Tataouine','Gafsa','Tozeur','Kébili',
];

export const NATURE_CLIENTS = ['GMS','DETAIL','GROSSISTE','PHARMACIE','PARFUMERIE','AUTRE'];
