import React, { useRef, useEffect, useState } from 'react';

// MediaPipe 33 standard joint skeleton connections
const POSE_CONNECTIONS = [
  // Torso
  ['LEFT_SHOULDER', 'RIGHT_SHOULDER'],
  ['LEFT_SHOULDER', 'LEFT_HIP'],
  ['RIGHT_SHOULDER', 'RIGHT_HIP'],
  ['LEFT_HIP', 'RIGHT_HIP'],
  // Left arm
  ['LEFT_SHOULDER', 'LEFT_ELBOW'],
  ['LEFT_ELBOW', 'LEFT_WRIST'],
  // Right arm
  ['RIGHT_SHOULDER', 'RIGHT_ELBOW'],
  ['RIGHT_ELBOW', 'RIGHT_WRIST'],
  // Left leg
  ['LEFT_HIP', 'LEFT_KNEE'],
  ['LEFT_KNEE', 'LEFT_ANKLE'],
  // Right leg
  ['RIGHT_HIP', 'RIGHT_KNEE'],
  ['RIGHT_KNEE', 'RIGHT_ANKLE'],
  // Head
  ['NOSE', 'LEFT_SHOULDER'],
  ['NOSE', 'RIGHT_SHOULDER']
];

export default function PoseVideoPlayer({ videoSrc, framesLandmarks, fps = 30, testType, activeMetric }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentFrameIdx, setCurrentFrameIdx] = useState(0);

  // Sync canvas pose drawing with video playback time
  useEffect(() => {
    let animationFrameId;

    const renderSkeleton = () => {
      const video = videoRef.current;
      const canvas = canvasRef.current;

      if (video && canvas) {
        const ctx = canvas.getContext('2d');
        const width = canvas.width = video.videoWidth || 640;
        const height = canvas.height = video.videoHeight || 480;

        ctx.clearRect(0, 0, width, height);

        if (framesLandmarks && framesLandmarks.length > 0) {
          const currentTime = video.currentTime;
          const targetIdx = Math.min(
            framesLandmarks.length - 1,
            Math.floor(currentTime * fps)
          );
          setCurrentFrameIdx(targetIdx);

          const frameData = framesLandmarks[targetIdx];
          if (frameData && frameData.landmarks) {
            const lm = frameData.landmarks;

            // Draw skeleton connections
            ctx.lineWidth = 4;
            ctx.strokeStyle = '#00f5a0';
            ctx.shadowColor = '#00f5a0';
            ctx.shadowBlur = 10;

            for (const [p1Name, p2Name] of POSE_CONNECTIONS) {
              const p1 = lm[p1Name];
              const p2 = lm[p2Name];

              if (p1 && p2 && (p1.visibility || p1[2] || 1.0) > 0.3 && (p2.visibility || p2[2] || 1.0) > 0.3) {
                const x1 = (p1.x !== undefined ? p1.x : p1[0]) * width;
                const y1 = (p1.y !== undefined ? p1.y : p1[1]) * height;
                const x2 = (p2.x !== undefined ? p2.x : p2[0]) * width;
                const y2 = (p2.y !== undefined ? p2.y : p2[1]) * height;

                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(x2, y2);
                ctx.stroke();
              }
            }

            // Draw joint keypoint nodes
            ctx.shadowBlur = 15;
            for (const [name, pt] of Object.entries(lm)) {
              const x = (pt.x !== undefined ? pt.x : pt[0]) * width;
              const y = (pt.y !== undefined ? pt.y : pt[1]) * height;
              const vis = pt.visibility !== undefined ? pt.visibility : (pt[2] || 1.0);

              if (vis > 0.3) {
                ctx.beginPath();
                ctx.arc(x, y, 6, 0, 2 * Math.PI);
                ctx.fillStyle = '#00f2fe';
                ctx.shadowColor = '#00f2fe';
                ctx.fill();

                ctx.beginPath();
                ctx.arc(x, y, 3, 0, 2 * Math.PI);
                ctx.fillStyle = '#ffffff';
                ctx.fill();
              }
            }
          }
        }
      }

      animationFrameId = requestAnimationFrame(renderSkeleton);
    };

    renderSkeleton();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [framesLandmarks, fps]);

  return (
    <div style={{
      position: 'relative',
      borderRadius: 'var(--radius-lg)',
      overflow: 'hidden',
      background: '#040711',
      border: '1px solid var(--border-glow)',
      boxShadow: '0 10px 30px rgba(0, 0, 0, 0.7)'
    }}>
      {/* Video Element */}
      <video
        ref={videoRef}
        src={videoSrc}
        controls
        playsInline
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        style={{
          width: '100%',
          maxHeight: '480px',
          display: 'block',
          objectFit: 'contain'
        }}
      />

      {/* Synchronized AI Skeleton Overlay Canvas */}
      <canvas
        ref={canvasRef}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          objectFit: 'contain'
        }}
      />

      {/* Top HUD Badge */}
      <div style={{
        position: 'absolute',
        top: '12px',
        left: '12px',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        background: 'rgba(7, 10, 18, 0.75)',
        backdropFilter: 'blur(10px)',
        padding: '6px 12px',
        borderRadius: 'var(--radius-pill)',
        border: '1px solid var(--border-glass)',
        fontSize: '0.75rem',
        fontWeight: 700
      }}>
        <div style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: isPlaying ? 'var(--accent-green)' : 'var(--primary)',
          boxShadow: isPlaying ? '0 0 10px var(--accent-green)' : 'none'
        }} />
        <span style={{ color: 'var(--primary)' }}>MediaPipe Pose AI HUD</span>
        <span style={{ color: 'var(--text-muted)' }}>Frame: {currentFrameIdx}</span>
      </div>

      {/* Floating Active Metric Card */}
      {activeMetric && (
        <div style={{
          position: 'absolute',
          bottom: '12px',
          right: '12px',
          background: 'rgba(13, 20, 36, 0.85)',
          backdropFilter: 'blur(14px)',
          border: '1px solid var(--border-glow)',
          borderRadius: 'var(--radius-md)',
          padding: '8px 14px',
          textAlign: 'right',
          boxShadow: '0 4px 20px rgba(0, 242, 254, 0.25)'
        }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            {activeMetric.label}
          </div>
          <div className="mono" style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--accent-green)' }}>
            {activeMetric.value}
          </div>
        </div>
      )}
    </div>
  );
}
