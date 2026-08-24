import React from 'react';
import { Video, Upload, Camera, ArrowRight, ShieldAlert, CheckCircle2 } from 'lucide-react';

export default function CameraGuidance({ onChooseUpload, onChooseWebcam, testTitle, t }) {
  return (
    <div className="glass-panel-glow" style={{ padding: '28px', textAlign: 'center' }}>
      <div style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '58px',
        height: '58px',
        borderRadius: '50%',
        background: 'rgba(0, 242, 254, 0.15)',
        color: 'var(--primary)',
        marginBottom: '14px'
      }}>
        <Video size={30} />
      </div>

      <h3 style={{ fontSize: '1.35rem', marginBottom: '8px' }}>
        Select Assessment Method
      </h3>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', marginBottom: '24px', maxWidth: '600px', margin: '0 auto 28px' }}>
        Choose how you would like to submit the test for AI MediaPipe Pose analysis.
      </p>

      {/* Two Assessment Options */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
        gap: '20px',
        marginBottom: '20px',
        textAlign: 'left'
      }}>
        {/* Option 1: File Upload (No Camera Checks Required) */}
        <div style={{
          background: 'rgba(13, 20, 36, 0.6)',
          border: '1px solid var(--border-glass)',
          borderRadius: 'var(--radius-lg)',
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          transition: 'transform 0.2s ease, border-color 0.2s ease'
        }}>
          <div>
            <div style={{
              display: 'inline-flex',
              padding: '10px',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(0, 242, 254, 0.1)',
              color: 'var(--primary)',
              marginBottom: '14px'
            }}>
              <Upload size={24} />
            </div>
            <h4 style={{ fontSize: '1.1rem', marginBottom: '6px' }}>
              Upload Recorded Video File
            </h4>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '14px', lineHeight: '1.5' }}>
              Upload any existing athlete test video (.mp4, .mov, .webm) recorded on phone or camera.
            </p>
            <div style={{
              fontSize: '0.74rem',
              color: 'var(--text-dim)',
              background: 'rgba(255, 255, 255, 0.03)',
              padding: '8px 12px',
              borderRadius: 'var(--radius-sm)',
              borderLeft: '3px solid var(--primary)',
              marginBottom: '18px'
            }}>
              ℹ️ Direct video file uploads bypass live camera checks and proceed straight to MediaPipe AI analysis.
            </div>
          </div>

          <button
            onClick={onChooseUpload}
            className="btn btn-secondary btn-pill"
            style={{ width: '100%', padding: '12px', fontSize: '0.92rem' }}
          >
            Upload File &rarr;
          </button>
        </div>

        {/* Option 2: Live Webcam (With Interactive Real-time Camera Guidance) */}
        <div style={{
          background: 'rgba(13, 20, 36, 0.6)',
          border: '1px solid var(--border-glow)',
          borderRadius: 'var(--radius-lg)',
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          boxShadow: '0 0 20px rgba(0, 242, 254, 0.1)'
        }}>
          <div>
            <div style={{
              display: 'inline-flex',
              padding: '10px',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(0, 245, 160, 0.1)',
              color: 'var(--accent-green)',
              marginBottom: '14px'
            }}>
              <Camera size={24} />
            </div>
            <h4 style={{ fontSize: '1.1rem', marginBottom: '6px' }}>
              Record Live via Webcam
            </h4>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '14px', lineHeight: '1.5' }}>
              Record directly using your webcam with real-time AI assistance for camera angle, body visibility, and distance positioning.
            </p>
            <div style={{
              fontSize: '0.74rem',
              color: 'var(--accent-green)',
              background: 'rgba(0, 245, 160, 0.06)',
              padding: '8px 12px',
              borderRadius: 'var(--radius-sm)',
              borderLeft: '3px solid var(--accent-green)',
              marginBottom: '18px'
            }}>
              🎥 Real-time AI guidance overlay helps you align camera angle and body visibility live!
            </div>
          </div>

          <button
            onClick={onChooseWebcam}
            className="btn btn-primary btn-pill"
            style={{ width: '100%', padding: '12px', fontSize: '0.92rem' }}
          >
            Record Live Webcam &rarr;
          </button>
        </div>
      </div>
    </div>
  );
}
