"""
Unit tests for real Vertical Jump Kinematic Flight-Time & Measurement Analyzer.
"""

import pytest
import numpy as np
from app.cv_engine.vertical_jump_analyzer import VerticalJumpAnalyzer

def test_vertical_jump_kinematic_calculation():
    analyzer = VerticalJumpAnalyzer(reference_athlete_height_cm=170.0)

    fps = 30.0
    dt = 1.0 / fps
    total_frames = 60 # 2 seconds

    # Simulate standing baseline (frames 0-15), takeoff (frame 16), airborne peak (frame 25), landing (frame 34)
    # Flight time = 18 frames = 0.60 seconds -> expected kinematic height = 9.81 * (0.60^2) / 8 = 0.4414 m = 44.1 cm
    landmark_history = []

    baseline_ankle_y = 0.80
    baseline_hip_y = 0.50
    nose_y = 0.15

    for f in range(total_frames):
        if 16 <= f <= 34:
            # Airborne trajectory (parabolic elevation)
            t_air = (f - 16) / 18.0 # 0.0 to 1.0
            elevation = 0.15 * np.sin(t_air * np.pi) # normalized elevation up to 0.15
        else:
            elevation = 0.0

        ankle_y = baseline_ankle_y - elevation
        hip_y = baseline_hip_y - elevation

        frame = {
            "NOSE": (0.5, nose_y - elevation, 0.9),
            "LEFT_HIP": (0.45, hip_y, 0.9),
            "RIGHT_HIP": (0.55, hip_y, 0.9),
            "LEFT_ANKLE": (0.45, ankle_y, 0.9),
            "RIGHT_ANKLE": (0.55, ankle_y, 0.9)
        }
        landmark_history.append(frame)

    results = analyzer.analyze_sequence(landmark_history, fps=fps, user_height_cm=170.0)

    assert results["status"] == "COMPLETED"
    assert results["takeoff_detected"] is True
    assert results["landing_detected"] is True
    assert results["flight_time_sec"] > 0.4
    assert 30.0 <= results["jump_height_cm"] <= 60.0
    assert results["confidence"] >= 70.0
