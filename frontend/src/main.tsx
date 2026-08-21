import React from 'react';
import ReactDOM from 'react-dom/client';
import { AuthProvider } from './app/AuthContext';
import { TimeSettingsProvider } from './app/TimeSettingsContext';
import { AppRouter } from './app/Router';
import './styles/global.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthProvider>
      <TimeSettingsProvider>
        <AppRouter />
      </TimeSettingsProvider>
    </AuthProvider>
  </React.StrictMode>
);
