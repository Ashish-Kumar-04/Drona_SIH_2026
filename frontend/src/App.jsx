import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import AuthScreen from './components/AuthScreen';
import TestSelection from './components/TestSelection';
import CameraGuidance from './components/CameraGuidance';
import VideoUploader from './components/VideoUploader';
import ManualEntryForm from './components/ManualEntryForm';
import PoseVideoPlayer from './components/PoseVideoPlayer';
import LiveMetricsHUD from './components/LiveMetricsHUD';
import AthleteProfileView from './components/AthleteProfileView';
import ScoutDashboard from './components/ScoutDashboard';
import { translations } from './utils/i18n';
import { api, getAccountType, clearAuth } from './utils/api';
import { isManualTest } from './utils/tests';
import { ArrowLeft, Download } from 'lucide-react';

export default function App() {
  const [lang, setLang] = useState('en');
  const [theme, setTheme] = useState(() => localStorage.getItem('app_theme') || 'dark');
  const [accountType, setAccountType] = useState(null); // 'athlete' | 'official' | null
  const [athlete, setAthlete] = useState(null);
  const [official, setOfficial] = useState(null);
  const [profileData, setProfileData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.body.setAttribute('data-theme', theme);
    localStorage.setItem('app_theme', theme);
  }, [theme]);

  // Athlete workflow: 'profile' | 'select_test' | 'guidance' | 'assessment' | 'manual_entry' | 'results'
  const [athleteStep, setAthleteStep] = useState('profile');
  const [selectedTest, setSelectedTest] = useState('vertical_jump');
  const [assessmentMode, setAssessmentMode] = useState('file');
  const [latestAssessmentResult, setLatestAssessmentResult] = useState(null);
  const [activeVideoSrc, setActiveVideoSrc] = useState(null);

  const t = translations[lang] || translations.en;

  // ─── Reset all session state to logged-out ───
  const resetSession = () => {
    setAccountType(null);
    setAthlete(null);
    setOfficial(null);
    setProfileData(null);
    setAthleteStep('profile');
    setLatestAssessmentResult(null);
    setActiveVideoSrc(null);
  };

  // ─── Load athlete profile from database ───
  const loadProfile = async (athleteId) => {
    try {
      const data = await api.getAthleteProfile(athleteId);
      setProfileData(data);
      setAthlete(data.athlete);
    } catch (err) {
      console.error('Failed to load profile:', err);
      // If profile load fails, clear the session cleanly.
      clearAuth();
      resetSession();
    }
  };

  // ─── Restore existing session on app load (based on stored account type) ───
  useEffect(() => {
    const type = getAccountType();
    if (type === 'official') {
      try {
        const stored = JSON.parse(localStorage.getItem('official_data') || 'null');
        if (stored) {
          setOfficial(stored);
          setAccountType('official');
        }
      } catch (_) { /* ignore malformed cache */ }
      setLoading(false);
    } else if (type === 'athlete') {
      const savedId = localStorage.getItem('athlete_id');
      if (savedId) {
        setAccountType('athlete');
        loadProfile(savedId).finally(() => setLoading(false));
      } else {
        setLoading(false);
      }
    } else {
      setLoading(false);
    }
  }, []);

  // ─── Force logout when a request reports the token is invalid/expired ───
  useEffect(() => {
    const onUnauthorized = () => resetSession();
    window.addEventListener('auth:unauthorized', onUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', onUnauthorized);
  }, []);

  // ─── Auth handlers ───
  const handleAuthenticated = (data, type) => {
    setAccountType(type);
    if (type === 'official') {
      setOfficial(data);
    } else {
      setAthlete(data);
      loadProfile(data.athlete_id);
      setAthleteStep('profile');
    }
  };

  const handleLogout = () => {
    clearAuth();
    resetSession();
  };

  // ─── Test flow handlers ───
  const handleSelectTest = (testId) => {
    setSelectedTest(testId);
    // Manual-capture tests (50m dash, 600m run, sit & reach) skip the camera
    // guidance/upload flow and go straight to an officiated result-entry form.
    setAthleteStep(isManualTest(testId) ? 'manual_entry' : 'guidance');
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

  // ─── Not logged in or profile unresolved → show Auth with Navbar & Footer ───
  if (!accountType || (accountType === 'athlete' && !athlete)) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        <Navbar
          user={null}
          onLogout={handleLogout}
          lang={lang} setLang={setLang}
          theme={theme} setTheme={setTheme}
          t={t}
        />
        <main style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px 20px' }}>
          <AuthScreen onAuthenticated={handleAuthenticated} t={t} />
        </main>
        <footer style={{
          textAlign: 'center', padding: '18px', fontSize: '0.90rem',
          color: 'var(--text-dim)', borderTop: '1px solid var(--border-glass)',
          background: 'var(--bg-footer)'
        }}>
          National Sports Talent Assessment Platform • Made With ❤️ By Team InnoVerse 
                                 <center>&copy; All Rights Reserved</center>
        </footer>
      </div>
    );
  }

  // ─── Official / Scout → Talent Discovery Dashboard ───
  if (accountType === 'official') {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        <Navbar
          user={official ? { name: official.name, id: official.official_id } : null}
          roleLabel={t.roles.scout}
          onLogout={handleLogout}
          lang={lang} setLang={setLang}
          theme={theme} setTheme={setTheme}
          t={t}
        />
        <main style={{ flex: 1, padding: '24px 20px', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
          <ScoutDashboard official={official} t={t} lang={lang} />
        </main>
        <footer style={{
          textAlign: 'center', padding: '18px', fontSize: '0.90rem',
          color: 'var(--text-dim)', borderTop: '1px solid var(--border-glass)',
          background: 'var(--bg-footer)'
        }}>
         National Sports Talent Assessment Platform • Made With ❤️ By Team InnoVerse 
                                 <center>&copy; All Rights Reserved</center>
        </footer>
      </div>
    );
  }

  // ─── Logged in → Athlete Dashboard ───
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar athlete={athlete} onLogout={handleLogout} lang={lang} setLang={setLang} theme={theme} setTheme={setTheme} t={t} />

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

        {/* Step 3: Camera Guidance / Method Selection */}
        {athleteStep === 'guidance' && (
          <CameraGuidance
            onChooseUpload={() => { setAssessmentMode('file'); setAthleteStep('assessment'); }}
            onChooseWebcam={() => { setAssessmentMode('webcam'); setAthleteStep('assessment'); }}
            testTitle={selectedTest}
            t={t}
          />
        )}

        {/* Step 4: Video Upload & Assessment */}
        {athleteStep === 'assessment' && (
          <VideoUploader
            athleteId={athlete.athlete_id}
            testType={selectedTest}
            initialMode={assessmentMode}
            onProcessingComplete={handleAssessmentComplete}
            t={t}
          />
        )}

        {/* Step 4b: Manual / assisted result entry (non-CV tests) */}
        {athleteStep === 'manual_entry' && (
          <ManualEntryForm
            athleteId={athlete.athlete_id}
            testType={selectedTest}
            onComplete={() => { setAthleteStep('profile'); loadProfile(athlete.athlete_id); }}
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

            <div style={{ display: 'flex', gap: '12px', marginTop: '20px', flexWrap: 'wrap' }}>
              <button onClick={() => { setAthleteStep('profile'); loadProfile(athlete.athlete_id); }}
                className="btn btn-primary" style={{ flex: 1, minWidth: '160px', padding: '14px' }}>
                View Updated Profile
              </button>
              <button
                onClick={() => api.downloadCertificate(latestAssessmentResult.assessment_id)
                  .catch(err => alert(err.message || 'Certificate download failed.'))}
                className="btn btn-secondary" style={{ padding: '14px' }}>
                <Download size={16} /> {t.certificate || 'Download Certificate'}
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
        textAlign: 'center', padding: '18px', fontSize: '0.90rem',
        color: 'var(--text-dim)', borderTop: '1px solid var(--border-glass)',
        background: 'var(--bg-footer)'
      }}>
        National Sports Talent Assessment Platform • Made With ❤️ By Team InnoVerse 
                                 <center>&copy; All Rights Reserved</center>
      </footer>
    </div>
  );
}
