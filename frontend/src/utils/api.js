/**
 * Backend REST API client — connects to real FastAPI backend.
 * No dummy data. All responses come from the SQLite database.
 */

const API_BASE = '/api/v1';

async function handleResponse(res) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export const api = {
  // Register a new athlete (with password)
  async registerAthlete(data) {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return handleResponse(res);
  },

  // Login with Athlete ID + Password
  async loginAthlete(athleteId, password) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ athlete_id: athleteId, password })
    });
    return handleResponse(res);
  },

  // Request OTP for password reset
  async requestOTP(athleteId) {
    const res = await fetch(`${API_BASE}/auth/request-otp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ athlete_id: athleteId })
    });
    return handleResponse(res);
  },

  // Verify OTP and set new password
  async resetPassword(athleteId, otpCode, newPassword) {
    const res = await fetch(`${API_BASE}/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ athlete_id: athleteId, otp_code: otpCode, new_password: newPassword })
    });
    return handleResponse(res);
  },

  // Get athlete full profile + performance index + assessment history
  async getAthleteProfile(athleteId) {
    const res = await fetch(`${API_BASE}/athlete/profile/${athleteId}`);
    return handleResponse(res);
  },

  // Upload real video file for AI MediaPipe processing
  async uploadVideo(file, athleteId, testType, referenceHeightCm = 170.0) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('athlete_id', athleteId);
    formData.append('test_type', testType);
    formData.append('reference_height_cm', referenceHeightCm.toString());

    const res = await fetch(`${API_BASE}/assessment/upload-video`, {
      method: 'POST',
      body: formData
    });
    return handleResponse(res);
  }
};
