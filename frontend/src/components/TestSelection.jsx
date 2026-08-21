import React from 'react';
import { Dumbbell, ArrowUpCircle, Gauge, ChevronRight } from 'lucide-react';

export default function TestSelection({ onSelectTest, selectedTest, t }) {
  const tests = [
    {
      id: 'sit_up',
      title: t.tests.sitUp,
      subtitle: t.tests.sitUpDesc,
      icon: <Dumbbell size={28} color="#00f2fe" />,
      color: '#00f2fe',
      metrics: 'Angle FSM • Reps • Cadence'
    },
    {
      id: 'vertical_jump',
      title: t.tests.verticalJump,
      subtitle: t.tests.verticalJumpDesc,
      icon: <ArrowUpCircle size={28} color="#00f5a0" />,
      color: '#00f5a0',
      metrics: 'Kinematics • Flight Time • Jump cm'
    },
    {
      id: 'shuttle_run',
      title: t.tests.shuttleRun,
      subtitle: t.tests.shuttleRunDesc,
      icon: <Gauge size={28} color="#ffb800" />,
      color: '#ffb800',
      metrics: '2D Trajectory • Boundary Cross • Time'
    }
  ];

  return (
    <div style={{ marginBottom: '24px' }}>
      <h3 style={{ fontSize: '1.25rem', marginBottom: '4px' }}>Select Fitness Test</h3>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '16px' }}>
        Standardized SAI physical assessment protocols with on-device computer vision.
      </p>

      <div style={{ display: 'grid', gap: '14px' }}>
        {tests.map(test => {
          const isSelected = selectedTest === test.id;
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
                borderColor: isSelected ? test.color : 'var(--border-glass)'
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
                  border: `1px solid ${test.color}40`
                }}>
                  {test.icon}
                </div>
                <div>
                  <h4 style={{ fontSize: '1.05rem', color: 'var(--text-main)', marginBottom: '4px' }}>
                    {test.title}
                  </h4>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                    {test.subtitle}
                  </p>
                  <span style={{ fontSize: '0.72rem', color: test.color, fontWeight: 600 }}>
                    {test.metrics}
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
                background: isSelected ? test.color : 'rgba(255, 255, 255, 0.05)',
                color: isSelected ? '#070a12' : 'var(--text-muted)'
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
