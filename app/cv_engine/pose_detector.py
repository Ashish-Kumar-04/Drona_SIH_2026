"""
MediaPipe Pose Landmark Extractor & AI Camera Guidance Engine.
Supports MediaPipe 1.0+ Task API (PoseLandmarker) and legacy solutions.pose API.
Performs real 2D/3D geometric landmark extraction, joint angle mathematics, and pre-assessment guidance checks.
"""

import math
import os
import urllib.request
import numpy as np
from typing import Dict, List, Tuple, Optional, Any

try:
    import cv2
    import mediapipe as mp
    HAS_CV2_MP = True
except ImportError:
    HAS_CV2_MP = False

LANDMARK_NAMES = [
    "NOSE", "LEFT_EYE_INNER", "LEFT_EYE", "LEFT_EYE_OUTER",
    "RIGHT_EYE_INNER", "RIGHT_EYE", "RIGHT_EYE_OUTER",
    "LEFT_EAR", "RIGHT_EAR", "MOUTH_LEFT", "MOUTH_RIGHT",
    "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW",
    "LEFT_WRIST", "RIGHT_WRIST", "LEFT_PINKY", "RIGHT_PINKY",
    "LEFT_INDEX", "RIGHT_INDEX", "LEFT_THUMB", "RIGHT_THUMB",
    "LEFT_HIP", "RIGHT_HIP", "LEFT_KNEE", "RIGHT_KNEE",
    "LEFT_ANKLE", "RIGHT_ANKLE", "LEFT_HEEL", "RIGHT_HEEL",
    "LEFT_FOOT_INDEX", "RIGHT_FOOT_INDEX"
]

