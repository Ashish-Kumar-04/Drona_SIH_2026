import React from 'react';
import { User, MapPin, Zap, Award, Calendar, Ruler, Weight, Download } from 'lucide-react';
import { api } from '../utils/api';
import { formatTestName } from '../utils/tests';
import CoachingFeedback from './CoachingFeedback';

function getBenchmarkBadge(score) {
  if (score >= 80) return { text: 'Excellent', className: 'badge badge-valid' };
  if (score >= 60) return { text: 'Above Average', className: 'badge badge-valid' };
  if (score >= 40) return { text: 'Average', className: 'badge badge-warning' };
  if (score > 0) return { text: 'Below Average', className: 'badge badge-danger' };
  return { text: 'No Data', className: 'badge badge-cyan' };
}

function formatDate(timestamp) {
  if (!timestamp) return '';
  const d = new Date(timestamp);
  return d.toLocaleDateString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
}

export default function AthleteProfileView({ profile, onTakeNewTest, t }) {
  if (!profile || !profile.athlete) {
    return (
      <div className="glass-panel" style={{ padding: '40px', textAlign: 'center' }}>
        <p style={{ color: 'var(--text-muted)' }}>Loading profile...</p>
      </div>
    );
  }

  const { athlete, performance, recent_assessments = [] } = profile;
  const overallIndex = performance ? Math.round(performance.overall_index) : 0;
  const badge = getBenchmarkBadge(overallIndex);

  const skills = [
    { label: t.domains?.speed || 'Speed', score: performance ? Math.round(performance.speed_score) : 0, color: '#00f2fe' },
    { label: t.domains?.agility || 'Agility', score: performance ? Math.round(performance.agility_score) : 0, color: '#4facfe' },
    { label: t.domains?.strength || 'Strength', score: performance ? Math.round(performance.strength_score) : 0, color: '#00f5a0' },
    { label: t.domains?.power || 'Explosive Power', score: performance ? Math.round(performance.power_score) : 0, color: '#ffb800' },
    { label: t.domains?.endurance || 'Endurance', score: performance ? Math.round(performance.endurance_score) : 0, color: '#9d4edd' },
    { label: t.domains?.flexibility || 'Flexibility', score: performance ? Math.round(performance.flexibility_score || 0) : 0, color: '#00c2a8' },
  ];

  // Body composition (BMI) is a two-sided "optimal band" indicator, shown apart
  // from the higher-is-better athletic domains above.
  const bmi = performance?.bmi ?? null;
  const bodyCompScore = performance ? Math.round(performance.body_composition_score || 0) : 0;
  const testsCompleted = performance?.tests_completed ?? 0;

  const radius = 58;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (overallIndex / 100) * circumference;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header Card */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{
              width: '64px', height: '64px', borderRadius: '50%',
              background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 0 20px rgba(0, 242, 254, 0.35)'
            }}>
              <User size={32} color="#070a12" />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <h2 style={{ fontSize: '1.4rem' }}>{athlete.name}</h2>
                <span className={badge.className}>{badge.text}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '4px', fontSize: '0.8rem', color: 'var(--text-muted)', flexWrap: 'wrap' }}>
                <span className="mono" style={{ color: 'var(--primary)' }}>ID: {athlete.athlete_id}</span>
                <span>•</span>
                <span>{athlete.age} yrs ({athlete.category})</span>
                <span>•</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                  <MapPin size={12} color="var(--primary)" />
                  {athlete.district}, {athlete.state}
                </span>
              </div>
              {/* Physical details */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '4px', fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                {athlete.height_cm && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                    <Ruler size={11} /> {athlete.height_cm} cm
                  </span>
                )}
                {athlete.weight_kg && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                    <Weight size={11} /> {athlete.weight_kg} kg
                  </span>
                )}
                {athlete.school && <span>• {athlete.school}</span>}
                {athlete.sports_interest && <span>• {athlete.sports_interest}</span>}
              </div>
            </div>
          </div>

          <button onClick={onTakeNewTest} className="btn btn-primary btn-pill">
            <Zap size={16} />
            + Take Fitness Assessment
          </button>
        </div>

        {/* Performance Index Gauge + Skills */}
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '24px', alignItems: 'center',
          background: 'rgba(0, 0, 0, 0.25)', padding: '20px',
          borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-glass)'
        }}>
          {/* Gauge */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '20px' }}>
            <div className="circle-gauge-wrap" style={{ width: '140px', height: '140px' }}>
              <svg width="140" height="140" style={{ transform: 'rotate(-90deg)' }}>
                <circle cx="70" cy="70" r={radius} stroke="rgba(255, 255, 255, 0.08)" strokeWidth="10" fill="transparent" />
                <circle cx="70" cy="70" r={radius} stroke="url(#indexGrad)" strokeWidth="10"
                  strokeDasharray={circumference} strokeDashoffset={strokeDashoffset}
                  strokeLinecap="round" fill="transparent"
                  style={{ transition: 'stroke-dashoffset 1s ease' }}
                />
                <defs>
                  <linearGradient id="indexGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#00f2fe" />
                    <stop offset="100%" stopColor="#00f5a0" />
                  </linearGradient>
                </defs>
              </svg>
              <div className="circle-gauge-content">
                <div className="mono" style={{ fontSize: '2.2rem', fontWeight: 900, color: '#ffffff', lineHeight: 1 }}>
                  {overallIndex}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>/ 100</div>
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Overall Indicator
              </div>
              <h3 style={{ fontSize: '1.2rem', color: 'var(--accent-green)', margin: '2px 0 6px 0' }}>
                Athletic Performance Index
              </h3>
              <p style={{ fontSize: '0.76rem', color: 'var(--text-dim)', maxWidth: '180px' }}>
                {overallIndex === 0
                  ? 'Complete your first assessment to see your score.'
                  : `Weighted score across ${testsCompleted || 'your'} assessed fitness ${testsCompleted === 1 ? 'test' : 'tests'}.`}
              </p>
              {/* Body composition (BMI) — two-sided optimal-band indicator */}
              {bmi != null && (
                <div style={{
                  display: 'inline-flex', alignItems: 'center', gap: '8px', marginTop: '10px',
                  padding: '6px 12px', background: 'rgba(255,255,255,0.04)',
                  border: '1px solid var(--border-glass)', borderRadius: 'var(--radius-pill)'
                }}>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    {t.domains?.bodyComposition || 'Body Composition'}
                  </span>
                  <span className="mono" style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-main)' }}>
                    BMI {bmi.toFixed(1)}
                  </span>
                  <span className="mono" style={{ fontSize: '0.8rem', fontWeight: 700, color: '#00c2a8' }}>
                    {bodyCompScore}/100
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Skills */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {skills.map(s => (
              <div key={s.label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '3px' }}>
                  <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>{s.label}</span>
                  <span className="mono" style={{ fontWeight: 700, color: s.color }}>{s.score}/100</span>
                </div>
                <div style={{ width: '100%', height: '8px', borderRadius: 'var(--radius-pill)', background: 'rgba(255, 255, 255, 0.06)', overflow: 'hidden' }}>
                  <div style={{
                    width: `${s.score}%`, height: '100%', background: s.color,
                    borderRadius: 'var(--radius-pill)', boxShadow: `0 0 10px ${s.color}60`,
                    transition: 'width 0.8s ease'
                  }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Assessment History */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Award size={20} color="var(--primary)" />
            <h3 style={{ fontSize: '1.1rem' }}>Assessment History</h3>
          </div>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            {recent_assessments.length} {recent_assessments.length === 1 ? 'Test' : 'Tests'} Recorded
          </span>
        </div>

        {recent_assessments.length === 0 ? (
          <div style={{
            padding: '40px 20px', textAlign: 'center', color: 'var(--text-dim)',
            border: '2px dashed var(--border-glass)', borderRadius: 'var(--radius-md)'
          }}>
            <Zap size={36} style={{ marginBottom: '10px', opacity: 0.4 }} />
            <p style={{ fontSize: '0.9rem', marginBottom: '4px' }}>No assessments yet</p>
            <p style={{ fontSize: '0.78rem' }}>
              Click "Take Fitness Assessment" above to record your first AI-verified test!
            </p>
          </div>
        ) : (
          <div style={{ display: 'grid', gap: '10px' }}>
            {recent_assessments.map(item => {
              const statusBadge = item.status === 'VALID' ? 'badge badge-valid'
                : item.status === 'SUSPICIOUS' ? 'badge badge-warning' : 'badge badge-danger';
              return (
                <div key={item.assessment_id} style={{
                  padding: '14px 18px', background: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid var(--border-glass)', borderRadius: 'var(--radius-md)',
                  transition: 'border-color 0.2s ease'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '3px' }}>
                        <span style={{ fontWeight: 700 }}>{formatTestName(item.test_type, t)}</span>
                        <span className={statusBadge} style={{ fontSize: '0.63rem' }}>
                          {item.status}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        Result: <strong style={{ color: 'var(--text-main)' }}>{item.raw_score} {item.unit}</strong>
                        {' '}• Confidence: {Math.round(item.confidence)}%
                        {' '}• Validity: {Math.round(item.validation_score)}%
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '2px' }}>
                        <Calendar size={11} />
                        {formatDate(item.timestamp)}
                      </div>
                    </div>

                    <div style={{ textAlign: 'right' }}>
                      <div className="mono" style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--accent-green)' }}>
                        {Math.round(item.normalized_score)}<span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>/100</span>
                      </div>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)' }}>
                        {item.benchmark_status}
                      </div>
                      <button
                        onClick={() => api.downloadCertificate(item.assessment_id)
                          .catch(err => alert(err.message || 'Certificate download failed.'))}
                        className="btn btn-secondary"
                        style={{ padding: '4px 10px', fontSize: '0.65rem', marginTop: '8px' }}
                        title="Download verified certificate">
                        <Download size={12} /> {t?.certificate || 'Certificate'}
                      </button>
                    </div>
                  </div>

                  {/* Corrective coaching for this result — what to fix and how to improve */}
                  <CoachingFeedback coaching={item.coaching} t={t} compact />
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
