import React from 'react';
import { Globe, Activity, LogOut, User } from 'lucide-react';

export default function Navbar({ athlete, onLogout, lang, setLang, t }) {
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
              SAI TalentAI
            </h2>
            <span className="badge badge-cyan" style={{ fontSize: '0.6rem' }}>SIH 25073</span>
          </div>
          <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            {t.tagline}
          </p>
        </div>
      </div>

      {/* Right side — athlete info + language + logout */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        {/* Athlete info (when logged in) */}
        {athlete && (
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
                {athlete.name}
              </div>
              <div className="mono" style={{ fontSize: '0.65rem', color: 'var(--primary)' }}>
                {athlete.athlete_id}
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
        {athlete && (
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
