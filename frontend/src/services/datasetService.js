// src/services/datasetService.js
import api from './api';

export const datasetService = {
  list:     (params) => api.get('/datasets', { params }),
  get:      (id)     => api.get(`/datasets/${id}`),
  delete:   (id)     => api.delete(`/datasets/${id}`),
  status:   (id)     => api.get(`/datasets/${id}/status`),
  train:    (id, trials = 8) => api.post(`/datasets/${id}/train`, { n_trials: trials }),
  upload:   (file, onProgress) => {
    const fd = new FormData();
    fd.append('file', file);
    return api.post('/datasets/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => onProgress && onProgress(Math.round(e.loaded * 100 / e.total)),
    });
  },
};
