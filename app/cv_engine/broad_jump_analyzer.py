"""
Standing Broad Jump (Standing Long Jump) Detection & Distance Estimation Engine.
Companion to Section 11 of the SIH 25073 specification for the horizontal explosive-power test.

NOTE ON ACCURACY: horizontal distance from a single uncalibrated phone camera is inherently
approximate (perspective + depth foreshortening). This CV estimate is a screening aid; the
officiated tape-measure value entered via /assessment/manual-entry is the authoritative result.
Pixel scale is derived from the athlete's standing height (nose->ankle), assuming square pixels.
"""

import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from app.core.config import settings


class BroadJumpAnalyzer:
    def __init__(self, reference_athlete_height_cm: float = 170.0):
        self.reference_height_cm = reference_athlete_height_cm

    def analyze_sequence(self, landmark_history: List[Dict[str, Tuple[float, float, float]]],
                         fps: float = 30.0,
                         user_height_cm: Optional[float] = None) -> Dict[str, Any]:
        """
        Estimates horizontal standing-broad-jump distance (cm) from a pose landmark sequence.
        Returns distance, take-off / landing detection, and a confidence score.
        """
        if not landmark_history or len(landmark_history) < 15:
            return {
                "jump_distance_cm": 0.0,
                "takeoff_detected": False,
                "landing_detected": False,
                "flight_time_sec": 0.0,
                "confidence": 0.0,
                "status": "INSUFFICIENT_DATA",
            }

        height_cm = user_height_cm if user_height_cm else self.reference_height_cm
        dt = 1.0 / fps

        foot_x_list, hip_x_list, ankle_y_list = [], [], []
        body_lengths_px, visibilities = [], []

        for frame in landmark_history:
            la = frame.get("LEFT_ANKLE", (0, 0, 0))
            ra = frame.get("RIGHT_ANKLE", (0, 0, 0))
            lh = frame.get("LEFT_HIP", (0, 0, 0))
            rh = frame.get("RIGHT_HIP", (0, 0, 0))
            nose = frame.get("NOSE", (0, 0, 0))

            avg_ankle_x = (la[0] + ra[0]) / 2.0
            avg_ankle_y = (la[1] + ra[1]) / 2.0
            avg_hip_x = (lh[0] + rh[0]) / 2.0
            avg_vis = min(la[2], ra[2], lh[2], rh[2])

            foot_x_list.append(avg_ankle_x)
            hip_x_list.append(avg_hip_x)
            ankle_y_list.append(avg_ankle_y)
            visibilities.append(avg_vis)

            if nose[2] > 0.4 and avg_vis > 0.4:
                body_len = avg_ankle_y - nose[1]  # normalized pixel standing height
                if body_len > 0.2:
                    body_lengths_px.append(body_len)

        # Pixel calibration: cm per normalized unit from standing body height.
        if body_lengths_px:
            standing_body_len = float(np.median(body_lengths_px[:10]))
            cm_per_unit = height_cm / standing_body_len if standing_body_len > 0 else 200.0
        else:
            cm_per_unit = 200.0

        # Smooth trajectories.
        window = max(3, int(fps * 0.1))
        def smooth(sig):
            arr = np.asarray(sig, dtype=float)
            if len(arr) >= window:
                return np.convolve(arr, np.ones(window) / window, mode="same")
            return arr

        foot_x = smooth(foot_x_list)
        hip_x = smooth(hip_x_list)
        ankle_y = smooth(ankle_y_list)
        ankle_disp = -(ankle_y - float(np.mean(ankle_y[:10])))  # up is positive

        # Airborne phase: ankles elevated above standing baseline.
        airborne = np.where(ankle_disp > 0.03)[0]
        takeoff_detected = landing_detected = False
        takeoff_frame = landing_frame = 0
        flight_time_sec = 0.0

        if len(airborne) > 0:
            takeoff_frame = int(airborne[0])
            landing_frame = int(airborne[-1])
            takeoff_detected = takeoff_frame > 0
            landing_detected = landing_frame > takeoff_frame
            if landing_detected:
                flight_time_sec = (landing_frame - takeoff_frame) * dt

        # Horizontal distance travelled by the feet between take-off and landing.
        baseline_foot_x = float(np.median(foot_x[:max(3, takeoff_frame or 3)]))
        if landing_detected:
            landing_foot_x = float(foot_x[landing_frame])
        else:
            landing_foot_x = float(foot_x[int(np.argmax(np.abs(foot_x - baseline_foot_x)))])

        # Prefer the larger of foot- and hip-based displacement (whichever tracked better).
        foot_disp = abs(landing_foot_x - baseline_foot_x)
        hip_disp = abs(float(np.max(hip_x)) - float(np.min(hip_x)))
        displacement_units = max(foot_disp, hip_disp)

        jump_distance_cm = round(float(np.clip(displacement_units * cm_per_unit, 0.0, 350.0)), 1)

        mean_vis = float(np.mean(visibilities)) if visibilities else 0.5
        detection_bonus = 15.0 if (takeoff_detected and landing_detected) else 0.0
        confidence = round(min(95.0, max(50.0, (mean_vis * 78.0) + detection_bonus)), 1)

        return {
            "jump_distance_cm": jump_distance_cm,
            "takeoff_detected": bool(takeoff_detected),
            "landing_detected": bool(landing_detected),
            "flight_time_sec": round(float(flight_time_sec), 3),
            "confidence": float(confidence),
            "status": "COMPLETED",
        }
