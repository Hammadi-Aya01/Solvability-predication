// src/services/predictionService.js
import api from './api';

export const predictionService = {
  single:   (data)   => api.post('/predict/single', data),
  history:  (params) => api.get('/predict/history', { params }),
  get:      (id)     => api.get(`/predict/history/${id}`),
  ready:    ()       => api.get('/predict/ready'),
  bulk:     (file)   => {
    const fd = new FormData();
    fd.append('file', file);
    return api.post('/predict/bulk', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};
