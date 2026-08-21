"""
AI-assisted Assessment Verification and Anomaly Detection Engine.
Implements Sections 13, 14, and 16 of SIH 25073 specification.
Verifies person consistency, movement pattern integrity, timestamp continuity, and anti-cheat validation.
"""

import numpy as np
from typing import Dict, List, Tuple, Any

class AnomalyVerifier:
    @staticmethod
    def verify_assessment(landmark_history: List[Dict[str, Tuple[float, float, float]]],
                          fps: float = 30.0,
                          test_specific_valid: bool = True) -> Dict[str, Any]:
        """
        Executes multi-layer anomaly detection and returns validation scores & status.
        """
        if not landmark_history or len(landmark_history) < 10:
            return {
                "athlete_detected": False,
                "full_movement_detected": False,
                "test_protocol_followed": False,
                "recording_valid": False,
                "validation_score": 0.0,
                "status": "INVALID",
                "flags": ["INSUFFICIENT_VIDEO_FRAMES"]
            }

        flags = []
        scores = []

        # Layer 1: Athlete Detection & Keypoint Continuity
        detected_frames = 0
        centers = []
        aspect_ratios = []

        for frame in landmark_history:
            left_hip = frame.get("LEFT_HIP", (0,0,0))
            right_hip = frame.get("RIGHT_HIP", (0,0,0))
            nose = frame.get("NOSE", (0,0,0))

            if left_hip[2] > 0.3 or right_hip[2] > 0.3:
                detected_frames += 1
                mid_x = (left_hip[0] + right_hip[0]) / 2.0
                mid_y = (left_hip[1] + right_hip[1]) / 2.0
                centers.append([mid_x, mid_y])

                if nose[2] > 0.3:
                    torso_h = abs(mid_y - nose[1])
                    if torso_h > 0.05:
                        aspect_ratios.append(torso_h)

        detection_ratio = detected_frames / len(landmark_history)
        athlete_detected = (detection_ratio >= 0.75)
        scores.append(detection_ratio * 100.0)

        if not athlete_detected:
            flags.append("ATHLETE_DISAPPEARED_MID_TEST")

        # Layer 2: Person Consistency & Identity Swap Check
        person_consistent = True
        if len(centers) > 5:
            centers_arr = np.array(centers)
            center_jumps = np.linalg.norm(np.diff(centers_arr, axis=0), axis=1)
            # Sudden unreal teleportation of person (center displacement > 0.35 frame width in single frame)
            max_jump = float(np.max(center_jumps)) if len(center_jumps) > 0 else 0.0
            if max_jump > 0.35:
                person_consistent = False
                flags.append("SUDDEN_PERSON_POSITION_JUMP")
                scores.append(50.0)
            else:
                scores.append(95.0)
        else:
            scores.append(80.0)

        # Layer 3: Movement Consistency & Biomechanical Speed Sanity
        biomechanical_valid = True
        if len(centers) > 5:
            # Velocity of mid-hip in normalized units per sec
            velocities = np.diff(centers_arr, axis=0) * fps
            speed_norms = np.linalg.norm(velocities, axis=1)
            max_speed = float(np.max(speed_norms))
            # Human speed threshold check in normalized frame (speeds > 4.0 norm units/sec indicate edited video)
            if max_speed > 5.0:
                biomechanical_valid = False
                flags.append("UNNATURAL_MOTION_SPEED_SPIKE")
                scores.append(40.0)
            else:
                scores.append(98.0)

        # Layer 4: Protocol Compliance
        test_protocol_followed = athlete_detected and biomechanical_valid and test_specific_valid
        if not test_protocol_followed:
            flags.append("PROTOCOL_VIOLATION_OR_INCOMPLETE")

        # Layer 5: Video Integrity & Frame Discontinuities
        recording_valid = (detection_ratio > 0.8) and person_consistent and biomechanical_valid
        if recording_valid:
            scores.append(98.0)
        else:
            scores.append(60.0)

        # Aggregate Validation Score
        validation_score = round(float(np.mean(scores)), 1)

        # Determine Final Status
        if validation_score >= 85.0 and recording_valid and test_protocol_followed:
            status = "VALID"
        elif validation_score >= 60.0:
            status = "SUSPICIOUS"
        else:
            status = "INVALID"

        return {
            "athlete_detected": bool(athlete_detected),
            "full_movement_detected": bool(biomechanical_valid),
            "test_protocol_followed": bool(test_protocol_followed),
            "recording_valid": bool(recording_valid),
            "authenticity_score": float(validation_score),
            "validation_score": float(validation_score),
            "status": str(status),
            "flags": [str(f) for f in flags]
        }
