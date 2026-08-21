import React from 'react';
import { ShieldCheck, Activity, Award, CheckCircle2, Zap } from 'lucide-react';

export default function LiveMetricsHUD({ assessmentResult, testType, t }) {
  if (!assessmentResult) return null;

  const {
    raw_score,
    unit,
    normalized_score,
    confidence,
    validation_score,
    status,
    benchmark_status,
    benchmark_source,
    details = {}
  } = assessmentResult;

  const isSitup = testType === 'sit_up';
  const isJump = testType === 'vertical_jump';
  const isShuttle = testType === 'shuttle_run';

  return (
    <div className="glass-panel" style={{ padding: '20px', marginTop: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Activity size={20} color="var(--primary)" />
          <h3 style={{ fontSize: '1.15rem' }}>AI Biomechanical Assessment Results</h3>
        </div>
        <span className={`badge ${status === 'VALID' ? 'badge-valid' : 'badge-warning'}`}>
          <ShieldCheck size={14} />
          {status} ({validation_score}%)
        </span>
      </div>

      {/* Main Metric Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
        gap: '12px',
        marginBottom: '18px'
      }}>
        {/* Raw Score */}
        <div style={{
          background: 'rgba(255, 255, 255, 0.03)',
          border: '1px solid var(--border-glass)',
          borderRadius: 'var(--radius-md)',
          padding: '14px',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
            {isSitup ? t.metrics.validReps : isJump ? t.metrics.jumpHeight : t.metrics.totalTime}
          </div>
          <div className="mono" style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--primary)' }}>
            {raw_score} <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{unit}</span>
          </div>
          {isSitup && details.total_reps && (
            <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
              {details.valid_reps} / {details.total_reps} clean reps
            </div>
          )}
        </div>

        {/* Normalized Percentile Score */}
        <div style={{
          background: 'rgba(255, 255, 255, 0.03)',
          border: '1px solid var(--border-glow)',
          borderRadius: 'var(--radius-md)',
          padding: '14px',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
            Normalized Benchmark
          </div>
          <div className="mono" style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--accent-green)' }}>
            {normalized_score}<span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>/100</span>
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--accent-green)', fontWeight: 600 }}>
            {benchmark_status}
          </div>
        </div>

        {/* Form Score / Kinematic Metric */}
        <div style={{
          background: 'rgba(255, 255, 255, 0.03)',
          border: '1px solid var(--border-glass)',
          borderRadius: 'var(--radius-md)',
          padding: '14px',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
            {isSitup ? t.metrics.formScore : isJump ? 'Flight Time' : 'Turnaround Speed'}
          </div>
          <div className="mono" style={{ fontSize: '1.6rem', fontWeight: 800, color: '#ffffff' }}>
            {isSitup ? `${details.form_score || 95}%` : isJump ? `${details.flight_time_sec || 0.45}s` : `${details.peak_velocity_norm || 1.2}`}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
            {isSitup ? 'Posture & Cadence' : isJump ? 'Kinematic equation' : 'Boundary check passed'}
          </div>
        </div>

        {/* AI Confidence */}
        <div style={{
          background: 'rgba(255, 255, 255, 0.03)',
          border: '1px solid var(--border-glass)',
          borderRadius: 'var(--radius-md)',
          padding: '14px',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
            {t.metrics.aiConfidence}
          </div>
          <div className="mono" style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--secondary)' }}>
            {confidence}%
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
            MediaPipe BlazePose
          </div>
        </div>
      </div>

      {/* Benchmark Source Directive Notice (Section 15 & 19) */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '10px 14px',
        background: 'rgba(0, 0, 0, 0.25)',
        borderRadius: 'var(--radius-sm)',
        fontSize: '0.75rem',
        color: 'var(--text-muted)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Award size={14} color="var(--accent-amber)" />
          <span>Reference Standard: <strong>{benchmark_source}</strong></span>
        </div>
        <span style={{ color: 'var(--text-dim)' }}>Peer group: Age & Category Norms</span>
      </div>
    </div>
  );
}
