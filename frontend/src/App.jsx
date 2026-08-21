import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import AuthScreen from './components/AuthScreen';
import TestSelection from './components/TestSelection';
import CameraGuidance from './components/CameraGuidance';
import VideoUploader from './components/VideoUploader';
import PoseVideoPlayer from './components/PoseVideoPlayer';
import LiveMetricsHUD from './components/LiveMetricsHUD';
import AthleteProfileView from './components/AthleteProfileView';
import { translations } from './utils/i18n';
import { api } from './utils/api';
import { ArrowLeft } from 'lucide-react';

export default function App() {
  const [lang, setLang] = useState('en');
  const [athlete, setAthlete] = useState(null);
  const [profileData, setProfileData] = useState(null);
  const [loading, setLoading] = useState(true);

  // Athlete workflow: 'profile' | 'select_test' | 'guidance' | 'assessment' | 'results'
  const [athleteStep, setAthleteStep] = useState('profile');
  const [selectedTest, setSelectedTest] = useState('vertical_jump');
  const [latestAssessmentResult, setLatestAssessmentResult] = useState(null);
  const [activeVideoSrc, setActiveVideoSrc] = useState(null);

  const t = translations[lang] || translations.en;

  // ─── Load profile from database ───
  const loadProfile = async (athleteId) => {
    try {
      const data = await api.getAthleteProfile(athleteId);
      setProfileData(data);
      setAthlete(data.athlete);
    } catch (err) {
      console.error('Failed to load profile:', err);
      // If profile load fails, clear session
      localStorage.removeItem('athlete_id');
      setAthlete(null);
      setProfileData(null);
    }
  };

  // ─── Check localStorage for existing session on app load ───
  useEffect(() => {
    const savedId = localStorage.getItem('athlete_id');
    if (savedId) {
      loadProfile(savedId).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  // ─── Auth handlers ───
  const handleAuthenticated = (athleteData) => {
    setAthlete(athleteData);
    loadProfile(athleteData.athlete_id);
    setAthleteStep('profile');
  };

  const handleLogout = () => {
    localStorage.removeItem('athlete_id');
    setAthlete(null);
    setProfileData(null);
    setAthleteStep('profile');
    setLatestAssessmentResult(null);
    setActiveVideoSrc(null);
  };

  // ─── Test flow handlers ───
  const handleSelectTest = (testId) => {
    setSelectedTest(testId);
    setAthleteStep('guidance');
  };

  const handleGuidanceReady = () => {
    setAthleteStep('assessment');
  };

  const handleAssessmentComplete = (result, videoUrl) => {
    setLatestAssessmentResult(result);
    setActiveVideoSrc(videoUrl);
    setAthleteStep('results');
    // Refresh profile with updated performance index
    if (athlete) {
      loadProfile(athlete.athlete_id);
    }
  };

  // ─── Loading state ───
  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{
            width: '48px', height: '48px', borderRadius: '50%',
            border: '3px solid rgba(0, 242, 254, 0.2)',
            borderTopColor: 'var(--primary)',
            animation: 'spin 0.8s linear infinite',
            margin: '0 auto 14px'
          }} />
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Loading...</p>
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  // ─── Not logged in → show Auth ───
  if (!athlete) {
    return <AuthScreen onAuthenticated={handleAuthenticated} t={t} />;
  }

  // ─── Logged in → Athlete Dashboard ───
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar athlete={athlete} onLogout={handleLogout} lang={lang} setLang={setLang} t={t} />

      <main style={{ flex: 1, padding: '24px 20px', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
        {/* Back button when in test flow */}
        {athleteStep !== 'profile' && (
          <div style={{ marginBottom: '16px' }}>
            <button onClick={() => setAthleteStep('profile')} className="btn btn-secondary"
              style={{ padding: '8px 16px', fontSize: '0.85rem' }}>
              <ArrowLeft size={16} /> Back to Dashboard
            </button>
          </div>
        )}

        {/* Step 1: Dashboard / Profile */}
        {athleteStep === 'profile' && (
          <AthleteProfileView
            profile={profileData}
            onTakeNewTest={() => setAthleteStep('select_test')}
            t={t}
          />
        )}

        {/* Step 2: Select Test */}
        {athleteStep === 'select_test' && (
          <TestSelection
            selectedTest={selectedTest}
            onSelectTest={handleSelectTest}
            t={t}
          />
        )}

        {/* Step 3: Camera Guidance */}
        {athleteStep === 'guidance' && (
          <CameraGuidance
            onReady={handleGuidanceReady}
            testTitle={selectedTest}
            t={t}
          />
        )}

        {/* Step 4: Video Upload & Assessment */}
        {athleteStep === 'assessment' && (
          <VideoUploader
            athleteId={athlete.athlete_id}
            testType={selectedTest}
            onProcessingComplete={handleAssessmentComplete}
            t={t}
          />
        )}

        {/* Step 5: Results */}
        {athleteStep === 'results' && latestAssessmentResult && (
          <div>
            <h3 style={{ fontSize: '1.25rem', marginBottom: '14px' }}>
              Assessment Results & AI Skeleton Analysis
            </h3>

            <PoseVideoPlayer
              videoSrc={activeVideoSrc}
              framesLandmarks={latestAssessmentResult.frames_landmarks}
              fps={latestAssessmentResult.frames_summary?.fps || 30}
              testType={selectedTest}
              activeMetric={{
                label: latestAssessmentResult.unit,
                value: `${latestAssessmentResult.raw_score} ${latestAssessmentResult.unit}`
              }}
            />

            <LiveMetricsHUD
              assessmentResult={latestAssessmentResult}
              testType={selectedTest}
              t={t}
            />

            <div style={{ display: 'flex', gap: '12px', marginTop: '20px' }}>
              <button onClick={() => { setAthleteStep('profile'); loadProfile(athlete.athlete_id); }}
                className="btn btn-primary" style={{ flex: 1, padding: '14px' }}>
                View Updated Profile
              </button>
              <button onClick={() => setAthleteStep('select_test')}
                className="btn btn-secondary" style={{ padding: '14px' }}>
                Take Another Test
              </button>
            </div>
          </div>
        )}
      </main>

      <footer style={{
        textAlign: 'center', padding: '18px', fontSize: '0.72rem',
        color: 'var(--text-dim)', borderTop: '1px solid var(--border-glass)',
        background: 'rgba(7, 10, 18, 0.9)'
      }}>
        National Sports Talent Assessment Platform • SIH 25073 • Powered by AI + MediaPipe
      </footer>
    </div>
  );
}
