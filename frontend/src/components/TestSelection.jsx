import React from 'react';
import {
  Dumbbell, ArrowUpCircle, Gauge, ChevronRight,
  Timer, Route, Ruler, MoveHorizontal, Video, ClipboardEdit
} from 'lucide-react';
import { TESTS } from '../utils/tests';

// Per-test presentation (icon, accent colour, headline metrics) keyed by the
// canonical test id. The list of tests itself comes from the shared registry
// (utils/tests.js) so it stays in sync with the backend battery.
const TEST_UI = {
  sit_up:        { icon: Dumbbell,       color: '#00f2fe', metrics: 'Angle FSM • Reps • Cadence' },
  vertical_jump: { icon: ArrowUpCircle,  color: '#00f5a0', metrics: 'Kinematics • Flight Time • Jump cm' },
  shuttle_run:   { icon: Gauge,          color: '#ffb800', metrics: '2D Trajectory • Boundary Cross • Time' },
  broad_jump:    { icon: MoveHorizontal, color: '#ff8a5c', metrics: 'Horizontal COM • Distance cm' },
  sprint_50m:    { icon: Timer,          color: '#4facfe', metrics: 'Stopwatch / Timing Gate • Seconds' },
  endurance_run: { icon: Route,          color: '#9d4edd', metrics: '600m Timed Run • Seconds' },
  sit_and_reach: { icon: Ruler,          color: '#00c2a8', metrics: 'Sit-and-reach Box • cm reached' },
};

export default function TestSelection({ onSelectTest, selectedTest, t }) {
  return (
    <div style={{ marginBottom: '24px' }}>
      <h3 style={{ fontSize: '1.25rem', marginBottom: '4px' }}>Select Fitness Test</h3>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '16px' }}>
        Standardized SAI physical assessment battery — computer-vision tests plus officiated manual entries.
      </p>

      <div style={{ display: 'grid', gap: '14px' }}>
        {TESTS.map(test => {
          const ui = TEST_UI[test.id] || { icon: Gauge, color: 'var(--primary)', metrics: '' };
          const Icon = ui.icon;
          const isSelected = selectedTest === test.id;
          const isCv = test.capture === 'cv';
          return (
            <div
              key={test.id}
              onClick={() => onSelectTest(test.id)}
              className={isSelected ? 'glass-panel-glow' : 'glass-panel'}
              style={{
                padding: '18px 20px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                borderColor: isSelected ? ui.color : 'var(--border-glass)'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <div style={{
                  width: '52px',
                  height: '52px',
                  borderRadius: '14px',
                  background: 'rgba(255, 255, 255, 0.04)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  border: `1px solid ${ui.color}40`,
                  flexShrink: 0
                }}>
                  <Icon size={28} color={ui.color} />
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '4px' }}>
                    <h4 style={{ fontSize: '1.05rem', color: 'var(--text-main)' }}>
                      {t.tests[test.titleKey]}
                    </h4>
                    <span className="badge" style={{
                      fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.03em',
                      display: 'inline-flex', alignItems: 'center', gap: '3px',
                      background: isCv ? 'rgba(0, 242, 254, 0.12)' : 'rgba(157, 78, 221, 0.14)',
                      color: isCv ? 'var(--primary)' : '#c08bff',
                      border: `1px solid ${isCv ? 'rgba(0,242,254,0.3)' : 'rgba(157,78,221,0.35)'}`
                    }}>
                      {isCv ? <><Video size={10} /> LIVE CV</> : <><ClipboardEdit size={10} /> MANUAL</>}
                    </span>
                  </div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                    {t.tests[test.descKey]}
                  </p>
                  <span style={{ fontSize: '0.72rem', color: ui.color, fontWeight: 600 }}>
                    {ui.metrics}
                  </span>
                </div>
              </div>

              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                background: isSelected ? ui.color : 'rgba(255, 255, 255, 0.05)',
                color: isSelected ? '#070a12' : 'var(--text-muted)',
                flexShrink: 0
              }}>
                <ChevronRight size={20} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
