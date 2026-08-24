import React, { useState, useRef, useEffect } from 'react';
import {
  Camera, StopCircle, AlertCircle, CheckCircle2, Eye, Sun, Compass,
  Crosshair, Maximize2, ArrowLeft, ArrowRight, ArrowUp, ArrowDown,
  WifiOff, Loader
} from 'lucide-react';
import { api } from '../utils/api';

// How often we ask the backend pose engine to re-check the framing (ms).
const CHECK_INTERVAL_MS = 750;
// Downscaled width sent to the backend — small enough to be cheap at ~1.3 Hz.
const SNAPSHOT_WIDTH = 320;
// Consecutive network failures before we drop to the on-device luminance heuristic.
const MAX_FAILURES = 2;

export default function LiveWebcamGuidance({ testType, onRecordingComplete, onCancel, t }) {
  const videoRef = useRef(null);
  const snapCanvasRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const recordedChunksRef = useRef([]);

  // Poll-loop guards (refs so the interval closure always sees current values).
  const inFlightRef = useRef(false);
  const offlineRef = useRef(false);
  const failRef = useRef(0);
  const recordingRef = useRef(false);

  const [streamActive, setStreamActive] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [mode, setMode] = useState('ai');          // 'ai' = backend pose, 'offline' = luminance only
  const [guidance, setGuidance] = useState(null);  // latest guidance dict from backend / fallback

  const tg = (t && t.guidance) || {};

  // Honest on-device fallback when the backend pose check is unreachable: only lighting is
  // measurable in-browser, so every pose-derived field is null (rendered as "not available").
  const buildOfflineGuidance = (lightingGood) => ({
    cv_available: false,
    offline: true,
    ready: !!lightingGood,
    full_body_visible: null,
    centered: null,
    distance_ok: null,
    orientation_ok: null,
    lighting_sufficient: !!lightingGood,
    camera_stable: true,
    alignment_score: lightingGood ? 60 : 25,
    off_center_x: null,
    off_center_y: null,
    orientation: null,
    instruction: lightingGood
      ? 'Basic checks only — make sure your whole body (head to feet) is in frame, then record.'
      : 'Find brighter, even lighting so the camera can see you clearly.',
  });

  useEffect(() => {
    let pollId;

    async function startCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
          audio: false
        });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play();
          setStreamActive(true);
        }
      } catch (err) {
        setErrorMsg('Webcam access denied or camera not found. Please allow camera permissions.');
      }
    }

    startCamera();

    // Throttled framing check: downscale the current frame, measure luminance locally, and
    // (when online) POST the JPEG to the backend pose engine for real alignment guidance.
    const tick = () => {
      const video = videoRef.current;
      const snap = snapCanvasRef.current;
      if (!video || video.readyState !== 4 || !snap) return;
      if (recordingRef.current) return; // no guidance needed while recording

      const vw = video.videoWidth || 640;
      const vh = video.videoHeight || 480;
      const scale = SNAPSHOT_WIDTH / vw;
      snap.width = SNAPSHOT_WIDTH;
      snap.height = Math.max(1, Math.round(vh * scale));
      const ctx = snap.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(video, 0, 0, snap.width, snap.height);

      // Local luminance — cheap, and the only signal we have if the backend is unreachable.
      let lightingGood = true;
      try {
        const data = ctx.getImageData(0, 0, snap.width, snap.height).data;
        let total = 0, samples = 0;
        for (let i = 0; i < data.length; i += 40 * 4) {
          total += 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
          samples++;
        }
        const avg = total / (samples || 1);
        lightingGood = avg > 45 && avg < 230;
      } catch (e) {
        // getImageData can throw on tainted canvas — treat lighting as unknown/ok.
      }

      if (offlineRef.current) {
        setGuidance(buildOfflineGuidance(lightingGood));
        return;
      }

      if (inFlightRef.current) return;
      inFlightRef.current = true;
      snap.toBlob((blob) => {
        if (!blob) { inFlightRef.current = false; return; }
        api.cameraCheck(blob, testType)
          .then((g) => {
            if (g && g.cv_available === false) {
              // Server has no CV libs — fall back honestly to on-device checks.
              offlineRef.current = true;
              setMode('offline');
              setGuidance(buildOfflineGuidance(lightingGood));
            } else {
              failRef.current = 0;
              setMode('ai');
              setGuidance(g);
            }
          })
          .catch(() => {
            failRef.current += 1;
            if (failRef.current >= MAX_FAILURES) {
              offlineRef.current = true;
              setMode('offline');
              setGuidance(buildOfflineGuidance(lightingGood));
            }
          })
          .finally(() => { inFlightRef.current = false; });
      }, 'image/jpeg', 0.6);
    };

    pollId = setInterval(tick, CHECK_INTERVAL_MS);

    return () => {
      clearInterval(pollId);
      if (videoRef.current && videoRef.current.srcObject) {
        videoRef.current.srcObject.getTracks().forEach(track => track.stop());
      }
    };
    // testType is fixed for the lifetime of this component instance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startRecording = () => {
    if (!videoRef.current || !videoRef.current.srcObject) return;
    const stream = videoRef.current.srcObject;
    recordedChunksRef.current = [];

    const finish = () => {
      const blob = new Blob(recordedChunksRef.current, { type: 'video/mp4' });
      const file = new File([blob], `live_webcam_${testType}_${Date.now()}.mp4`, { type: 'video/mp4' });
      const previewUrl = URL.createObjectURL(blob);
      onRecordingComplete(file, previewUrl);
    };

    const attach = (mediaRecorder) => {
      mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) recordedChunksRef.current.push(e.data); };
      mediaRecorder.onstop = finish;
      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start(100);
      recordingRef.current = true;
      setIsRecording(true);
      setErrorMsg(null);
    };

    try {
      attach(new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp8' }));
    } catch (err) {
      try {
        attach(new MediaRecorder(stream)); // fallback mimeType
      } catch (e2) {
        setErrorMsg('Failed to record video stream on this browser.');
      }
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      recordingRef.current = false;
      setIsRecording(false);
    }
  };

  // ─── Derived view state ───
  const g = guidance || {};
  const hasGuidance = !!guidance;
  const isOffline = mode === 'offline';
  const isReady = g.ready === true;
  const score = Math.max(0, Math.min(100, Math.round(g.alignment_score || 0)));
  const ringColor = isReady ? 'var(--accent-green)' : score >= 50 ? 'var(--accent-amber)' : 'var(--accent-red)';

  // Directional arrow — which way should the athlete move to re-centre?
  let arrowDir = null;
  if (hasGuidance && g.centered === false) {
    if (g.off_center_x != null && Math.abs(g.off_center_x) >= 0.15) {
      arrowDir = g.off_center_x > 0 ? 'left' : 'right';   // right-of-centre ⇒ move left
    } else if (g.off_center_y != null && Math.abs(g.off_center_y) >= 0.2) {
      arrowDir = g.off_center_y > 0 ? 'up' : 'down';
    }
  }
  const ArrowIcon = { left: ArrowLeft, right: ArrowRight, up: ArrowUp, down: ArrowDown }[arrowDir];

  const instruction = hasGuidance ? g.instruction : (tg.analyzing || 'Analyzing camera…');

  // Ring geometry.
  const ringR = 26;
  const ringC = 2 * Math.PI * ringR;
  const ringOffset = ringC - (score / 100) * ringC;

  const checks = [
    { label: tg.fullBody || 'Full Body Visibility', Icon: Eye, state: g.full_body_visible,
      okHint: 'Head to feet are in frame', badHint: 'Fit your whole body in the frame' },
    { label: tg.centering || 'Centering', Icon: Crosshair, state: g.centered,
      okHint: 'Nicely centred', badHint: 'Move toward the middle of the frame' },
    { label: tg.distance || 'Distance', Icon: Maximize2, state: g.distance_ok,
      okHint: 'Good distance from camera', badHint: 'Adjust how close you stand' },
    { label: tg.orientation || 'Orientation', Icon: Compass, state: g.orientation_ok,
      okHint: 'Facing the right way', badHint: 'Turn to the angle this test needs' },
    { label: tg.lighting || 'Lighting & Clarity', Icon: Sun, state: g.lighting_sufficient,
      okHint: 'Well lit', badHint: 'Find brighter, even lighting' },
  ];

  const canStart = streamActive && isReady && !isRecording;

  return (
    <div className="glass-panel-glow" style={{ padding: '24px', textAlign: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
        <h3 style={{ fontSize: '1.25rem', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Camera color="var(--primary)" size={24} />
          {tg.title || 'AI Camera Guidance Pre-Check'}
        </h3>
        <button onClick={onCancel} className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
          &larr; {tg.switchUpload || 'Switch to File Upload'}
        </button>
      </div>

      <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '16px' }}>
        {tg.subtitle || 'Real MediaPipe pose guidance — position yourself before recording.'}
      </p>

      {errorMsg && (
        <div style={{
          padding: '10px 14px', background: 'rgba(255, 56, 92, 0.15)',
          border: '1px solid rgba(255, 56, 92, 0.4)', borderRadius: 'var(--radius-md)',
          color: 'var(--accent-red)', fontSize: '0.85rem', marginBottom: '16px'
        }}>
          <AlertCircle size={18} style={{ verticalAlign: 'middle', marginRight: '6px' }} />
          {errorMsg}
        </div>
      )}

      {/* Live Video Feed with real-time AI overlay */}
      <div style={{
        position: 'relative', borderRadius: 'var(--radius-lg)', overflow: 'hidden',
        background: '#000', marginBottom: '16px', maxHeight: '400px'
      }}>
        <video
          ref={videoRef}
          muted
          playsInline
          style={{ width: '100%', maxHeight: '400px', objectFit: 'cover', display: 'block' }}
        />
        <canvas ref={snapCanvasRef} style={{ display: 'none' }} />

        {/* Alignment score ring (top-right) */}
        {!isRecording && (
          <div style={{ position: 'absolute', top: '12px', right: '12px' }}>
            <div style={{ position: 'relative', width: '64px', height: '64px' }}>
              <svg width="64" height="64" style={{ transform: 'rotate(-90deg)' }}>
                <circle cx="32" cy="32" r={ringR} stroke="rgba(0,0,0,0.55)" strokeWidth="6" fill="rgba(0,0,0,0.45)" />
                <circle cx="32" cy="32" r={ringR} stroke={ringColor} strokeWidth="6"
                  strokeDasharray={ringC} strokeDashoffset={ringOffset} strokeLinecap="round" fill="transparent"
                  style={{ transition: 'stroke-dashoffset 0.5s ease, stroke 0.4s ease' }} />
              </svg>
              <div style={{
                position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center'
              }}>
                <span className="mono" style={{ fontSize: '1rem', fontWeight: 800, color: '#fff', lineHeight: 1 }}>{score}</span>
                <span style={{ fontSize: '0.5rem', color: 'rgba(255,255,255,0.7)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  {tg.alignment || 'Alignment'}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Positioning box */}
        <div style={{
          position: 'absolute', top: '8%', left: '18%', right: '18%', bottom: '8%',
          border: isRecording ? '3px dashed var(--accent-red)' : isReady ? '2px dashed var(--accent-green)' : '2px dashed var(--primary)',
          borderRadius: '16px', pointerEvents: 'none',
          boxShadow: isReady ? '0 0 20px rgba(0, 245, 160, 0.3)' : 'none',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'space-between', padding: '12px'
        }}>
          <span style={{
            fontSize: '0.72rem', fontWeight: 700, background: 'rgba(0,0,0,0.7)',
            padding: '4px 10px', borderRadius: 'var(--radius-pill)',
            color: g.full_body_visible ? 'var(--accent-green)' : 'var(--primary)'
          }}>
            {g.full_body_visible ? '✓ FULL BODY DETECTED' : 'POSITION HEAD TO FEET IN THIS FRAME'}
          </span>

          {/* Directional move arrow */}
          {ArrowIcon && !isRecording && (
            <ArrowIcon size={68} color="var(--primary)"
              style={{ filter: 'drop-shadow(0 0 8px rgba(0,0,0,0.8))', animation: 'pulse 1s infinite' }} />
          )}

          {isRecording && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(255, 56, 92, 0.9)',
              padding: '6px 14px', borderRadius: 'var(--radius-pill)', color: '#fff', fontWeight: 800, fontSize: '0.85rem'
            }}>
              <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#fff', animation: 'pulse 1s infinite' }} />
              {tg.recording || 'RECORDING LIVE TEST…'}
            </div>
          )}
        </div>
      </div>

      {/* Instruction banner */}
      {!isRecording && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '10px', justifyContent: 'center',
          padding: '11px 16px', marginBottom: '16px',
          background: isReady ? 'rgba(0, 245, 160, 0.1)' : 'rgba(255, 255, 255, 0.03)',
          border: `1px solid ${isReady ? 'rgba(0, 245, 160, 0.4)' : 'var(--border-glass)'}`,
          borderRadius: 'var(--radius-md)'
        }}>
          {!hasGuidance
            ? <Loader size={16} className="spin" color="var(--text-muted)" />
            : isReady
              ? <CheckCircle2 size={18} color="var(--accent-green)" />
              : <AlertCircle size={18} color="var(--accent-amber)" />}
          <span style={{ fontSize: '0.86rem', fontWeight: 600, color: isReady ? 'var(--accent-green)' : 'var(--text-main)' }}>
            {instruction}
          </span>
          {isOffline && (
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: '4px', marginLeft: '6px',
              fontSize: '0.68rem', color: 'var(--text-dim)', border: '1px solid var(--border-glass)',
              borderRadius: 'var(--radius-pill)', padding: '2px 8px'
            }}>
              <WifiOff size={11} /> {tg.offline || 'Basic checks (offline)'}
            </span>
          )}
        </div>
      )}

      {/* Real-time checks grid (driven by the backend pose engine) */}
      {!isRecording && (
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: '10px', marginBottom: '20px', textAlign: 'left'
        }}>
          {checks.map(({ label, Icon, state, okHint, badHint }) => {
            const known = state === true || state === false;
            const ok = state === true;
            const color = !known ? 'var(--text-dim)' : ok ? 'var(--accent-green)' : 'var(--accent-amber)';
            const bg = ok ? 'rgba(0, 245, 160, 0.08)' : !known ? 'rgba(255,255,255,0.02)' : 'rgba(255, 176, 32, 0.07)';
            const border = ok ? 'rgba(0, 245, 160, 0.4)' : !known ? 'var(--border-glass)' : 'rgba(255, 176, 32, 0.35)';
            return (
              <div key={label} style={{
                background: bg, border: `1px solid ${border}`, borderRadius: 'var(--radius-md)',
                padding: '11px 12px', transition: 'all 0.3s ease'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color, marginBottom: '3px' }}>
                  {ok ? <CheckCircle2 size={17} /> : <Icon size={17} />}
                  <span style={{ fontSize: '0.8rem', fontWeight: 700 }}>{label}</span>
                </div>
                <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', margin: 0 }}>
                  {!known ? (tg.notAvailableOffline || 'Not available offline') : ok ? okHint : badHint}
                </p>
              </div>
            );
          })}
        </div>
      )}

      {/* Recording actions */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', alignItems: 'center' }}>
        {!isRecording ? (
          <>
            <button
              onClick={startRecording}
              disabled={!canStart}
              className="btn btn-primary btn-pill"
              style={{ padding: '14px 28px', fontSize: '1rem', width: '100%', maxWidth: '340px', opacity: canStart ? 1 : 0.55 }}
            >
              <Camera size={20} />
              {tg.startLive || 'Start Live Recording'} &rarr;
            </button>
            {streamActive && !isReady && (
              <button
                onClick={startRecording}
                className="btn btn-secondary"
                style={{ padding: '8px 18px', fontSize: '0.8rem' }}
              >
                {tg.recordAnyway || 'Record anyway'} &rarr;
              </button>
            )}
          </>
        ) : (
          <button
            onClick={stopRecording}
            className="btn btn-danger btn-pill"
            style={{ padding: '14px 28px', fontSize: '1rem', width: '100%', maxWidth: '340px' }}
          >
            <StopCircle size={20} />
            {tg.finishAnalyze || 'Finish & Analyze Recording'} &rarr;
          </button>
        )}
      </div>
    </div>
  );
}
