// src/services/modelService.js
import api from './api';

export const modelService = {
  list:        ()    => api.get('/models'),
  active:      ()    => api.get('/models/active'),
  get:         (id)  => api.get(`/models/${id}`),
  activate:    (id)  => api.post(`/models/${id}/activate`),
  compare:     ()    => api.get('/models/compare'),
  status:      ()    => api.get('/models/status'),
  importances: (id)  => api.get(`/models/${id}/feature-importances`),
};
