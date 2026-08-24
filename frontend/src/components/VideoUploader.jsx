import React, { useState, useRef, useEffect } from 'react';
import { Upload, Video, RefreshCw, AlertCircle, CheckCircle2, FileVideo, CloudOff } from 'lucide-react';
import LiveWebcamGuidance from './LiveWebcamGuidance';
import { api } from '../utils/api';

export default function VideoUploader({ athleteId, testType, initialMode = 'file', onProcessingComplete, t }) {
  const [mode, setMode] = useState(initialMode); // 'file' | 'webcam'
  const [selectedFile, setSelectedFile] = useState(null);
  const [videoPreviewUrl, setVideoPreviewUrl] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [queuedNotice, setQueuedNotice] = useState(false);

  const fileInputRef = useRef(null);

  useEffect(() => {
    setMode(initialMode);
  }, [initialMode]);

  // Handle local video file selection
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      setVideoPreviewUrl(URL.createObjectURL(file));
      setErrorMsg(null);
    }
  };

  // Callback when live webcam recording finishes
  const handleLiveWebcamRecorded = (file, previewUrl) => {
    setSelectedFile(file);
    setVideoPreviewUrl(previewUrl);
    setMode('file'); // Switch to review & analyze view
  };

  // Start real video upload & AI inference on FastAPI backend
  const handleProcessVideo = async () => {
    if (!selectedFile) {
      setErrorMsg('Please select or record a video first.');
      return;
    }

    setIsProcessing(true);
    setErrorMsg(null);
    setQueuedNotice(false);

    try {
      const result = await api.uploadVideo(selectedFile, athleteId, testType, 170.0);
      if (result && result.queued) {
        // No network — the video was stashed in IndexedDB and will auto-submit on reconnect.
        // There is no assessment result yet, so stay on this screen rather than navigating.
        setQueuedNotice(true);
        setSelectedFile(null);
        setVideoPreviewUrl(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
      } else {
        onProcessingComplete(result, videoPreviewUrl);
      }
    } catch (err) {
      setErrorMsg(err.message || 'AI video processing failed.');
    } finally {
      setIsProcessing(false);
    }
  };

  // Render Live Webcam Guidance when mode is webcam
  if (mode === 'webcam') {
    return (
      <LiveWebcamGuidance
        testType={testType}
        onRecordingComplete={handleLiveWebcamRecorded}
        onCancel={() => setMode('file')}
        t={t}
      />
    );
  }

  return (
    <div className="glass-panel" style={{ padding: '24px', textAlign: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
        <h3 style={{ fontSize: '1.25rem', margin: 0 }}>
          Submit Test Video for AI Analysis
        </h3>
        <button
          onClick={() => setMode('webcam')}
          className="btn btn-secondary"
          style={{ padding: '6px 14px', fontSize: '0.82rem' }}
        >
          📷 Record Live Webcam Instead
        </button>
      </div>

      <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '20px' }}>
        Upload any athlete test video file (.mp4, .mov, .webm) for instant MediaPipe Pose AI analysis.
      </p>

      {/* Error alert */}
      {errorMsg && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '10px 14px',
          background: 'rgba(255, 56, 92, 0.15)',
          border: '1px solid rgba(255, 56, 92, 0.4)',
          borderRadius: 'var(--radius-md)',
          color: 'var(--accent-red)',
          fontSize: '0.85rem',
          marginBottom: '16px',
          textAlign: 'left'
        }}>
          <AlertCircle size={18} />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Offline-saved notice */}
      {queuedNotice && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          padding: '12px 14px',
          background: 'rgba(255, 176, 32, 0.12)',
          border: '1px solid rgba(255, 176, 32, 0.4)',
          borderRadius: 'var(--radius-md)',
          color: '#ffb020',
          fontSize: '0.85rem',
          marginBottom: '16px',
          textAlign: 'left'
        }}>
          <CloudOff size={20} />
          <span>
            <strong>Saved offline.</strong> You have no network right now — this assessment
            was stored on your device and will submit automatically once you're back online.
          </span>
        </div>
      )}

      {/* File Upload Selector Box */}
      <input
        type="file"
        accept="video/*"
        ref={fileInputRef}
        onChange={handleFileChange}
        style={{ display: 'none' }}
      />

      <div
        onClick={() => fileInputRef.current?.click()}
        style={{
          border: '2px dashed var(--border-glow)',
          borderRadius: 'var(--radius-lg)',
          padding: '32px 20px',
          cursor: 'pointer',
          background: 'rgba(0, 242, 254, 0.02)',
          marginBottom: '20px',
          transition: 'all 0.2s ease'
        }}
      >
        <Upload size={36} color="var(--primary)" style={{ marginBottom: '10px' }} />
        <div style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '4px' }}>
          Click to Browse & Select Video File
        </div>
        <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
          Supports MP4, MOV, WEBM format
        </div>
      </div>

      {/* Selected File Status / Video Preview */}
      {selectedFile && (
        <div style={{
          padding: '14px 18px',
          background: 'rgba(0, 242, 254, 0.06)',
          border: '1px solid var(--border-glow)',
          borderRadius: 'var(--radius-md)',
          marginBottom: '20px',
          textAlign: 'left'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <FileVideo size={24} color="var(--primary)" />
              <div>
                <div style={{ fontSize: '0.9rem', fontWeight: 700 }}>{selectedFile.name}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Size: {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                </div>
              </div>
            </div>
            <span className="badge badge-valid">Ready for Analysis</span>
          </div>

          {videoPreviewUrl && (
            <video
              src={videoPreviewUrl}
              controls
              style={{ width: '100%', maxHeight: '240px', borderRadius: 'var(--radius-sm)', background: '#000' }}
            />
          )}
        </div>
      )}

      {/* Process Button */}
      <button
        onClick={handleProcessVideo}
        disabled={!selectedFile || isProcessing}
        className="btn btn-primary btn-pill"
        style={{
          width: '100%',
          padding: '14px',
          fontSize: '1.05rem',
          opacity: (!selectedFile || isProcessing) ? 0.6 : 1.0,
          cursor: (!selectedFile || isProcessing) ? 'not-allowed' : 'pointer'
        }}
      >
        {isProcessing ? (
          <>
            <RefreshCw size={20} className="glow-pulse" style={{ animation: 'spin 1s linear infinite' }} />
            Running MediaPipe Pose AI Model...
          </>
        ) : (
          <>
            <Video size={20} />
            Analyze Assessment with AI &rarr;
          </>
        )}
      </button>
    </div>
  );
}
