import React from 'react';
import ReactDOM from 'react-dom/client';
import { registerSW } from 'virtual:pwa-register';
import App from './App.jsx';
import { api } from './utils/api';
import './index.css';

// Register the service worker (auto-updates in the background; no-op in dev builds).
registerSW({ immediate: true });

// Replay any offline-queued assessments on boot and whenever the network returns.
const flushOfflineQueue = () => { api.flushOfflineQueue().catch(() => {}); };
window.addEventListener('online', flushOfflineQueue);
flushOfflineQueue();

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