class PoseDetector:
    # Key landmark indices (MediaPipe Pose standards)
    NOSE = 0
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32

    def __init__(self, min_detection_confidence: float = 0.5, min_tracking_confidence: float = 0.5):
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.use_tasks_api = False
        self.detector = None
        self.pose = None

        if HAS_CV2_MP:
            # 1. Try legacy solutions API first
            if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'pose'):
                self.mp_pose = mp.solutions.pose
                self.pose = self.mp_pose.Pose(
                    static_image_mode=False,
                    model_complexity=1,
                    smooth_landmarks=True,
                    min_detection_confidence=min_detection_confidence,
                    min_tracking_confidence=min_tracking_confidence
                )
            else:
                # 2. Use MediaPipe 1.0+ Tasks API (PoseLandmarker)
                self.use_tasks_api = True
                model_dir = os.path.dirname(__file__)
                model_path = os.path.join(model_dir, "pose_landmarker.task")
                
                # Check root project directory as fallback
                root_model_path = os.path.join(os.getcwd(), "pose_landmarker.task")
                if not os.path.exists(model_path) and os.path.exists(root_model_path):
                    model_path = root_model_path
                elif not os.path.exists(model_path):
                    url = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
                    try:
                        urllib.request.urlretrieve(url, model_path)
                    except Exception as e:
                        print(f"[Warning] Failed to download pose_landmarker model: {e}")

                if os.path.exists(model_path):
                    from mediapipe.tasks import python
                    from mediapipe.tasks.python import vision

                    base_options = python.BaseOptions(model_asset_path=model_path)
                    options = vision.PoseLandmarkerOptions(
                        base_options=base_options,
                        running_mode=vision.RunningMode.IMAGE,
                        min_pose_detection_confidence=min_detection_confidence,
                        min_pose_presence_confidence=min_tracking_confidence
                    )
                    self.detector = vision.PoseLandmarker.create_from_options(options)

    @staticmethod
    def calculate_angle_2d(p1: Tuple[float, float], p2: Tuple[float, float], p3: Tuple[float, float]) -> float:
        """
        Calculate 2D interior angle at vertex p2 formed by lines (p1 -> p2) and (p3 -> p2).
        Returns angle in degrees [0.0, 180.0].
        """
        v1 = np.array([p1[0] - p2[0], p1[1] - p2[1]])
        v2 = np.array([p3[0] - p2[0], p3[1] - p2[1]])

        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)

        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0

        cosine_angle = np.dot(v1, v2) / (norm_v1 * norm_v2)
        cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
        angle_rad = np.arccos(cosine_angle)
        return float(np.degrees(angle_rad))

    @staticmethod
    def calculate_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """Euclidean distance between two 2D points."""
        return float(math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2))

    def process_frame(self, frame_bgr: np.ndarray) -> Optional[Dict[str, Tuple[float, float, float]]]:
        """
        Processes a BGR OpenCV image frame and returns normalized landmark dict:
        { landmark_name: (x, y, visibility) }
        """
        if not HAS_CV2_MP:
            return None

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        # Legacy API
        if not self.use_tasks_api and self.pose is not None:
            results = self.pose.process(frame_rgb)
            if not results.pose_landmarks:
                return None

            landmarks_dict = {}
            for idx, lm in enumerate(results.pose_landmarks.landmark):
                name = self.mp_pose.PoseLandmark(idx).name
                landmarks_dict[name] = (lm.x, lm.y, lm.visibility)
            return landmarks_dict

        # Tasks API (MediaPipe 1.0+)
        if self.use_tasks_api and self.detector is not None:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            detection_result = self.detector.detect(mp_image)

            if not detection_result.pose_landmarks or len(detection_result.pose_landmarks) == 0:
                return None

            landmarks_dict = {}
            pose_landmarks = detection_result.pose_landmarks[0]
            for idx, lm in enumerate(pose_landmarks):
                name = LANDMARK_NAMES[idx] if idx < len(LANDMARK_NAMES) else f"LANDMARK_{idx}"
                visibility = lm.visibility if hasattr(lm, 'visibility') and lm.visibility is not None else 1.0
                landmarks_dict[name] = (lm.x, lm.y, visibility)
            return landmarks_dict

        return None

    @staticmethod
    def check_camera_guidance(landmarks_history: List[Dict[str, Tuple[float, float, float]]],
                               frame_bgr: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """
        AI Camera Guidance Check (Section 8 of specification).
        Checks:
        1. Full body visibility
        2. Camera stability
        3. Lighting & clarity (if raw frame provided)
        4. Testing area posture readiness
        """
        if not landmarks_history:
            return {
                "ready": False,
                "full_body_visible": False,
                "camera_stable": False,
                "lighting_sufficient": True,
                "athlete_positioned": False,
                "message": "No athlete detected in camera frame."
            }

        latest_frame = landmarks_history[-1]
        
        # 1. Full Body Visibility Check
        required_landmarks = [
            "NOSE", "LEFT_SHOULDER", "RIGHT_SHOULDER",
            "LEFT_HIP", "RIGHT_HIP", "LEFT_KNEE", "RIGHT_KNEE",
            "LEFT_ANKLE", "RIGHT_ANKLE"
        ]
        
        visible_count = 0
        for key in required_landmarks:
            if key in latest_frame:
                x, y, vis = latest_frame[key]
                if vis > 0.4 and 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                    visible_count += 1

        full_body_visible = (visible_count >= len(required_landmarks) - 1)

        # 2. Camera Stability Check (Variance of Hip Keypoints across recent frames)
        camera_stable = True
        if len(landmarks_history) >= 5:
            hip_positions = []
            for frame in landmarks_history[-10:]:
                if "LEFT_HIP" in frame and "RIGHT_HIP" in frame:
                    mid_hip_x = (frame["LEFT_HIP"][0] + frame["RIGHT_HIP"][0]) / 2.0
                    mid_hip_y = (frame["LEFT_HIP"][1] + frame["RIGHT_HIP"][1]) / 2.0
                    hip_positions.append([mid_hip_x, mid_hip_y])
            
            if len(hip_positions) > 3:
                variance = float(np.var(hip_positions, axis=0).sum())
                # If variance is excessively high, camera or person is violently shaking
                camera_stable = (variance < 0.08)

        # 3. Lighting & Clarity Check
        lighting_sufficient = True
        if frame_bgr is not None and HAS_CV2_MP:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            brightness = float(np.mean(gray))
            laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            lighting_sufficient = (brightness > 40.0 and laplacian_var > 30.0)

        athlete_positioned = full_body_visible and camera_stable
        ready = full_body_visible and camera_stable and lighting_sufficient

        message = "READY to begin assessment" if ready else "Please adjust camera angle to ensure full body visibility and stability."

        return {
            "ready": ready,
            "full_body_visible": full_body_visible,
            "camera_stable": camera_stable,
            "lighting_sufficient": lighting_sufficient,
            "athlete_positioned": athlete_positioned,
            "message": message
        }
