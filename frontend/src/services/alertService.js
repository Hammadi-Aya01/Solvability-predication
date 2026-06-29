// src/services/alertService.js
import api from './api';

export const alertService = {
  list:    (params) => api.get('/clients', { params }),
  resolve: (id)     => api.post(`/clients/alerts/${id}/resolve`),
};
