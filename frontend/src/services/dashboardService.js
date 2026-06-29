// src/services/dashboardService.js
import api from './api';

export const dashboardService = {
  overview:       (days = 30) => api.get(`/dashboard/overview?days=${days}`),
  kpis:           ()          => api.get('/dashboard/kpis'),
  scoreEvolution: (days = 30) => api.get(`/dashboard/score-evolution?days=${days}`),
  topRisk:        (limit = 10)=> api.get(`/dashboard/top-risk?limit=${limit}`),
  paymentModes:   ()          => api.get('/dashboard/payment-modes'),
  predHistory:    (days = 30) => api.get(`/dashboard/prediction-history?days=${days}`),
  gouvernorat:    ()          => api.get('/dashboard/gouvernorat-stats'),
  alertsSummary:  ()          => api.get('/dashboard/alerts/summary'),
  systemHistory:  (days = 30) => api.get(`/dashboard/historique-systeme?days=${days}`),
};
