import React, { useState } from 'react';
import { UserPlus, LogIn, KeyRound, ArrowLeft, ShieldCheck, Eye, EyeOff, Send, User, Building2 } from 'lucide-react';
import { api } from '../utils/api';

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
  padding: '12px 14px',
  borderRadius: 'var(--radius-md)',
  background: 'rgba(255, 255, 255, 0.05)',
  border: '1px solid var(--border-glass)',
  color: 'var(--text-main)',
  fontSize: '0.92rem',
  fontFamily: 'var(--font-body)',
  outline: 'none',
  transition: 'border-color 0.2s ease'
};

const labelStyle = {
  display: 'block',
  fontSize: '0.78rem',
  color: 'var(--text-muted)',
  marginBottom: '5px',
  fontWeight: 600,
  letterSpacing: '0.02em'
};

export default function AuthScreen({ onAuthenticated, t }) {
  const [mode, setMode] = useState('login'); // 'login' | 'register' | 'forgot' | 'otp_verify'
  const [accountType, setAccountType] = useState('athlete'); // 'athlete' | 'official'
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [showPassword, setShowPassword] = useState(false);

  // Login state
  const [loginId, setLoginId] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [officialEmail, setOfficialEmail] = useState('');

  // Athlete registration state
  const [regForm, setRegForm] = useState({
    name: '', age: '', category: 'Male', state: '', district: '',
    school: '', sports_interest: '', height_cm: '', weight_kg: '',
    phone: '', email: '', password: '', confirmPassword: ''
  });
  const [registeredId, setRegisteredId] = useState(null);

  // Official registration state
  const [offForm, setOffForm] = useState({
    name: '', email: '', organization: '', phone: '',
    password: '', confirmPassword: '', signup_key: ''
  });

  // Forgot password state
  const [resetAthleteId, setResetAthleteId] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [otpSentData, setOtpSentData] = useState(null);

  const clearMessages = () => { setError(null); setSuccess(null); };
  const switchAccountType = (type) => { setAccountType(type); clearMessages(); };

  // ─── LOGIN ───
  const handleLogin = async (e) => {
    e.preventDefault();
    clearMessages();
    setLoading(true);
    try {
      if (accountType === 'official') {
        if (!officialEmail.trim() || !loginPassword) {
          setError('Please enter your official email and password.');
          setLoading(false);
          return;
        }
        const data = await api.loginOfficial(officialEmail.trim(), loginPassword);
        onAuthenticated(data.official, 'official');
      } else {
        if (!loginId.trim() || !loginPassword) {
          setError('Please enter your Athlete ID and password.');
          setLoading(false);
          return;
        }
        const data = await api.loginAthlete(loginId.trim(), loginPassword);
        onAuthenticated(data.athlete, 'athlete');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ─── ATHLETE REGISTER ───
  const handleRegister = async (e) => {
    e.preventDefault();
    clearMessages();
    if (!regForm.name || !regForm.age || !regForm.state || !regForm.district || !regForm.password) {
      setError('Please fill all required fields.');
      return;
    }
    if (regForm.password.length < 4) {
      setError('Password must be at least 4 characters.');
      return;
    }
    if (regForm.password !== regForm.confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      const payload = {
        name: regForm.name.trim(),
        age: parseInt(regForm.age),
        category: regForm.category,
        state: regForm.state,
        district: regForm.district.trim(),
        school: regForm.school.trim() || null,
        sports_interest: regForm.sports_interest.trim() || null,
        height_cm: regForm.height_cm ? parseFloat(regForm.height_cm) : null,
        weight_kg: regForm.weight_kg ? parseFloat(regForm.weight_kg) : null,
        phone: regForm.phone.trim() || null,
        email: regForm.email.trim() || null,
        password: regForm.password
      };
      const data = await api.registerAthlete(payload);
      setRegisteredId(data.athlete.athlete_id);
      setSuccess(`Registration successful! Your Athlete ID is: ${data.athlete.athlete_id}`);
      setTimeout(() => onAuthenticated(data.athlete, 'athlete'), 2500);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ─── OFFICIAL REGISTER ───
  const handleOfficialRegister = async (e) => {
    e.preventDefault();
    clearMessages();
    if (!offForm.name || !offForm.email || !offForm.password || !offForm.signup_key) {
      setError('Please fill name, email, password and the official enrolment key.');
      return;
    }
    if (offForm.password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    if (offForm.password !== offForm.confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      const payload = {
        name: offForm.name.trim(),
        email: offForm.email.trim(),
        organization: offForm.organization.trim() || null,
        phone: offForm.phone.trim() || null,
        password: offForm.password,
        signup_key: offForm.signup_key.trim()
      };
      const data = await api.registerOfficial(payload);
      setSuccess('Official account created! Entering the scout dashboard...');
      setTimeout(() => onAuthenticated(data.official, 'official'), 1500);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ─── REQUEST OTP ───
  const handleRequestOTP = async (e) => {
    e.preventDefault();
    clearMessages();
    if (!resetAthleteId.trim()) {
      setError('Please enter your Athlete ID, Phone Number, or Email.');
      return;
    }
    setLoading(true);
    try {
      const data = await api.requestOTP(resetAthleteId.trim());
      setOtpSentData(data);
      if (data.athlete_id) setResetAthleteId(data.athlete_id);
      if (data.otp_code) setOtpCode(data.otp_code);
      setMode('otp_verify');
      if (data.delivered) {
        setSuccess(data.message || `OTP sent via SMS to ${data.contact}. Check your mobile phone.`);
      } else {
        setError(data.message || 'Could not deliver the SMS. See details below.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ─── VERIFY OTP & RESET ───
  const handleResetPassword = async (e) => {
    e.preventDefault();
    clearMessages();
    if (!otpCode || !newPassword) {
      setError('Please enter the OTP and your new password.');
      return;
    }
    if (newPassword.length < 4) {
      setError('New password must be at least 4 characters.');
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      await api.resetPassword(resetAthleteId.trim(), otpCode.trim(), newPassword);
      setSuccess('Password reset successful! You can now login.');
      setTimeout(() => {
        setMode('login');
        setAccountType('athlete');
        setLoginId(resetAthleteId);
        clearMessages();
      }, 2000);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const isOfficial = accountType === 'official';
  const showRoleToggle = mode === 'login' || mode === 'register';

  const roleBtnStyle = (active) => ({
    flex: 1, padding: '9px', borderRadius: 'var(--radius-md)', cursor: 'pointer',
    fontSize: '0.82rem', fontWeight: 700, display: 'flex', alignItems: 'center',
    justifyContent: 'center', gap: '6px', transition: 'all 0.2s ease',
    border: active ? '1px solid var(--primary)' : '1px solid var(--border-glass)',
    background: active ? 'rgba(0, 242, 254, 0.12)' : 'transparent',
    color: active ? 'var(--primary)' : 'var(--text-muted)'
  });

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
      <div className="glass-panel" style={{ maxWidth: '520px', width: '100%', padding: '36px 32px' }}>

        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '20px' }}>
          <div style={{
            width: '60px', height: '60px', borderRadius: '50%',
            background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: '14px', boxShadow: '0 0 30px rgba(0, 242, 254, 0.4)'
          }}>
            {mode === 'login' && <LogIn size={28} color="#070a12" />}
            {mode === 'register' && <UserPlus size={28} color="#070a12" />}
            {(mode === 'forgot' || mode === 'otp_verify') && <KeyRound size={28} color="#070a12" />}
          </div>
          <h2 style={{ fontSize: '1.45rem', marginBottom: '4px' }}>
            {mode === 'login' && (isOfficial ? 'Scout / Official Login' : 'Athlete Login')}
            {mode === 'register' && (isOfficial ? 'Register Official Account' : 'New Athlete Registration')}
            {mode === 'forgot' && 'Reset Password'}
            {mode === 'otp_verify' && 'Verify OTP'}
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
            {mode === 'login' && (isOfficial
              ? 'Access the talent discovery dashboard.'
              : 'Sign in to access your sports profile and assessments.')}
            {mode === 'register' && (isOfficial
              ? 'For SAI scouts and officials (enrolment key required).'
              : 'Create your digital sports identity for talent discovery.')}
            {mode === 'forgot' && 'Enter your Athlete ID to receive a reset OTP.'}
            {mode === 'otp_verify' && 'Enter the OTP and set your new password.'}
          </p>
        </div>

        {/* Role toggle (Athlete / Official) */}
        {showRoleToggle && (
          <div style={{ display: 'flex', gap: '8px', marginBottom: '18px' }}>
            <button type="button" onClick={() => switchAccountType('athlete')} style={roleBtnStyle(!isOfficial)}>
              <User size={16} /> Athlete
            </button>
            <button type="button" onClick={() => switchAccountType('official')} style={roleBtnStyle(isOfficial)}>
              <Building2 size={16} /> Scout / Official
            </button>
          </div>
        )}

        {/* Error / Success Messages */}
        {error && (
          <div style={{ padding: '10px 14px', background: 'rgba(255, 56, 92, 0.12)', color: 'var(--accent-red)', borderRadius: 'var(--radius-md)', marginBottom: '16px', fontSize: '0.83rem', border: '1px solid rgba(255, 56, 92, 0.3)' }}>
            {error}
          </div>
        )}
        {success && (
          <div style={{ padding: '10px 14px', background: 'rgba(0, 245, 160, 0.12)', color: 'var(--accent-green)', borderRadius: 'var(--radius-md)', marginBottom: '16px', fontSize: '0.83rem', border: '1px solid rgba(0, 245, 160, 0.3)' }}>
            {success}
          </div>
        )}

        {/* ═══ LOGIN FORM ═══ */}
        {mode === 'login' && (
          <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {isOfficial ? (
              <div>
                <label style={labelStyle}>Official Email</label>
                <input type="email" required placeholder="official@sai.gov.in" value={officialEmail}
                  onChange={(e) => setOfficialEmail(e.target.value)}
                  style={inputStyle}
                />
              </div>
            ) : (
              <div>
                <label style={labelStyle}>Athlete ID</label>
                <input type="text" required placeholder="ATH-2026-XXXXXX" value={loginId}
                  onChange={(e) => setLoginId(e.target.value)}
                  style={inputStyle}
                />
              </div>
            )}
            <div>
              <label style={labelStyle}>Password</label>
              <div style={{ position: 'relative' }}>
                <input type={showPassword ? 'text' : 'password'} required placeholder="Enter your password" value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  style={{ ...inputStyle, paddingRight: '44px' }}
                />
                <button type="button" onClick={() => setShowPassword(!showPassword)}
                  style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '4px' }}>
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
            <button type="submit" disabled={loading} className="btn btn-primary btn-pill"
              style={{ marginTop: '6px', padding: '14px', width: '100%', fontSize: '1rem' }}>
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
              {!isOfficial && (
                <button type="button" onClick={() => { setMode('forgot'); clearMessages(); }}
                  style={{ background: 'none', border: 'none', color: 'var(--primary)', fontSize: '0.82rem', cursor: 'pointer', fontWeight: 600 }}>
                  Forgot Password?
                </button>
              )}
              <button type="button" onClick={() => { setMode('register'); clearMessages(); }}
                style={{ background: 'none', border: 'none', color: 'var(--accent-green)', fontSize: '0.82rem', cursor: 'pointer', fontWeight: 600, marginLeft: 'auto' }}>
                New? Register here
              </button>
            </div>
          </form>
        )}

        {/* ═══ OFFICIAL REGISTER FORM ═══ */}
        {mode === 'register' && isOfficial && (
          <form onSubmit={handleOfficialRegister} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <label style={labelStyle}>Full Name *</label>
              <input type="text" required placeholder="Your name" value={offForm.name}
                onChange={(e) => setOffForm({ ...offForm, name: e.target.value })} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Official Email * (used to log in)</label>
              <input type="email" required placeholder="official@sai.gov.in" value={offForm.email}
                onChange={(e) => setOffForm({ ...offForm, email: e.target.value })} style={inputStyle} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label style={labelStyle}>Organization</label>
                <input type="text" placeholder="e.g. SAI" value={offForm.organization}
                  onChange={(e) => setOffForm({ ...offForm, organization: e.target.value })} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>Phone</label>
                <input type="tel" placeholder="Optional" value={offForm.phone}
                  onChange={(e) => setOffForm({ ...offForm, phone: e.target.value })} style={inputStyle} />
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label style={labelStyle}>Password * (min 6)</label>
                <input type="password" required placeholder="Password" value={offForm.password}
                  onChange={(e) => setOffForm({ ...offForm, password: e.target.value })} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>Confirm Password *</label>
                <input type="password" required placeholder="Re-enter" value={offForm.confirmPassword}
                  onChange={(e) => setOffForm({ ...offForm, confirmPassword: e.target.value })} style={inputStyle} />
              </div>
            </div>
            <div>
              <label style={labelStyle}>Official Enrolment Key *</label>
              <input type="text" required placeholder="Provided by your administrator" value={offForm.signup_key}
                onChange={(e) => setOffForm({ ...offForm, signup_key: e.target.value })} style={inputStyle} />
            </div>
            <button type="submit" disabled={loading} className="btn btn-accent btn-pill"
              style={{ marginTop: '4px', padding: '14px', width: '100%', fontSize: '1rem' }}>
              {loading ? 'Creating Account...' : 'Register Official Account'}
            </button>
            <div style={{ textAlign: 'center', marginTop: '2px' }}>
              <button type="button" onClick={() => { setMode('login'); clearMessages(); }}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '0.82rem', cursor: 'pointer' }}>
                <ArrowLeft size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} />
                Already registered? Sign In
              </button>
            </div>
          </form>
        )}

        {/* ═══ ATHLETE REGISTER FORM ═══ */}
        {mode === 'register' && !isOfficial && (
          <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <label style={labelStyle}>Full Name *</label>
              <input type="text" required placeholder="Enter your full name" value={regForm.name}
                onChange={(e) => setRegForm({ ...regForm, name: e.target.value })}
                style={inputStyle}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label style={labelStyle}>Age *</label>
                <input type="number" min="6" max="60" required placeholder="Age" value={regForm.age}
                  onChange={(e) => setRegForm({ ...regForm, age: e.target.value })}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Gender *</label>
                <select value={regForm.category}
                  onChange={(e) => setRegForm({ ...regForm, category: e.target.value })}
                  style={{ ...inputStyle, background: '#0d1424' }}>
                  <option value="Male">Male</option>
                  <option value="Female">Female</option>
                  <option value="General">General</option>
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label style={labelStyle}>State *</label>
                <select required value={regForm.state}
                  onChange={(e) => setRegForm({ ...regForm, state: e.target.value })}
                  style={{ ...inputStyle, background: '#0d1424' }}>
                  <option value="">Select State</option>
                  {INDIAN_STATES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label style={labelStyle}>District *</label>
                <input type="text" required placeholder="Your district" value={regForm.district}
                  onChange={(e) => setRegForm({ ...regForm, district: e.target.value })}
                  style={inputStyle}
                />
              </div>
            </div>

            <div>
              <label style={labelStyle}>School / College / Academy</label>
              <input type="text" placeholder="Optional" value={regForm.school}
                onChange={(e) => setRegForm({ ...regForm, school: e.target.value })}
                style={inputStyle}
              />
            </div>

            <div>
              <label style={labelStyle}>Sports Interest</label>
              <input type="text" placeholder="e.g. Athletics, Football, Kabaddi" value={regForm.sports_interest}
                onChange={(e) => setRegForm({ ...regForm, sports_interest: e.target.value })}
                style={inputStyle}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label style={labelStyle}>Height (cm)</label>
                <input type="number" min="50" max="250" step="0.1" placeholder="e.g. 165" value={regForm.height_cm}
                  onChange={(e) => setRegForm({ ...regForm, height_cm: e.target.value })}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Weight (kg)</label>
                <input type="number" min="10" max="200" step="0.1" placeholder="e.g. 55" value={regForm.weight_kg}
                  onChange={(e) => setRegForm({ ...regForm, weight_kg: e.target.value })}
                  style={inputStyle}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label style={labelStyle}>Phone</label>
                <input type="tel" placeholder="Mobile number" value={regForm.phone}
                  onChange={(e) => setRegForm({ ...regForm, phone: e.target.value })}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Email</label>
                <input type="email" placeholder="Email address" value={regForm.email}
                  onChange={(e) => setRegForm({ ...regForm, email: e.target.value })}
                  style={inputStyle}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label style={labelStyle}>Password *</label>
                <input type="password" required placeholder="Min 4 characters" value={regForm.password}
                  onChange={(e) => setRegForm({ ...regForm, password: e.target.value })}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Confirm Password *</label>
                <input type="password" required placeholder="Re-enter password" value={regForm.confirmPassword}
                  onChange={(e) => setRegForm({ ...regForm, confirmPassword: e.target.value })}
                  style={inputStyle}
                />
              </div>
            </div>

            {registeredId && (
              <div style={{ padding: '12px', background: 'rgba(0, 242, 254, 0.1)', border: '1px solid rgba(0, 242, 254, 0.3)', borderRadius: 'var(--radius-md)', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Your Athlete ID (save this!)</div>
                <div className="mono" style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--primary)', letterSpacing: '0.03em' }}>{registeredId}</div>
              </div>
            )}

            <button type="submit" disabled={loading} className="btn btn-accent btn-pill"
              style={{ marginTop: '4px', padding: '14px', width: '100%', fontSize: '1rem' }}>
              {loading ? 'Creating Account...' : 'Register & Enter Platform'}
            </button>
            <div style={{ textAlign: 'center', marginTop: '2px' }}>
              <button type="button" onClick={() => { setMode('login'); clearMessages(); }}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '0.82rem', cursor: 'pointer' }}>
                <ArrowLeft size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} />
                Already registered? Sign In
              </button>
            </div>
          </form>
        )}

        {/* ═══ FORGOT PASSWORD ═══ */}
        {mode === 'forgot' && (
          <form onSubmit={handleRequestOTP} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={labelStyle}>Athlete ID / Mobile Number / Email</label>
              <input type="text" required placeholder="ATH-2026-XXXXXX or 9876543210" value={resetAthleteId}
                onChange={(e) => setResetAthleteId(e.target.value)}
                style={inputStyle}
              />
            </div>
            <button type="submit" disabled={loading} className="btn btn-primary btn-pill"
              style={{ padding: '14px', width: '100%', fontSize: '0.95rem' }}>
              <Send size={16} />
              {loading ? 'Sending OTP via SMS...' : 'Send Reset OTP via SMS'}
            </button>
            <div style={{ textAlign: 'center' }}>
              <button type="button" onClick={() => { setMode('login'); clearMessages(); }}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '0.82rem', cursor: 'pointer' }}>
                <ArrowLeft size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} />
                Back to Login
              </button>
            </div>
          </form>
        )}

        {/* ═══ OTP VERIFICATION & NEW PASSWORD ═══ */}
        {mode === 'otp_verify' && (
          <form onSubmit={handleResetPassword} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {otpSentData && (
              <div style={{ padding: '14px', background: 'rgba(0, 242, 254, 0.08)', border: '1px solid rgba(0, 242, 254, 0.25)', borderRadius: 'var(--radius-md)', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span>
                    <ShieldCheck size={16} style={{ verticalAlign: 'middle', color: 'var(--primary)', marginRight: '6px' }} />
                    {otpSentData.delivered ? 'SMS sent to: ' : 'Recipient: '}
                    <strong style={{ color: 'var(--text-main)' }}>{otpSentData.contact}</strong>
                  </span>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: otpSentData.delivered ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                    {otpSentData.delivered ? `✓ Sent via ${otpSentData.delivery_provider}` : '⚠ Not delivered'}
                  </span>
                </div>

                {!otpSentData.delivered && otpSentData.debug_note && (
                  <div style={{ fontSize: '0.72rem', color: 'var(--accent-red)', marginTop: '2px', lineHeight: 1.4 }}>
                    {otpSentData.debug_note}
                  </div>
                )}

                {otpSentData.otp_code && (
                  <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(0,0,0,0.3)', padding: '6px 10px', borderRadius: 'var(--radius-sm)' }}>
                    <span style={{ fontSize: '0.78rem' }}>OTP Code: <strong className="mono" style={{ color: 'var(--accent-green)', fontSize: '1.05rem', letterSpacing: '0.1em' }}>{otpSentData.otp_code}</strong></span>
                    <button
                      type="button"
                      onClick={() => setOtpCode(otpSentData.otp_code)}
                      style={{ background: 'var(--primary)', color: '#000', border: 'none', padding: '3px 8px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer' }}
                    >
                      ⚡ Auto-fill OTP
                    </button>
                  </div>
                )}

                <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '6px' }}>Expires in {otpSentData.expires_in_minutes} minutes</div>
              </div>
            )}
            <div>
              <label style={labelStyle}>6-Digit OTP</label>
              <input type="text" required placeholder="Enter OTP" maxLength={6} value={otpCode}
                onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                style={{ ...inputStyle, textAlign: 'center', fontSize: '1.3rem', letterSpacing: '0.3em', fontFamily: 'var(--font-mono)' }}
              />
            </div>
            <div>
              <label style={labelStyle}>New Password</label>
              <input type="password" required placeholder="Min 4 characters" value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>Confirm New Password</label>
              <input type="password" required placeholder="Re-enter new password" value={confirmNewPassword}
                onChange={(e) => setConfirmNewPassword(e.target.value)}
                style={inputStyle}
              />
            </div>
            <button type="submit" disabled={loading} className="btn btn-accent btn-pill"
              style={{ padding: '14px', width: '100%', fontSize: '0.95rem' }}>
              {loading ? 'Resetting...' : 'Reset Password'}
            </button>
            <div style={{ textAlign: 'center' }}>
              <button type="button" onClick={() => { setMode('forgot'); clearMessages(); setOtpSentData(null); }}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '0.82rem', cursor: 'pointer' }}>
                <ArrowLeft size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} />
                Resend OTP
              </button>
            </div>
          </form>
        )}

      </div>
    </div>
  );
}
