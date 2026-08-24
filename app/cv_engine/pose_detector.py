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
                               frame_bgr: Optional[np.ndarray] = None,
                               test_type: Optional[str] = None) -> Dict[str, Any]:
        """
        AI Camera Guidance Check (Section 8 of specification).

        From the latest pose frame this computes, in addition to the original checks:
          * centering       — hip mid-point vs frame centre (are you in the middle of the shot?)
          * distance_ok     — nose→ankle body span vs frame height (too close / too far / good)
          * orientation_ok  — shoulder-width ÷ torso-height ⇒ front-on vs side-on, checked against
                              what the chosen test needs (sit-up / broad jump → side; vertical jump
                              → front; shuttle → any)
          * instruction     — the single most useful next correction, in plain language
          * alignment_score — 0-100 readiness score the UI can gate the Start button on

        `test_type` is optional and backward-compatible: when omitted, orientation is not enforced.
        All original keys (`ready`, `full_body_visible`, `camera_stable`, `lighting_sufficient`,
        `athlete_positioned`, `message`) are still returned.
        """
        # Per-test camera orientation requirement.
        ORIENTATION_REQ = {
            "sit_up": "side",        # camera to the side to read the hip/torso angle
            "broad_jump": "side",    # side-on to measure horizontal distance
            "vertical_jump": "front",# face-on, whole body, to read the flight
            "shuttle_run": "any",    # runs across the frame — orientation not critical
        }
        req_orientation = ORIENTATION_REQ.get(test_type or "", "any")

        if not landmarks_history:
            return {
                "ready": False,
                "full_body_visible": False,
                "camera_stable": False,
                "lighting_sufficient": True,
                "athlete_positioned": False,
                "centered": False,
                "distance_ok": False,
                "orientation_ok": (req_orientation == "any"),
                "orientation": None,
                "off_center_x": None,
                "off_center_y": None,
                "alignment_score": 0,
                "test_type": test_type,
                "instruction": "No athlete detected — step into the camera's view.",
                "message": "No athlete detected in camera frame."
            }

        latest_frame = landmarks_history[-1]

        def _pt(name):
            """Return (x, y, vis) if the landmark is present and reasonably visible, else None."""
            v = latest_frame.get(name)
            if v is None:
                return None
            x, y, vis = v
            return (x, y, vis) if vis is not None and vis > 0.4 else None

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

        # 4. Centering — hip mid-point relative to the frame centre.
        centered = False
        off_center_x = None
        off_center_y = None
        centering_msg = None
        lh, rh = _pt("LEFT_HIP"), _pt("RIGHT_HIP")
        if lh and rh:
            mid_hip_x = (lh[0] + rh[0]) / 2.0
            mid_hip_y = (lh[1] + rh[1]) / 2.0
            off_center_x = round(mid_hip_x - 0.5, 3)      # +ve ⇒ athlete is right-of-centre in frame
            off_center_y = round(mid_hip_y - 0.55, 3)     # target hips slightly below centre
            centered = abs(off_center_x) <= 0.15
            if off_center_x > 0.15:
                centering_msg = "You're too far to the right of the frame — move to the centre."
            elif off_center_x < -0.15:
                centering_msg = "You're too far to the left of the frame — move to the centre."

        # 5. Distance — vertical body span (nose → lowest ankle) as a fraction of frame height.
        distance_ok = False
        distance_msg = None
        nose = _pt("NOSE")
        ankles = [p for p in (_pt("LEFT_ANKLE"), _pt("RIGHT_ANKLE")) if p]
        if nose and ankles:
            nose_y = nose[1]
            ankle_y = max(p[1] for p in ankles)
            span = ankle_y - nose_y
            top_clip = nose_y < 0.06
            bottom_clip = ankle_y > 0.96
            if top_clip or bottom_clip:
                distance_msg = "Step back so your whole body — head to feet — fits in the frame."
            elif span < 0.45:
                distance_msg = "Move a little closer — you look too small in the frame."
            else:
                distance_ok = True
        # If nose/ankles aren't visible the full-body check already owns the instruction.

        # 6. Orientation — shoulder width vs torso height ⇒ front-on / side-on.
        orientation = None
        orientation_ok = True
        orientation_msg = None
        ls, rs = _pt("LEFT_SHOULDER"), _pt("RIGHT_SHOULDER")
        if ls and rs and lh and rh:
            shoulder_width = abs(ls[0] - rs[0])
            mid_sh_y = (ls[1] + rs[1]) / 2.0
            mid_hip_y = (lh[1] + rh[1]) / 2.0
            torso_h = abs(mid_hip_y - mid_sh_y)
            if torso_h > 0.05:
                ratio = shoulder_width / torso_h
                if ratio >= 0.42:
                    orientation = "front"
                elif ratio <= 0.30:
                    orientation = "side"
                else:
                    orientation = "angled"   # in-between; accepted for either requirement
        if req_orientation != "any" and orientation is not None:
            if req_orientation == "front" and orientation == "side":
                orientation_ok = False
                orientation_msg = "Face the camera so your whole body is visible."
            elif req_orientation == "side" and orientation == "front":
                orientation_ok = False
                orientation_msg = "Turn side-on to the camera so it sees your profile."

        athlete_positioned = full_body_visible and camera_stable and centered

        # Weighted readiness score (0-100). Full-body visibility dominates.
        alignment_score = int(round(
            35 * full_body_visible +
            20 * centered +
            25 * distance_ok +
            10 * orientation_ok +
            10 * lighting_sufficient
        ))

        ready = (full_body_visible and centered and distance_ok
                 and orientation_ok and lighting_sufficient and camera_stable)

        # Single, prioritized instruction — the most useful next correction.
        if not full_body_visible:
            instruction = "Make sure your whole body — head to feet — is visible in the frame."
        elif distance_msg:
            instruction = distance_msg
        elif not camera_stable:
            instruction = "Keep the camera still — prop it up on a stable surface."
        elif centering_msg:
            instruction = centering_msg
        elif orientation_msg:
            instruction = orientation_msg
        elif not lighting_sufficient:
            instruction = "Find a brighter, evenly-lit spot so the camera can see you clearly."
        else:
            instruction = "Perfect — hold still and press Start."

        return {
            "ready": ready,
            "full_body_visible": full_body_visible,
            "camera_stable": camera_stable,
            "lighting_sufficient": lighting_sufficient,
            "athlete_positioned": athlete_positioned,
            "centered": centered,
            "distance_ok": distance_ok,
            "orientation_ok": orientation_ok,
            "orientation": orientation,
            "off_center_x": off_center_x,
            "off_center_y": off_center_y,
            "alignment_score": alignment_score,
            "test_type": test_type,
            "instruction": instruction,
            "message": instruction
        }
