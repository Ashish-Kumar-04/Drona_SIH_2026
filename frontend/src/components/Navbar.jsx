import React, { useState, useEffect } from 'react';
import { Globe, Activity, LogOut, User, WifiOff, UploadCloud } from 'lucide-react';
import { queueCount } from '../utils/offlineQueue';

export default function Navbar({ athlete, user, roleLabel, onLogout, lang, setLang, t }) {
  // Normalize whichever account is signed in (athlete or official) into {name, id}.
  const acct = user || (athlete ? { name: athlete.name, id: athlete.athlete_id } : null);

  // Live network + offline-queue status (only meaningful for athletes, but harmless otherwise).
  const [online, setOnline] = useState(typeof navigator === 'undefined' ? true : navigator.onLine);
  const [pending, setPending] = useState(0);

  useEffect(() => {
    const refresh = () => { queueCount().then(setPending).catch(() => { }); };
    const goOnline = () => { setOnline(true); refresh(); };
    const goOffline = () => setOnline(false);
    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    window.addEventListener('queue:changed', refresh);
    refresh();
    return () => {
      window.removeEventListener('online', goOnline);
      window.removeEventListener('offline', goOffline);
      window.removeEventListener('queue:changed', refresh);
    };
  }, []);

  const statusPill = {
    display: 'flex', alignItems: 'center', gap: '6px',
    padding: '6px 12px', borderRadius: 'var(--radius-pill)',
    fontSize: '0.72rem', fontWeight: 700, whiteSpace: 'nowrap'
  };

  return (
    <header style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '14px 24px',
      borderBottom: '1px solid var(--border-glass)',
      background: 'rgba(7, 10, 18, 0.88)',
      backdropFilter: 'blur(16px)',
      position: 'sticky',
      top: 0,
      zIndex: 100
    }}>
      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div style={{
          width: '40px', height: '40px', borderRadius: '12px',
          background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 0 18px rgba(0, 242, 254, 0.4)'
        }}>
          <Activity size={22} color="#070a12" strokeWidth={2.5} />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
              Drona-Sports Talent Assessment Platform
            </h2>

          </div>
          <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            {t.tagline}
          </p>
        </div>
      </div>

      {/* Right side — athlete info + language + logout */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        {/* Offline / pending-sync status */}
        {!online && (
          <span style={{
            ...statusPill,
            background: 'rgba(255, 176, 32, 0.14)',
            border: '1px solid rgba(255, 176, 32, 0.4)',
            color: '#ffb020'
          }} title="No network — assessments will be saved on this device">
            <WifiOff size={13} /> Offline
          </span>
        )}
        {pending > 0 && (
          <span style={{
            ...statusPill,
            background: 'rgba(0, 242, 254, 0.1)',
            border: '1px solid var(--border-glow)',
            color: 'var(--primary)'
          }} title="Assessments waiting to sync">
            <UploadCloud size={13} /> {pending} pending
          </span>
        )}

        {/* Account info (when logged in) */}
        {acct && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            padding: '6px 14px',
            background: 'rgba(255, 255, 255, 0.05)',
            borderRadius: 'var(--radius-pill)',
            border: '1px solid var(--border-glass)'
          }}>
            <div style={{
              width: '28px', height: '28px', borderRadius: '50%',
              background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <User size={14} color="#070a12" />
            </div>
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-main)', lineHeight: 1.2 }}>
                {acct.name}
              </div>
              <div className="mono" style={{ fontSize: '0.65rem', color: 'var(--primary)' }}>
                {roleLabel ? `${roleLabel} • ${acct.id}` : acct.id}
              </div>
            </div>
          </div>
        )}

        {/* Language */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '5px',
          background: 'rgba(255, 255, 255, 0.04)',
          border: '1px solid var(--border-glass)',
          borderRadius: 'var(--radius-md)',
          padding: '4px 8px'
        }}>
          <Globe size={14} color="var(--primary)" />
          <select value={lang} onChange={(e) => setLang(e.target.value)}
            style={{
              background: 'transparent', border: 'none', color: 'var(--text-main)',
              fontFamily: 'var(--font-display)', fontWeight: 600,
              fontSize: '0.8rem', cursor: 'pointer', outline: 'none'
            }}>
            <option value="en" style={{ background: '#090e1a' }}>EN</option>
            <option value="hi" style={{ background: '#090e1a' }}>हिं</option>
          </select>
        </div>

        {/* Logout */}
        {acct && (
          <button onClick={onLogout} className="btn btn-secondary"
            style={{ padding: '7px 14px', fontSize: '0.8rem', borderRadius: 'var(--radius-pill)' }}>
            <LogOut size={15} />
            Logout
          </button>
        )}
      </div>
    </header>
  );
}
