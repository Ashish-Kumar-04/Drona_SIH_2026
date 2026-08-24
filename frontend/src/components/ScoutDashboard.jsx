import React, { useState, useEffect } from 'react';
import {
  Search, MapPin, Users, Award, TrendingUp, ShieldCheck, ShieldAlert,
  Phone, Mail, X, Trophy, Filter
} from 'lucide-react';
import { api } from '../utils/api';
import { TESTS, formatTestName } from '../utils/tests';

const INDIAN_STATES = [
  'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
  'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand',
  'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur',
  'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Punjab',
  'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura',
  'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
  'Andaman and Nicobar Islands', 'Chandigarh', 'Dadra and Nagar Haveli and Daman and Diu',
  'Delhi', 'Jammu and Kashmir', 'Ladakh', 'Lakshadweep', 'Puducherry'
];

const inputStyle = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: 'var(--radius-md)',
  background: 'rgba(255, 255, 255, 0.05)',
  border: '1px solid var(--border-glass)',
  color: 'var(--text-main)',
  fontSize: '0.88rem',
  fontFamily: 'var(--font-body)',
  outline: 'none'
};

const labelStyle = {
  display: 'block',
  fontSize: '0.72rem',
  color: 'var(--text-muted)',
  marginBottom: '5px',
  fontWeight: 600,
  letterSpacing: '0.02em'
};

const indexColor = (v) => {
  if (v >= 80) return 'var(--accent-green)';
  if (v >= 60) return 'var(--primary)';
  if (v >= 40) return '#ffb020';
  return 'var(--text-muted)';
};

