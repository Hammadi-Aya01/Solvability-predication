// src/App.js
import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from './context/AuthContext';
import AppRoutes from './routes/AppRoutes';
import './styles/global.css';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: 'var(--bg-elevated)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-strong)',
              borderRadius: '10px',
              fontSize: '13px',
              fontFamily: 'var(--font-body)',
              boxShadow: 'var(--shadow-lg)',
            },
            success: {
              iconTheme: { primary: 'var(--green)', secondary: 'var(--bg-base)' },
            },
            error: {
              iconTheme: { primary: 'var(--red)', secondary: 'var(--bg-base)' },
            },
          }}
        />
      </AuthProvider>
    </BrowserRouter>
  );
}
