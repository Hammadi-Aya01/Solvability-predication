// src/services/authService.js
import api from './api';

export const authService = {
  login:      (email, password) => api.post('/auth/login',    { email, password }),
  register:   (data)            => api.post('/auth/register', data),
  logout:     ()                => api.post('/auth/logout'),
  me:         ()                => api.get('/auth/me'),
  updateMe:   (data)            => api.put('/auth/me', data),
  changePassword: (data)       => api.put('/auth/me/password', data),
  getUsers:   ()                => api.get('/auth/users'),
  createUser: (data)            => api.post('/auth/users', data),
  updateUser: (id, data)        => api.put(`/auth/users/${id}`, data),
};