export default function ScoutDashboard({ official, t, lang }) {
  const [filters, setFilters] = useState({ state: '', district: '', min_overall_index: '', test_type: '' });
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searched, setSearched] = useState(false);

  const testLabel = (tt) => formatTestName(tt, t);

  const runSearch = async (activeFilters) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.scoutSearch(activeFilters);
      setResults(Array.isArray(data) ? data : []);
      setSearched(true);
    } catch (err) {
      setError(err.message);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  // Populate with all athletes on first mount.
  useEffect(() => {
    runSearch({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSearch = (e) => {
    if (e) e.preventDefault();
    runSearch(filters);
  };

  const handleClear = () => {
    const cleared = { state: '', district: '', min_overall_index: '', test_type: '' };
    setFilters(cleared);
    runSearch(cleared);
  };

  // ─── Summary stats derived from results ───
  const totalFound = results.length;
  const districtsCovered = new Set(results.map(r => `${r.athlete.state}|${r.athlete.district}`)).size;
  const topTalents = results.filter(r => (r.performance?.overall_index || 0) >= 80).length;

  const stats = [
    { icon: Users, label: t.scout.athletesAssessed, value: totalFound, color: 'var(--primary)' },
    { icon: MapPin, label: t.scout.districtsCovered, value: districtsCovered, color: '#4facfe' },
    { icon: Trophy, label: t.scout.topTalents, value: topTalents, color: 'var(--accent-green)' }
  ];

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: '20px' }}>
        <h2 style={{ fontSize: '1.5rem', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Award size={26} color="var(--primary)" />
          {t.scout.dashTitle}
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          {t.scout.dashSubtitle}
          {official?.organization ? ` — ${official.organization}` : ''}
        </p>
      </div>

      {/* Summary stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '14px', marginBottom: '20px' }}>
        {stats.map((s, i) => (
          <div key={i} className="glass-panel" style={{ padding: '18px 20px', display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div style={{
              width: '44px', height: '44px', borderRadius: '12px',
              background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-glass)',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <s.icon size={22} color={s.color} />
            </div>
            <div>
              <div style={{ fontSize: '1.6rem', fontWeight: 800, color: s.color, lineHeight: 1 }}>{s.value}</div>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: '3px' }}>{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Filter bar */}
      <form onSubmit={handleSearch} className="glass-panel" style={{ padding: '18px 20px', marginBottom: '22px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
          <Filter size={16} color="var(--primary)" />
          <span style={{ fontWeight: 700, fontSize: '0.9rem' }}>{t.scout.filters}</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', alignItems: 'end' }}>
          <div>
            <label style={labelStyle}>{t.scout.filterState}</label>
            <select value={filters.state} onChange={(e) => setFilters({ ...filters, state: e.target.value })}
              style={{ ...inputStyle, background: '#0d1424' }}>
              <option value="">{t.scout.anyState}</option>
              {INDIAN_STATES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>{t.scout.filterDistrict}</label>
            <input type="text" placeholder={t.scout.districtPlaceholder} value={filters.district}
              onChange={(e) => setFilters({ ...filters, district: e.target.value })} style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>{t.scout.filterScore}</label>
            <input type="number" min="0" max="100" placeholder="0 – 100" value={filters.min_overall_index}
              onChange={(e) => setFilters({ ...filters, min_overall_index: e.target.value })} style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>{t.scout.filterTest}</label>
            <select value={filters.test_type} onChange={(e) => setFilters({ ...filters, test_type: e.target.value })}
              style={{ ...inputStyle, background: '#0d1424' }}>
              <option value="">{t.scout.anyTest}</option>
              {TESTS.map(test => (
                <option key={test.id} value={test.id}>{t.tests[test.titleKey]}</option>
              ))}
            </select>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button type="submit" disabled={loading} className="btn btn-primary"
              style={{ flex: 1, padding: '10px 14px', fontSize: '0.85rem', whiteSpace: 'nowrap' }}>
              <Search size={15} /> {loading ? t.scout.searching : t.scout.search}
            </button>
            <button type="button" onClick={handleClear} className="btn btn-secondary"
              style={{ padding: '10px 12px', fontSize: '0.85rem' }} title={t.scout.clear}>
              <X size={15} />
            </button>
          </div>
        </div>
      </form>

      {error && (
        <div style={{ padding: '12px 16px', background: 'rgba(255, 56, 92, 0.12)', color: 'var(--accent-red)', borderRadius: 'var(--radius-md)', marginBottom: '16px', fontSize: '0.85rem', border: '1px solid rgba(255, 56, 92, 0.3)' }}>
          {error}
        </div>
      )}

      {/* Results */}
      <h3 style={{ fontSize: '1.05rem', marginBottom: '14px', color: 'var(--text-muted)', fontWeight: 700 }}>
        {t.scout.resultsHeading} <span style={{ color: 'var(--primary)' }}>({totalFound})</span>
      </h3>

      {!loading && searched && totalFound === 0 && (
        <div className="glass-panel" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
          {t.scout.noResults}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '16px' }}>
        {results.map((r) => {
          const a = r.athlete;
          const idx = r.performance?.overall_index || 0;
          const latest = r.recent_assessments && r.recent_assessments[0];
          const valid = latest && String(latest.status).toUpperCase() === 'VALID';
          return (
            <div key={a.athlete_id} className="glass-panel" style={{ padding: '18px 20px' }}>
              {/* Card header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <div>
                  <div style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-main)' }}>{a.name}</div>
                  <div className="mono" style={{ fontSize: '0.7rem', color: 'var(--primary)', marginTop: '2px' }}>{a.athlete_id}</div>
                </div>
                <div style={{ textAlign: 'center', minWidth: '72px' }}>
                  <div style={{ fontSize: '1.7rem', fontWeight: 800, color: indexColor(idx), lineHeight: 1 }}>
                    {idx.toFixed(1)}
                  </div>
                  <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginTop: '2px' }}>{t.scout.overallIndex}</div>
                </div>
              </div>

              {/* Meta */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '12px' }}>
                <span className="badge" style={{ fontSize: '0.66rem', background: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)' }}>
                  {t.scout.age}: {a.age} • {a.category}
                </span>
                <span className="badge" style={{ fontSize: '0.66rem', background: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)' }}>
                  <MapPin size={10} style={{ verticalAlign: 'middle', marginRight: '3px' }} />
                  {a.district}, {a.state}
                </span>
              </div>

              {/* Domain mini-breakdown */}
              {r.performance && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '5px', marginBottom: '12px' }}>
                  {[
                    { k: 'speed_score', label: t.domains.speed },
                    { k: 'agility_score', label: t.domains.agility },
                    { k: 'strength_score', label: t.domains.strength },
                    { k: 'power_score', label: t.domains.power },
                    { k: 'endurance_score', label: t.domains.endurance },
                    { k: 'flexibility_score', label: t.domains.flexibility }
                  ].map((d) => (
                    <div key={d.k} style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '0.82rem', fontWeight: 700, color: indexColor(r.performance[d.k] || 0) }}>
                        {Math.round(r.performance[d.k] || 0)}
                      </div>
                      <div style={{ fontSize: '0.54rem', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                        {d.label.split(' ')[0]}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Latest assessment + validation */}
              {latest ? (
                <div style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '10px 12px', background: 'rgba(0,0,0,0.25)', borderRadius: 'var(--radius-md)', marginBottom: '12px'
                }}>
                  <div>
                    <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>{t.scout.latestTest}</div>
                    <div style={{ fontSize: '0.82rem', fontWeight: 700 }}>
                      {testLabel(latest.test_type)}: {latest.raw_score} {latest.unit}
                    </div>
                    <div style={{ fontSize: '0.66rem', color: 'var(--text-muted)' }}>
                      {t.metrics.validationScore}: {latest.validation_score}%
                    </div>
                  </div>
                  <span className="badge" style={{
                    fontSize: '0.64rem', fontWeight: 700,
                    background: valid ? 'rgba(0,245,160,0.12)' : 'rgba(255,176,32,0.12)',
                    color: valid ? 'var(--accent-green)' : '#ffb020',
                    display: 'inline-flex', alignItems: 'center', gap: '4px'
                  }}>
                    {valid ? <ShieldCheck size={12} /> : <ShieldAlert size={12} />}
                    {latest.status}
                  </span>
                </div>
              ) : (
                <div style={{ fontSize: '0.74rem', color: 'var(--text-dim)', marginBottom: '12px', fontStyle: 'italic' }}>
                  No assessments recorded yet.
                </div>
              )}

              {/* Contact (officials are authorized to see this) */}
              {(a.phone || a.email) && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', fontSize: '0.72rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-glass)', paddingTop: '10px' }}>
                  {a.phone && <span><Phone size={12} style={{ verticalAlign: 'middle', marginRight: '4px' }} />{a.phone}</span>}
                  {a.email && <span><Mail size={12} style={{ verticalAlign: 'middle', marginRight: '4px' }} />{a.email}</span>}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
