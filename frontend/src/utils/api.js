/**
 * Backend REST API client — connects to real FastAPI backend.
 * No dummy data. All responses come from the SQLite database.
 *
 * Auth: a JWT is stored in localStorage after login/registration and attached as a
 * Bearer token on every request. A 401 clears the session and notifies the app.
 */

const API_BASE = '/api/v1';
const TOKEN_KEY = 'auth_token';
const ACCOUNT_TYPE_KEY = 'account_type';

import { enqueueAssessment, flushQueue } from './offlineQueue';

// ─── Token storage ───
export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
export function getAccountType() {
  return localStorage.getItem(ACCOUNT_TYPE_KEY);
}
function setAuth(token, accountType) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(ACCOUNT_TYPE_KEY, accountType);
}
export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ACCOUNT_TYPE_KEY);
  localStorage.removeItem('athlete_id');
  localStorage.removeItem('official_data');
}

function authHeaders(extra = {}) {
  const token = getToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : { ...extra };
}

async function handleResponse(res) {
  if (res.status === 401 && getToken()) {
    // Token invalid/expired — force a clean re-login.
    clearAuth();
    window.dispatchEvent(new CustomEvent('auth:unauthorized'));
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export const api = {
  // Register a new athlete (with password) → stores token, returns TokenResponse
  async registerAthlete(data) {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    const result = await handleResponse(res);
    setAuth(result.access_token, 'athlete');
    localStorage.setItem('athlete_id', result.athlete.athlete_id);
    return result;
  },

  // Login with Athlete ID + Password → stores token, returns TokenResponse
  async loginAthlete(athleteId, password) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ athlete_id: athleteId, password })
    });
    const result = await handleResponse(res);
    setAuth(result.access_token, 'athlete');
    localStorage.setItem('athlete_id', result.athlete.athlete_id);
    return result;
  },

  // Register a scout / official account (requires the shared enrolment key)
  async registerOfficial(data) {
    const res = await fetch(`${API_BASE}/auth/official/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    const result = await handleResponse(res);
    setAuth(result.access_token, 'official');
    localStorage.setItem('official_data', JSON.stringify(result.official));
    return result;
  },

  // Login as a scout / official by email + password
  async loginOfficial(email, password) {
    const res = await fetch(`${API_BASE}/auth/official/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const result = await handleResponse(res);
    setAuth(result.access_token, 'official');
    localStorage.setItem('official_data', JSON.stringify(result.official));
    return result;
  },

  // Request OTP for password reset (public)
  async requestOTP(athleteId) {
    const res = await fetch(`${API_BASE}/auth/request-otp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ athlete_id: athleteId })
    });
    return handleResponse(res);
  },

  // Verify OTP and set new password (public)
  async resetPassword(athleteId, otpCode, newPassword) {
    const res = await fetch(`${API_BASE}/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ athlete_id: athleteId, otp_code: otpCode, new_password: newPassword })
    });
    return handleResponse(res);
  },

  // Get athlete full profile + performance index + assessment history (auth required)
  async getAthleteProfile(athleteId) {
    const res = await fetch(`${API_BASE}/athlete/profile/${athleteId}`, {
      headers: authHeaders()
    });
    return handleResponse(res);
  },

  // Scout talent-discovery search (official token required)
  async scoutSearch(filters = {}) {
    const params = new URLSearchParams();
    if (filters.state) params.append('state', filters.state);
    if (filters.district) params.append('district', filters.district);
    if (filters.min_overall_index != null && filters.min_overall_index !== '')
      params.append('min_overall_index', filters.min_overall_index);
    if (filters.test_type) params.append('test_type', filters.test_type);
    const qs = params.toString();
    const res = await fetch(`${API_BASE}/scout/search${qs ? `?${qs}` : ''}`, {
      headers: authHeaders()
    });
    return handleResponse(res);
  },

  // Manual / assisted result entry for tests that can't be reliably measured by CV
  // from a single phone clip (50m dash, 600m run, sit & reach) or via tape (broad jump).
  // Validated against the registry's plausibility bounds server-side. (auth required)
  async submitManualEntry(athleteId, testType, rawValue, officiated = false, notes = null) {
    const res = await fetch(`${API_BASE}/assessment/manual-entry`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        athlete_id: athleteId,
        test_type: testType,
        raw_value: rawValue,
        officiated,
        notes
      })
    });
    return handleResponse(res);
  },

  // Live-capture camera alignment check. Posts ONE downscaled JPEG frame + the test
  // type to the backend MediaPipe pose engine and returns real guidance:
  //   { cv_available, ready, full_body_visible, centered, distance_ok, orientation_ok,
  //     orientation, off_center_x, off_center_y, alignment_score, instruction, ... }.
  // Throws on network failure so the caller can fall back to on-device checks. Only used
  // by the live webcam path — the upload-video path is unaffected. (auth required)
  async cameraCheck(frameBlob, testType) {
    const formData = new FormData();
    formData.append('file', frameBlob, 'frame.jpg');
    formData.append('test_type', testType);
    // Note: do NOT set Content-Type — the browser sets the multipart boundary.
    const res = await fetch(`${API_BASE}/assessment/camera-check`, {
      method: 'POST',
      headers: authHeaders(),
      body: formData
    });
    return handleResponse(res);
  },

  // Raw multipart upload for AI MediaPipe processing — throws on network failure
  // or server error. (auth required)
  async uploadVideoRaw(file, athleteId, testType, referenceHeightCm = 170.0) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('athlete_id', athleteId);
    formData.append('test_type', testType);
    formData.append('reference_height_cm', referenceHeightCm.toString());

    // Note: do NOT set Content-Type — the browser sets the multipart boundary.
    const res = await fetch(`${API_BASE}/assessment/upload-video`, {
      method: 'POST',
      headers: authHeaders(),
      body: formData
    });
    return handleResponse(res);
  },

  // Offline-aware upload: if the network is unavailable the video is stored in
  // IndexedDB and submitted automatically on reconnect. Returns {queued:true} then.
  async uploadVideo(file, athleteId, testType, referenceHeightCm = 170.0) {
    try {
      if (typeof navigator !== 'undefined' && navigator.onLine === false) {
        throw new TypeError('offline');
      }
      return await this.uploadVideoRaw(file, athleteId, testType, referenceHeightCm);
    } catch (err) {
      const networkFailure = (typeof navigator !== 'undefined' && navigator.onLine === false)
        || err instanceof TypeError; // fetch() throws TypeError when unreachable
      if (networkFailure) {
        await enqueueAssessment({
          file,
          athlete_id: athleteId,
          test_type: testType,
          reference_height_cm: referenceHeightCm
        });
        return { queued: true };
      }
      throw err; // genuine server error (bad video, 4xx/5xx, expired token) — surface it
    }
  },

  // Replay any queued offline assessments. Bound to app boot and the 'online' event.
  async flushOfflineQueue() {
    if (!getToken() || getAccountType() !== 'athlete') return 0;
    return flushQueue((item) => {
      const file = item.file instanceof Blob
        ? item.file
        : new File([item.file], 'assessment.webm', { type: 'video/webm' });
      return this.uploadVideoRaw(
        file, item.athlete_id, item.test_type, item.reference_height_cm ?? 170.0
      );
    });
  },

  // Download the verified PDF certificate for one assessment (auth required).
  // Fetches the PDF as a blob and triggers a browser download.
  async downloadCertificate(assessmentId) {
    const res = await fetch(`${API_BASE}/assessment/${assessmentId}/certificate`, {
      headers: authHeaders()
    });
    if (res.status === 401 && getToken()) {
      clearAuth();
      window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Certificate download failed (${res.status})`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `SAI_Certificate_${assessmentId}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }
};
