import React from 'react';
import { CheckCircle2, AlertTriangle, Video, Eye, Sun, Compass } from 'lucide-react';

export default function CameraGuidance({ onReady, testTitle, t }) {
  return (
    <div className="glass-panel-glow" style={{ padding: '24px', textAlign: 'center', marginBottom: '20px' }}>
      <div style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '54px',
        height: '54px',
        borderRadius: '50%',
        background: 'rgba(0, 242, 254, 0.15)',
        color: 'var(--primary)',
        marginBottom: '12px'
      }}>
        <Video size={28} />
      </div>

      <h3 style={{ fontSize: '1.25rem', marginBottom: '6px' }}>
        {t.guidance.title}
      </h3>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '20px' }}>
        AI system verifies testing environment before allowing assessment recording.
      </p>

      {/* Pre-Check List */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
        gap: '12px',
        marginBottom: '24px',
        textAlign: 'left'
      }}>
        <div style={{
          background: 'rgba(255, 255, 255, 0.03)',
          border: '1px solid rgba(0, 245, 160, 0.3)',
          borderRadius: 'var(--radius-md)',
          padding: '12px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-green)', marginBottom: '4px' }}>
            <CheckCircle2 size={16} />
            <span style={{ fontSize: '0.8rem', fontWeight: 700 }}>{t.guidance.fullBody}</span>
          </div>
          <p style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Head to ankles visible in camera frame</p>
        </div>

        <div style={{
          background: 'rgba(255, 255, 255, 0.03)',
          border: '1px solid rgba(0, 245, 160, 0.3)',
          borderRadius: 'var(--radius-md)',
          padding: '12px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-green)', marginBottom: '4px' }}>
            <CheckCircle2 size={16} />
            <span style={{ fontSize: '0.8rem', fontWeight: 700 }}>{t.guidance.stability}</span>
          </div>
          <p style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Tripod or steady surface recommended</p>
        </div>

        <div style={{
          background: 'rgba(255, 255, 255, 0.03)',
          border: '1px solid rgba(0, 245, 160, 0.3)',
          borderRadius: 'var(--radius-md)',
          padding: '12px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-green)', marginBottom: '4px' }}>
            <CheckCircle2 size={16} />
            <span style={{ fontSize: '0.8rem', fontWeight: 700 }}>{t.guidance.lighting}</span>
          </div>
          <p style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Adequate front-facing daylight or indoor light</p>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '14px' }}>
        <span className="badge badge-valid" style={{ padding: '6px 14px', fontSize: '0.85rem' }}>
          ✓ {t.guidance.ready}
        </span>
        <button onClick={onReady} className="btn btn-primary btn-pill">
          {t.guidance.start} &rarr;
        </button>
      </div>
    </div>
  );
}
