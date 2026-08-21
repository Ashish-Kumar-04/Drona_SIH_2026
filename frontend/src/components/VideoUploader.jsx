import React, { useState, useRef } from 'react';
import { Upload, Video, Camera, StopCircle, RefreshCw, AlertCircle } from 'lucide-react';
import { api } from '../utils/api';

export default function VideoUploader({ athleteId, testType, onProcessingComplete, t }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [videoPreviewUrl, setVideoPreviewUrl] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  const fileInputRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const webcamVideoRef = useRef(null);
  const recordedChunksRef = useRef([]);

  // Handle local video file selection
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      setVideoPreviewUrl(URL.createObjectURL(file));
      setErrorMsg(null);
    }
  };

  // Start real video upload & AI inference on FastAPI backend
  const handleProcessVideo = async () => {
    if (!selectedFile) {
      setErrorMsg('Please select or record a video first.');
      return;
    }

    setIsProcessing(true);
    setErrorMsg(null);

    try {
      const result = await api.uploadVideo(selectedFile, athleteId, testType, 170.0);
      onProcessingComplete(result, videoPreviewUrl);
    } catch (err) {
      setErrorMsg(err.message || 'AI video processing failed.');
    } finally {
      setIsProcessing(false);
    }
  };

  // Live Webcam Recording
  const startWebcamRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      if (webcamVideoRef.current) {
        webcamVideoRef.current.srcObject = stream;
        webcamVideoRef.current.play();
      }

      recordedChunksRef.current = [];
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordedChunksRef.current.push(e.data);
      };
      mediaRecorder.onstop = () => {
        const blob = new Blob(recordedChunksRef.current, { type: 'video/mp4' });
        const file = new File([blob], 'webcam_assessment.mp4', { type: 'video/mp4' });
        setSelectedFile(file);
        setVideoPreviewUrl(URL.createObjectURL(blob));
        // Stop stream tracks
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start();
      setIsRecording(true);
      setErrorMsg(null);
    } catch (err) {
      setErrorMsg('Webcam permission denied or camera not found.');
    }
  };

  const stopWebcamRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '24px', textAlign: 'center' }}>
      <h3 style={{ fontSize: '1.25rem', marginBottom: '8px' }}>
        Record or Upload Real Test Video
      </h3>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '20px' }}>
        Upload any real athlete test video (.mp4, .mov, .webm) or record live via camera for instant AI MediaPipe Pose analysis.
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

      {/* Recording Webcam View */}
      {isRecording && (
        <div style={{ position: 'relative', marginBottom: '16px', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
          <video
            ref={webcamVideoRef}
            muted
            style={{ width: '100%', maxHeight: '360px', background: '#000', objectFit: 'cover' }}
          />
          <div style={{
            position: 'absolute',
            top: '12px',
            left: '12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: 'rgba(255, 56, 92, 0.9)',
            padding: '4px 10px',
            borderRadius: 'var(--radius-pill)',
            fontSize: '0.75rem',
            fontWeight: 700
          }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#fff' }} />
            RECORDING LIVE ASSESSMENT
          </div>
        </div>
      )}

      {/* Upload & Webcam Action Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '14px',
        marginBottom: '20px'
      }}>
        {/* File Upload Trigger */}
        <input
          type="file"
          accept="video/*"
          ref={fileInputRef}
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          className="btn btn-secondary"
          style={{ padding: '16px', display: 'flex', flexDirection: 'column', height: '100px' }}
        >
          <Upload size={24} color="var(--primary)" />
          <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Choose Video File</span>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>MP4, MOV, WEBM</span>
        </button>

        {/* Live Camera Trigger */}
        {!isRecording ? (
          <button
            onClick={startWebcamRecording}
            className="btn btn-secondary"
            style={{ padding: '16px', display: 'flex', flexDirection: 'column', height: '100px' }}
          >
            <Camera size={24} color="var(--accent-green)" />
            <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Record Webcam</span>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Live Camera Feed</span>
          </button>
        ) : (
          <button
            onClick={stopWebcamRecording}
            className="btn btn-danger"
            style={{ padding: '16px', display: 'flex', flexDirection: 'column', height: '100px' }}
          >
            <StopCircle size={24} />
            <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Stop Recording</span>
            <span style={{ fontSize: '0.72rem' }}>Finish Test Clip</span>
          </button>
        )}
      </div>

      {/* Selected File Status */}
      {selectedFile && (
        <div style={{
          padding: '12px 16px',
          background: 'rgba(0, 242, 254, 0.05)',
          border: '1px solid var(--border-glow)',
          borderRadius: 'var(--radius-md)',
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', textAlign: 'left' }}>
            <Video size={20} color="var(--primary)" />
            <div>
              <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>{selectedFile.name}</div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                Size: {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
              </div>
            </div>
          </div>
          <span className="badge badge-valid">Ready to Process</span>
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
