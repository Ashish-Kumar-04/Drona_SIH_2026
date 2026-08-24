import React from 'react';
import { AlertTriangle, ArrowUpRight, CheckCircle2, Lightbulb } from 'lucide-react';

/**
 * Shared corrective-feedback panel.
 *
 * Renders the backend `coaching` object — { summary, score_band, faults:[{issue,severity}],
 * improvements:[str], strengths:[str] } — so an athlete can see WHAT they did wrong and HOW
 * to improve, on every result surface (live HUD, manual entry, profile history).
 *
 * Body text (issues/tips) comes from the backend in English; only the section headers and
 * severity chips are translated via `t.coaching`.
 *
 * Props:
 *   coaching  the coaching dict (renders nothing if absent/empty)
 *   t         translations
 *   compact   dense single-column variant for tight rows (profile history)
 */

const SEVERITY = {
  high: { color: 'var(--accent-red)', bg: 'rgba(255, 56, 92, 0.12)', border: 'rgba(255, 56, 92, 0.35)' },
  medium: { color: 'var(--accent-amber)', bg: 'rgba(255, 176, 32, 0.12)', border: 'rgba(255, 176, 32, 0.35)' },
  low: { color: 'var(--text-muted)', bg: 'rgba(255, 255, 255, 0.04)', border: 'var(--border-glass)' },
};

export default function CoachingFeedback({ coaching, t, compact = false }) {
  if (!coaching) return null;

  const c = (t && t.coaching) || {};
  const faults = Array.isArray(coaching.faults) ? coaching.faults : [];
  const improvements = Array.isArray(coaching.improvements) ? coaching.improvements : [];
  const strengths = Array.isArray(coaching.strengths) ? coaching.strengths : [];

  // Nothing actionable to show.
  if (!faults.length && !improvements.length && !strengths.length && !coaching.summary) return null;

  const severityLabel = (sev) =>
    sev === 'high' ? (c.high || 'High')
      : sev === 'medium' ? (c.medium || 'Medium')
        : (c.low || 'Minor');

  const sectionTitleStyle = {
    display: 'flex', alignItems: 'center', gap: '6px',
    fontSize: compact ? '0.72rem' : '0.8rem', fontWeight: 700,
    marginBottom: '8px', letterSpacing: '0.01em'
  };
  const itemTextStyle = {
    fontSize: compact ? '0.74rem' : '0.82rem', lineHeight: 1.45, color: 'var(--text-main)'
  };

  return (
    <div style={{
      marginTop: compact ? '10px' : '18px',
      padding: compact ? '12px 14px' : '16px 18px',
      background: 'rgba(255, 255, 255, 0.02)',
      border: '1px solid var(--border-glass)',
      borderRadius: 'var(--radius-md)',
      textAlign: 'left'
    }}>
      {/* Header + summary */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: coaching.summary ? '6px' : '12px' }}>
        <Lightbulb size={compact ? 15 : 18} color="var(--accent-amber)" />
        <span style={{ fontSize: compact ? '0.82rem' : '0.95rem', fontWeight: 800 }}>
          {c.title || 'Coaching Feedback'}
        </span>
        {coaching.score_band && (
          <span className="badge badge-cyan" style={{ fontSize: '0.62rem', marginLeft: 'auto' }}>
            {coaching.score_band}
          </span>
        )}
      </div>
      {coaching.summary && (
        <p style={{ fontSize: compact ? '0.75rem' : '0.85rem', color: 'var(--text-muted)', margin: '0 0 12px 0', lineHeight: 1.45 }}>
          {coaching.summary}
        </p>
      )}

      {/* Faults — what went wrong (severity-colored) */}
      {faults.length > 0 && (
        <div style={{ marginBottom: (improvements.length || strengths.length) ? '14px' : 0 }}>
          <div style={{ ...sectionTitleStyle, color: 'var(--accent-red)' }}>
            <AlertTriangle size={compact ? 13 : 15} /> {c.faults || 'What to fix'}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {faults.map((f, i) => {
              const s = SEVERITY[f.severity] || SEVERITY.low;
              return (
                <div key={i} style={{
                  display: 'flex', alignItems: 'flex-start', gap: '8px',
                  padding: '8px 10px', background: s.bg,
                  border: `1px solid ${s.border}`, borderRadius: 'var(--radius-sm)'
                }}>
                  <span style={{
                    flexShrink: 0, fontSize: '0.58rem', fontWeight: 800, textTransform: 'uppercase',
                    letterSpacing: '0.04em', color: s.color, border: `1px solid ${s.border}`,
                    borderRadius: 'var(--radius-pill)', padding: '2px 7px', marginTop: '1px'
                  }}>
                    {severityLabel(f.severity)}
                  </span>
                  <span style={itemTextStyle}>{f.issue}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Improvements — how to fix it */}
      {improvements.length > 0 && (
        <div style={{ marginBottom: strengths.length ? '14px' : 0 }}>
          <div style={{ ...sectionTitleStyle, color: 'var(--primary)' }}>
            <ArrowUpRight size={compact ? 13 : 15} /> {c.improvements || 'How to improve'}
          </div>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {improvements.map((imp, i) => (
              <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                <ArrowUpRight size={compact ? 13 : 15} color="var(--primary)" style={{ flexShrink: 0, marginTop: '2px' }} />
                <span style={itemTextStyle}>{imp}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Strengths — what went well */}
      {strengths.length > 0 && (
        <div>
          <div style={{ ...sectionTitleStyle, color: 'var(--accent-green)' }}>
            <CheckCircle2 size={compact ? 13 : 15} /> {c.strengths || 'What you did well'}
          </div>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {strengths.map((s, i) => (
              <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                <CheckCircle2 size={compact ? 13 : 15} color="var(--accent-green)" style={{ flexShrink: 0, marginTop: '2px' }} />
                <span style={itemTextStyle}>{s}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
