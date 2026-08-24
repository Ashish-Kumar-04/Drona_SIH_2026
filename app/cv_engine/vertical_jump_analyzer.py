"""
Vertical Jump Detection & Kinematic Height Measurement Engine.
Implements Section 11 of SIH 25073 specification using real kinematic equations of motion and pixel calibration scaling.
"""

import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from app.core.config import settings
from app.cv_engine.pose_detector import PoseDetector

class VerticalJumpAnalyzer:
    def __init__(self, reference_athlete_height_cm: float = 170.0):
        self.reference_height_cm = reference_athlete_height_cm
        self.g = settings.GRAVITY_ACCEL # 9.81 m/s^2

    def analyze_sequence(self, landmark_history: List[Dict[str, Tuple[float, float, float]]],
                         fps: float = 30.0,
                         user_height_cm: Optional[float] = None) -> Dict[str, Any]:
        """
        Analyzes pose landmark sequence for a vertical jump test.
        Returns estimated jump height (cm), take-off detection, landing detection, and confidence.
        """
        if not landmark_history or len(landmark_history) < 15:
            return {
                "jump_height_cm": 0.0,
                "takeoff_detected": False,
                "landing_detected": False,
                "flight_time_sec": 0.0,
                "confidence": 0.0,
                "status": "INSUFFICIENT_DATA"
            }

        height_cm = user_height_cm if user_height_cm else self.reference_height_cm

        ankle_y_list = []
        hip_y_list = []
        body_lengths_px = []
        visibilities = []

        for frame in landmark_history:
            left_ankle = frame.get("LEFT_ANKLE", (0,0,0))
            right_ankle = frame.get("RIGHT_ANKLE", (0,0,0))
            left_hip = frame.get("LEFT_HIP", (0,0,0))
            right_hip = frame.get("RIGHT_HIP", (0,0,0))
            nose = frame.get("NOSE", (0,0,0))

            avg_ankle_y = (left_ankle[1] + right_ankle[1]) / 2.0
            avg_hip_y = (left_hip[1] + right_hip[1]) / 2.0
            avg_vis = min(left_ankle[2], right_ankle[2], left_hip[2], right_hip[2])

            ankle_y_list.append(avg_ankle_y)
            hip_y_list.append(avg_hip_y)
            visibilities.append(avg_vis)

            if nose[2] > 0.4 and avg_vis > 0.4:
                body_len = avg_ankle_y - nose[1] # Normalized pixel height
                if body_len > 0.2:
                    body_lengths_px.append(body_len)

        # Baseline pixel calibration scale (cm per normalized pixel unit)
        if body_lengths_px:
            standing_body_len_px = float(np.median(body_lengths_px[:10]))
            cm_per_pixel = height_cm / standing_body_len_px if standing_body_len_px > 0 else 200.0
        else:
            cm_per_pixel = 200.0

        # Invert Y so up is positive displacement
        hip_disp = -np.array(hip_y_list)
        ankle_disp = -np.array(ankle_y_list)

        # Smooth signal
        window = max(3, int(fps * 0.1))
        if len(hip_disp) >= window:
            smoothed_hip = np.convolve(hip_disp, np.ones(window)/window, mode='same')
            smoothed_ankle = np.convolve(ankle_disp, np.ones(window)/window, mode='same')
        else:
            smoothed_hip = hip_disp
            smoothed_ankle = ankle_disp

        # Velocity signal (derivative of position)
        dt = 1.0 / fps
        hip_velocity = np.gradient(smoothed_hip, dt)
        ankle_velocity = np.gradient(smoothed_ankle, dt)

        # Standing baseline (first 10 frames)
        baseline_ankle = float(np.mean(smoothed_ankle[:10]))
        baseline_hip = float(np.mean(smoothed_hip[:10]))

        # Detect Airborne Phase where ankle position is significantly elevated above baseline
        ankle_elevation = smoothed_ankle - baseline_ankle
        airborne_indices = np.where(ankle_elevation > 0.03)[0]

        takeoff_detected = False
        landing_detected = False
        takeoff_frame = 0
        landing_frame = 0
        flight_time_sec = 0.0
        kinematic_height_cm = 0.0

        if len(airborne_indices) > 0:
            # Group consecutive airborne indices to find main jump
            jump_start = int(airborne_indices[0])
            jump_end = int(airborne_indices[-1])

            # Refine takeoff frame (where upward velocity peaks or position crosses threshold)
            takeoff_candidates = np.where((smoothed_ankle > baseline_ankle + 0.02) & (ankle_velocity > 0.2))[0]
            if len(takeoff_candidates) > 0:
                takeoff_frame = int(takeoff_candidates[0])
                takeoff_detected = True

            # Refine landing frame
            landing_candidates = np.where((smoothed_ankle <= baseline_ankle + 0.02) & (np.arange(len(smoothed_ankle)) > takeoff_frame + 3))[0]
            if len(landing_candidates) > 0:
                landing_frame = int(landing_candidates[0])
                landing_detected = True

            if takeoff_detected and landing_detected and landing_frame > takeoff_frame:
                flight_time_sec = (landing_frame - takeoff_frame) * dt
                # Kinematic equation: h = g * t_flight^2 / 8
                kinematic_height_cm = (self.g * (flight_time_sec ** 2) / 8.0) * 100.0

        # Pixel displacement measurement: peak Y vs baseline Y
        peak_hip_disp = float(np.max(smoothed_hip) - baseline_hip)
        pixel_height_cm = max(0.0, peak_hip_disp * cm_per_pixel)

        # Hybrid height estimation (70% kinematic flight time + 30% pixel displacement)
        if takeoff_detected and landing_detected and flight_time_sec > 0.15:
            estimated_jump_height_cm = (kinematic_height_cm * 0.70) + (pixel_height_cm * 0.30)
        else:
            estimated_jump_height_cm = pixel_height_cm

        # Clamp to realistic human standing-vertical-jump bounds [0 cm, 120 cm].
        estimated_jump_height_cm = round(float(np.clip(estimated_jump_height_cm, 0.0, 120.0)), 1)

        # Confidence Score calculation
        mean_vis = float(np.mean(visibilities)) if visibilities else 0.5
        detection_bonus = 15.0 if (takeoff_detected and landing_detected) else 0.0
        confidence = round(min(98.0, max(50.0, (mean_vis * 80.0) + detection_bonus)), 1)

        return {
            "jump_height_cm": estimated_jump_height_cm,
            "takeoff_detected": bool(takeoff_detected),
            "landing_detected": bool(landing_detected),
            "flight_time_sec": round(float(flight_time_sec), 3),
            "kinematic_height_cm": round(float(kinematic_height_cm), 1),
            "pixel_height_cm": round(float(pixel_height_cm), 1),
            "confidence": float(confidence),
            "status": "COMPLETED"
        }
