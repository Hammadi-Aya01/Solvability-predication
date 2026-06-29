// src/services/clientService.js
import api from './api';

export const clientService = {
  list:       (params) => api.get('/clients', { params }),
  topRisk:    (limit = 20) => api.get('/clients/top-risk', { params: { limit } }),
  get:        (id)     => api.get(`/clients/${id}`),
  create:     (data)   => api.post('/clients', data),
  update:     (id, d)  => api.put(`/clients/${id}`, d),
  delete:     (id)     => api.delete(`/clients/${id}`),
  profile:    (id)     => api.get(`/clients/${id}/profile`),
  alerts:     (id)     => api.get(`/clients/${id}/alerts`),
  relances:   (id)     => api.get(`/clients/${id}/relances`),
  createRelance: (id, d) => api.post(`/clients/${id}/relances`, d),
  setCreditLimit: (id, p) => api.put(`/clients/${id}/credit-limit`, { plafond_credit: p }),
  resolveAlert: (alertId) => api.post(`/clients/alerts/${alertId}/resolve`),
  exportExcel: () => api.get('/clients/export/excel', { responseType: 'blob' }),
  exportCsv:   () => api.get('/clients/export/csv',   { responseType: 'blob' }),
  reportPdf:   (id) => api.get(`/clients/${id}/report/pdf`, { responseType: 'blob' }),
};
