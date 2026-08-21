"""
Unit tests for real Sit-up Repetition Counting & Form Analyzer logic.
"""

import pytest
import numpy as np
from app.cv_engine.situp_analyzer import SitUpAnalyzer

def generate_situp_test_sequence(num_reps: int = 3):
    landmark_history = []
    base_angles = [140, 130, 115, 100, 85, 70, 58, 55, 60, 75, 90, 105, 120, 135, 140]
    angles = []
    for a in base_angles:
        angles.extend([a, a]) # ~30 frames per rep

    h = (0.5, 0.5, 0.95)
    k = (0.8, 0.5, 0.95) # knee along horizontal ray (dx=0.3, dy=0)

    for rep in range(num_reps):
        for angle in angles:
            rad = angle * (np.pi / 180.0)
            # shoulder positioned at angle relative to hip-knee ray
            s = (0.5 + 0.3 * float(np.cos(rad)), 0.5 - 0.3 * float(np.sin(rad)), 0.95)
            frame = {
                "LEFT_SHOULDER": s, "RIGHT_SHOULDER": s,
                "LEFT_HIP": h, "RIGHT_HIP": h,
                "LEFT_KNEE": k, "RIGHT_KNEE": k
            }
            landmark_history.append(frame)
    return landmark_history

def test_situp_analyzer_repetition_count():
    analyzer = SitUpAnalyzer(up_angle_threshold=65.0, down_angle_threshold=135.0)
    landmark_history = generate_situp_test_sequence(num_reps=3)

    results = analyzer.analyze_sequence(landmark_history, fps=30.0)

    assert results["status"] == "COMPLETED"
    assert results["valid_reps"] >= 2
    assert results["form_score"] >= 80.0
    assert results["confidence"] > 50.0

def test_situp_analyzer_incomplete_rep():
    analyzer = SitUpAnalyzer(up_angle_threshold=65.0, down_angle_threshold=135.0)

    # Incomplete movement (never reaches <= 65 deg UP threshold)
    angles_cycle = [140, 130, 110, 90, 80, 90, 110, 130, 140]
    
    landmark_history = []
    for angle in angles_cycle:
        rad = angle * (np.pi / 180.0)
        s = (0.5, 0.2, 0.9)
        h = (0.5, 0.6, 0.9)
        k = (0.5 + 0.3 * float(np.sin(rad)), 0.6 + 0.3 * float(np.cos(rad)), 0.9)

        frame = {
            "LEFT_SHOULDER": s,
            "LEFT_HIP": h,
            "LEFT_KNEE": k
        }
        landmark_history.append(frame)

    results = analyzer.analyze_sequence(landmark_history, fps=30.0)
    assert results["valid_reps"] == 0


