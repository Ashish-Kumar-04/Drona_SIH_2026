"""
Sit-up Detection & Movement Analysis Engine.
Implements Section 10 of SIH 25073 specification using real body landmark angle mathematics.
"""

import numpy as np
from typing import Dict, List, Tuple, Any
from app.cv_engine.pose_detector import PoseDetector

class SitUpAnalyzer:
    # State constants
    STATE_DOWN = "DOWN"
    STATE_UP = "UP"

    def __init__(self, up_angle_threshold: float = 65.0, down_angle_threshold: float = 135.0):
        self.up_angle_threshold = up_angle_threshold
        self.down_angle_threshold = down_angle_threshold

    def analyze_sequence(self, landmark_history: List[Dict[str, Tuple[float, float, float]]], fps: float = 30.0) -> Dict[str, Any]:
        """
        Analyzes a sequence of pose landmark frames to track sit-ups.
        Returns total reps, valid reps, invalid reps, form score, confidence, and rep timeline.
        """
        if not landmark_history or len(landmark_history) < 10:
            return {
                "total_reps": 0,
                "valid_reps": 0,
                "invalid_reps": 0,
                "form_score": 0.0,
                "confidence": 0.0,
                "angles": [],
                "rep_timestamps": [],
                "status": "INSUFFICIENT_DATA"
            }

        angles = []
        confidences = []
        valid_frames_count = 0

        # Compute hip angle for each frame
        for frame in landmark_history:
            # Prefer side with higher visibility
            left_vis = min(frame.get("LEFT_SHOULDER", (0,0,0))[2], frame.get("LEFT_HIP", (0,0,0))[2], frame.get("LEFT_KNEE", (0,0,0))[2])
            right_vis = min(frame.get("RIGHT_SHOULDER", (0,0,0))[2], frame.get("RIGHT_HIP", (0,0,0))[2], frame.get("RIGHT_KNEE", (0,0,0))[2])

            if left_vis >= right_vis and left_vis > 0.3:
                s = frame["LEFT_SHOULDER"][:2]
                h = frame["LEFT_HIP"][:2]
                k = frame["LEFT_KNEE"][:2]
                avg_vis = left_vis
            elif right_vis > 0.3:
                s = frame["RIGHT_SHOULDER"][:2]
                h = frame["RIGHT_HIP"][:2]
                k = frame["RIGHT_KNEE"][:2]
                avg_vis = right_vis
            else:
                s, h, k = (0,0), (0,0), (0,0)
                avg_vis = 0.0

            if avg_vis > 0.3:
                angle = PoseDetector.calculate_angle_2d(s, h, k)
                angles.append(angle)
                confidences.append(avg_vis)
                valid_frames_count += 1
            else:
                # Fallback interpolation or carry forward
                angles.append(angles[-1] if angles else 140.0)
                confidences.append(0.2)

        # Smooth angles with moving average filter
        window_size = max(3, int(fps * 0.15))
        if len(angles) >= window_size:
            smoothed_angles = list(np.convolve(angles, np.ones(window_size)/window_size, mode='same'))
        else:
            smoothed_angles = angles

        # Finite State Machine for Sit-Up Rep Counting
        current_state = self.STATE_DOWN
        valid_reps = 0
        invalid_reps = 0
        total_attempts = 0
        rep_durations = []
        last_rep_frame = 0
        
        min_rep_frames = int(fps * 0.5) # A real sit-up takes at least 0.5 seconds
        reached_up = False
        min_angle_in_rep = 180.0

        for idx, angle in enumerate(smoothed_angles):
            if current_state == self.STATE_DOWN:
                if angle < self.down_angle_threshold - 10.0:
                    # Athlete has initiated upward movement
                    reached_up = False
                    min_angle_in_rep = angle

                if angle <= self.up_angle_threshold:
                    reached_up = True
                    current_state = self.STATE_UP
                    min_angle_in_rep = min(min_angle_in_rep, angle)

            elif current_state == self.STATE_UP:
                min_angle_in_rep = min(min_angle_in_rep, angle)

                if angle >= self.down_angle_threshold:
                    # Completed return to DOWN state
                    current_state = self.STATE_DOWN
                    frame_delta = idx - last_rep_frame

                    if reached_up and frame_delta >= min_rep_frames:
                        valid_reps += 1
                        total_attempts += 1
                        rep_durations.append(frame_delta / fps)
                        last_rep_frame = idx
                    elif not reached_up and min_angle_in_rep < (self.down_angle_threshold - 25.0):
                        # Incomplete repetition (turned back without reaching UP threshold)
                        invalid_reps += 1
                        total_attempts += 1

        total_reps = valid_reps + invalid_reps
        
        # Calculate Form Score & Movement Consistency
        if total_reps > 0:
            form_score = round((valid_reps / total_reps) * 100.0, 1)
        else:
            form_score = 0.0

        if rep_durations and len(rep_durations) > 1:
            rhythm_std = float(np.std(rep_durations))
            cadence_score = max(0.0, 100.0 - (rhythm_std * 20.0))
        else:
            cadence_score = 90.0

        # AI Confidence Score
        mean_vis = float(np.mean(confidences)) if confidences else 0.5
        ai_confidence = round(min(98.0, max(50.0, mean_vis * 100.0 * 0.95)), 1)

        return {
            "total_reps": total_reps,
            "valid_reps": valid_reps,
            "invalid_reps": invalid_reps,
            "form_score": form_score,
            "rhythm_consistency_score": round(cadence_score, 1),
            "confidence": ai_confidence,
            "rep_durations_sec": [round(d, 2) for d in rep_durations],
            "min_angle_recorded": round(float(min(smoothed_angles)), 1) if smoothed_angles else 0.0,
            "max_angle_recorded": round(float(max(smoothed_angles)), 1) if smoothed_angles else 0.0,
            "status": "COMPLETED"
        }
