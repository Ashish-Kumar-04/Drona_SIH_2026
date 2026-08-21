"""
Unit tests for real Shuttle Run Sprint & Boundary Crossing Analyzer.
"""

import pytest
import numpy as np
from app.cv_engine.shuttle_run_analyzer import ShuttleRunAnalyzer

def test_shuttle_run_boundary_and_timing():
    analyzer = ShuttleRunAnalyzer(start_x_thresh=0.15, boundary_x_thresh=0.85)

    fps = 30.0
    total_frames = 180 # 6.0 seconds

    landmark_history = []
    # Simulate athlete running out from X=0.10 to X=0.90 (frame 0 -> 90) and returning to X=0.10 (frame 91 -> 180)
    for f in range(total_frames):
        if f <= 90:
            x = 0.10 + (0.80 * (f / 90.0))
        else:
            x = 0.90 - (0.80 * ((f - 90) / 90.0))

        frame = {
            "LEFT_HIP": (x, 0.5, 0.9),
            "RIGHT_HIP": (x, 0.5, 0.9)
        }
        landmark_history.append(frame)

    results = analyzer.analyze_sequence(landmark_history, fps=fps)

    assert results["status"] == "COMPLETED"
    assert bool(results["boundary_crossed"]) is True
    assert bool(results["valid_run"]) is True
    assert results["total_time_sec"] >= 4.0
    assert results["confidence"] >= 80.0
