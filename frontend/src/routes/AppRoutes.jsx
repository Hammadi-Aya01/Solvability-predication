// src/routes/AppRoutes.jsx
import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Spinner from '../components/common/Spinner';

import AppLayout      from '../layouts/AppLayout';
import Login          from '../pages/Login';
import Dashboard      from '../pages/Dashboard';
import Datasets       from '../pages/Datasets';
import Clients        from '../pages/Clients';
import ClientProfile  from '../pages/ClientProfile';
import History        from '../pages/History';
import Alerts         from '../pages/Alerts';
import Settings       from '../pages/Settings';

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center',
        justifyContent: 'center', flexDirection: 'column', gap: 16,
        color: 'var(--text-secondary)', fontSize: 14,
      }}>
        <Spinner size={36} />
        <span>Chargement…</span>
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;
  return children;
}


function isAdmin(user) {
  return String(user?.role || '').toUpperCase() === 'ADMIN';
}

function AdminRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (!isAdmin(user)) return <Navigate to="/" replace />;
  return children;
}

function PublicRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/" replace />;
  return children;
}

export default function AppRoutes() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={
        <PublicRoute><Login /></PublicRoute>
      } />

      {/* Protected — all wrapped in AppLayout */}
      <Route path="/" element={
        <ProtectedRoute><AppLayout /></ProtectedRoute>
      }>
        <Route index                  element={<Dashboard />} />
        <Route path="datasets"        element={<AdminRoute><Datasets /></AdminRoute>} />
        <Route path="clients"         element={<Clients />} />
        <Route path="clients/:id"     element={<ClientProfile />} />
        <Route path="history"         element={<AdminRoute><History /></AdminRoute>} />
        <Route path="alerts"          element={<AdminRoute><Alerts /></AdminRoute>} />
        <Route path="settings"        element={<Settings />} />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>

      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
