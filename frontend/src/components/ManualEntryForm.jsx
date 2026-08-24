import React, { useState } from 'react';
import { Timer, Route, Ruler, MoveHorizontal, CheckCircle2, ShieldCheck, Award, AlertTriangle } from 'lucide-react';
import { api } from '../utils/api';
import { TEST_BY_ID, MANUAL_BOUNDS, formatTestName } from '../utils/tests';
import CoachingFeedback from './CoachingFeedback';

// Per-test accent + icon for the manual battery (speed / endurance / flexibility / leg power).
const TEST_UI = {
  sprint_50m:    { icon: Timer,          color: '#00f2fe' },
  endurance_run: { icon: Route,          color: '#9d4edd' },
  sit_and_reach: { icon: Ruler,          color: '#4facfe' },
  broad_jump:    { icon: MoveHorizontal, color: '#ffb800' },
};

const inputStyle = {
  width: '100%',
  padding: '12px 14px',
  borderRadius: 'var(--radius-md)',
  background: 'rgba(255, 255, 255, 0.05)',
  border: '1px solid var(--border-glass)',
  color: 'var(--text-main)',
  fontSize: '1rem',
  fontFamily: 'var(--font-body)',
  outline: 'none'
};

export default function ManualEntryForm({ athleteId, testType, onComplete, t }) {
  const meta = TEST_BY_ID[testType] || {};
  const bounds = MANUAL_BOUNDS[testType] || { min: -Infinity, max: Infinity };
  const ui = TEST_UI[testType] || { icon: Timer, color: 'var(--primary)' };
  const Icon = ui.icon;
  const m = t.manual;

  const [rawValue, setRawValue] = useState('');
  const [officiated, setOfficiated] = useState(false);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    const trimmed = String(rawValue).trim();
    if (trimmed === '') {
      setError(m.required);
      return;
    }
    const value = parseFloat(trimmed);
    if (Number.isNaN(value) || value < bounds.min || value > bounds.max) {
      setError(`${m.outOfRange} (${m.rangeHint}: ${bounds.min}–${bounds.max} ${meta.unit})`);
      return;
    }

    setSubmitting(true);
    try {
      const res = await api.submitManualEntry(
        athleteId, testType, value, officiated, notes.trim() || null
      );
      setResult(res);
    } catch (err) {
      setError(err.message || 'Submission failed.');
    } finally {
      setSubmitting(false);
    }
  };

  const resetForm = () => {
    setRawValue('');
    setOfficiated(false);
    setNotes('');
    setError(null);
    setResult(null);
  };

  // ─── Success state: show the scored result ───
  if (result) {
    const valid = String(result.status).toUpperCase() === 'VALID';
    return (
      <div className="glass-panel-glow" style={{ padding: '28px', maxWidth: '560px', margin: '0 auto' }}>
        <div style={{ textAlign: 'center', marginBottom: '20px' }}>
          <CheckCircle2 size={44} color="var(--accent-green)" style={{ marginBottom: '10px' }} />
          <h3 style={{ fontSize: '1.3rem', marginBottom: '4px' }}>{m.success}</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            {formatTestName(testType, t)} — {result.raw_score} {result.unit}
          </p>
        </div>

        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
          gap: '12px', marginBottom: '20px'
        }}>
          <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-glow)', borderRadius: 'var(--radius-md)', padding: '14px', textAlign: 'center' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Normalized Benchmark</div>
            <div className="mono" style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--accent-green)' }}>
              {Math.round(result.normalized_score)}<span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>/100</span>
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--accent-green)', fontWeight: 600 }}>{result.benchmark_status}</div>
          </div>
          <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-glass)', borderRadius: 'var(--radius-md)', padding: '14px', textAlign: 'center' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '4px' }}>{t.metrics.validationScore}</div>
            <div className="mono" style={{ fontSize: '1.6rem', fontWeight: 800, color: valid ? 'var(--accent-green)' : '#ffb020' }}>
              {Math.round(result.validation_score)}%
            </div>
            <div style={{ fontSize: '0.7rem', color: valid ? 'var(--accent-green)' : '#ffb020', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <ShieldCheck size={12} /> {result.status}
            </div>
          </div>
        </div>

        <div style={{
          display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'center',
          padding: '10px 14px', background: 'rgba(0,0,0,0.25)', borderRadius: 'var(--radius-sm)',
          fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '20px'
        }}>
          <Award size={13} color="var(--accent-amber)" />
          <span>Reference Standard: <strong>{result.benchmark_source}</strong></span>
        </div>

        {/* Corrective coaching — what to fix and how to improve */}
        <CoachingFeedback coaching={result.coaching || (result.details && result.details.coaching)} t={t} />

        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <button onClick={onComplete} className="btn btn-primary" style={{ flex: 1, minWidth: '160px', padding: '13px' }}>
            {m.viewProfile}
          </button>
          <button onClick={resetForm} className="btn btn-secondary" style={{ padding: '13px' }}>
            {m.another}
          </button>
        </div>
      </div>
    );
  }

  // ─── Entry form ───
  return (
    <form onSubmit={handleSubmit} className="glass-panel" style={{ padding: '28px', maxWidth: '560px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '20px' }}>
        <div style={{
          width: '52px', height: '52px', borderRadius: '14px',
          background: 'rgba(255, 255, 255, 0.04)', border: `1px solid ${ui.color}40`,
          display: 'flex', alignItems: 'center', justifyContent: 'center'
        }}>
          <Icon size={28} color={ui.color} />
        </div>
        <div>
          <h3 style={{ fontSize: '1.2rem', marginBottom: '2px' }}>{formatTestName(testType, t)}</h3>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {t.tests[meta.descKey] || m.subtitle}
          </p>
        </div>
      </div>

      <div style={{ marginBottom: '16px' }}>
        <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '6px', fontWeight: 600 }}>
          {m.resultLabel}
        </label>
        <div style={{ position: 'relative' }}>
          <input
            type="number"
            step="0.01"
            min={Number.isFinite(bounds.min) ? bounds.min : undefined}
            max={Number.isFinite(bounds.max) ? bounds.max : undefined}
            value={rawValue}
            onChange={(e) => setRawValue(e.target.value)}
            placeholder="0.00"
            autoFocus
            style={{ ...inputStyle, paddingRight: '58px' }}
          />
          <span style={{
            position: 'absolute', right: '14px', top: '50%', transform: 'translateY(-50%)',
            fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600, pointerEvents: 'none'
          }}>
            {meta.unit}
          </span>
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '5px' }}>
          {m.rangeHint}: {bounds.min}–{bounds.max} {meta.unit}
        </div>
      </div>

      <label style={{
        display: 'flex', alignItems: 'flex-start', gap: '10px', marginBottom: '16px',
        cursor: 'pointer', padding: '12px 14px', background: 'rgba(255,255,255,0.02)',
        border: '1px solid var(--border-glass)', borderRadius: 'var(--radius-md)'
      }}>
        <input
          type="checkbox"
          checked={officiated}
          onChange={(e) => setOfficiated(e.target.checked)}
          style={{ marginTop: '2px', width: '18px', height: '18px', accentColor: 'var(--primary)', cursor: 'pointer' }}
        />
        <span>
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main)' }}>{m.officiated}</span>
          <span style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '2px' }}>
            {m.officiatedHint}
          </span>
        </span>
      </label>

      <div style={{ marginBottom: '18px' }}>
        <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '6px', fontWeight: 600 }}>
          {m.notes}
        </label>
        <input
          type="text"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder={m.notesPlaceholder}
          style={inputStyle}
        />
      </div>

      {error && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '8px',
          padding: '11px 14px', background: 'rgba(255, 56, 92, 0.12)', color: 'var(--accent-red)',
          borderRadius: 'var(--radius-md)', marginBottom: '16px', fontSize: '0.82rem',
          border: '1px solid rgba(255, 56, 92, 0.3)'
        }}>
          <AlertTriangle size={16} /> {error}
        </div>
      )}

      <button type="submit" disabled={submitting} className="btn btn-primary"
        style={{ width: '100%', padding: '14px', fontSize: '0.95rem' }}>
        {submitting ? m.submitting : m.submit}
      </button>
    </form>
  );
}
