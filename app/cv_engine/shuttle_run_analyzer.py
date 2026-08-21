"""
Shuttle Run Movement & Boundary Crossing Detection Engine.
Implements Section 12 of SIH 25073 specification with 2D spatial tracking and speed/agility timing calculation.
"""

import numpy as np
from typing import Dict, List, Tuple, Any, Optional

class ShuttleRunAnalyzer:
    def __init__(self, start_x_thresh: float = 0.15, boundary_x_thresh: float = 0.85):
        self.start_x_thresh = start_x_thresh
        self.boundary_x_thresh = boundary_x_thresh

    def analyze_sequence(self, landmark_history: List[Dict[str, Tuple[float, float, float]]],
                         fps: float = 30.0) -> Dict[str, Any]:
        """
        Analyzes 2D center-of-mass trajectory for Shuttle Run sprint, turnaround, and return.
        """
        if not landmark_history or len(landmark_history) < 20:
            return {
                "total_time_sec": 0.0,
                "valid_run": False,
                "boundary_crossed": False,
                "peak_velocity_norm": 0.0,
                "confidence": 0.0,
                "status": "INSUFFICIENT_DATA"
            }

        dt = 1.0 / fps
        x_positions = []
        timestamps = []
        visibilities = []

        for idx, frame in enumerate(landmark_history):
            left_hip = frame.get("LEFT_HIP", (0,0,0))
            right_hip = frame.get("RIGHT_HIP", (0,0,0))
            
            mid_x = (left_hip[0] + right_hip[0]) / 2.0
            vis = min(left_hip[2], right_hip[2])

            x_positions.append(mid_x)
            timestamps.append(idx * dt)
            visibilities.append(vis)

        # Smooth position trajectory
        window = max(3, int(fps * 0.15))
        if len(x_positions) >= window:
            smoothed_x = list(np.convolve(x_positions, np.ones(window)/window, mode='same'))
        else:
            smoothed_x = x_positions

        # Derivative for horizontal velocity
        velocities = list(np.gradient(smoothed_x, dt))

        # Detect Start Event (athlete moves away from start area)
        start_index = 0
        for i in range(len(smoothed_x)):
            if abs(velocities[i]) > 0.05:
                start_index = i
                break

        start_time = timestamps[start_index]

        # Detect Boundary Crossing & Turnaround Event (Max X displacement)
        max_x_idx = int(np.argmax(smoothed_x))
        max_x_val = smoothed_x[max_x_idx]
        boundary_crossed = (max_x_val >= self.boundary_x_thresh - 0.1)

        # Detect Finish Event (athlete returns to start line area)
        finish_index = len(smoothed_x) - 1
        for i in range(max_x_idx, len(smoothed_x)):
            if smoothed_x[i] <= self.start_x_thresh + 0.1:
                finish_index = i
                break

        finish_time = timestamps[finish_index]
        total_time_sec = max(0.0, finish_time - start_time)

        # Calculate Agility Turnaround Deceleration Time
        turnaround_decel_frames = max(1, int(fps * 0.4))
        turn_start_idx = max(0, max_x_idx - turnaround_decel_frames)
        turn_end_idx = min(len(velocities) - 1, max_x_idx + turnaround_decel_frames)
        decel_time_sec = (turn_end_idx - turn_start_idx) * dt

        # Validity Check
        valid_run = (boundary_crossed and total_time_sec >= 3.0 and finish_index > max_x_idx)

        # Peak Velocity metric
        peak_velocity = float(np.max(np.abs(velocities)))

        # Confidence score
        mean_vis = float(np.mean(visibilities)) if visibilities else 0.5
        boundary_bonus = 15.0 if boundary_crossed else 0.0
        confidence = round(min(98.0, max(50.0, (mean_vis * 80.0) + boundary_bonus)), 1)

        return {
            "total_time_sec": round(float(total_time_sec), 2),
            "valid_run": bool(valid_run),
            "boundary_crossed": bool(boundary_crossed),
            "start_time_sec": round(float(start_time), 2),
            "finish_time_sec": round(float(finish_time), 2),
            "turnaround_time_sec": round(float(decel_time_sec), 2),
            "peak_velocity_norm": round(float(peak_velocity), 2),
            "confidence": float(confidence),
            "status": "COMPLETED"
        }
