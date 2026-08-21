"""
Core configuration and normative benchmark reference standards for SIH 25073.
"""

import os
from typing import Dict, Any

class Settings:
    PROJECT_NAME: str = "AI Sports Talent Assessment Platform"
    PROBLEM_STATEMENT_ID: str = "25073"
    VERSION: str = "1.0.0"
    
    # Database
    SQLITE_DB_URL: str = os.getenv("DATABASE_URL", "sqlite:///./sih_assessment.db")
    
    # Physics constants
    GRAVITY_ACCEL: float = 9.81  # m/s^2
    
    # MediaPipe pose configuration
    MIN_DETECTION_CONFIDENCE: float = 0.5
    MIN_TRACKING_CONFIDENCE: float = 0.5
    
    # Benchmark Labeling Strategy (per document directive #15)
    BENCHMARK_SOURCE_LABEL: str = "Prototype / Research Benchmark"
    
    # Normative Benchmarks by Age (10-18+) and Category
    # Metrics: Sit-ups (reps in 60s), Vertical Jump (cm), Shuttle Run (seconds for 10x4m or 20m shuttle)
    # Means and Std Devs derived from Indian youth physical assessment normative datasets
    NORMATIVE_BENCHMARKS: Dict[str, Dict[str, Any]] = {
        "10-12_Male": {
            "situp": {"mean": 20.0, "std": 5.0},
            "vertical_jump": {"mean": 28.0, "std": 6.0},
            "shuttle_run": {"mean": 14.5, "std": 1.2}  # lower time is better
        },
        "10-12_Female": {
            "situp": {"mean": 18.0, "std": 4.5},
            "vertical_jump": {"mean": 24.0, "std": 5.5},
            "shuttle_run": {"mean": 15.2, "std": 1.3}
        },
        "13-15_Male": {
            "situp": {"mean": 28.0, "std": 6.0},
            "vertical_jump": {"mean": 38.0, "std": 7.0},
            "shuttle_run": {"mean": 12.8, "std": 1.0}
        },
        "13-15_Female": {
            "situp": {"mean": 24.0, "std": 5.0},
            "vertical_jump": {"mean": 31.0, "std": 6.0},
            "shuttle_run": {"mean": 13.8, "std": 1.1}
        },
        "16-18_Male": {
            "situp": {"mean": 35.0, "std": 7.0},
            "vertical_jump": {"mean": 48.0, "std": 8.0},
            "shuttle_run": {"mean": 11.5, "std": 0.9}
        },
        "16-18_Female": {
            "situp": {"mean": 28.0, "std": 6.0},
            "vertical_jump": {"mean": 36.0, "std": 6.5},
            "shuttle_run": {"mean": 12.8, "std": 1.0}
        },
        "General": {
            "situp": {"mean": 25.0, "std": 6.0},
            "vertical_jump": {"mean": 35.0, "std": 7.0},
            "shuttle_run": {"mean": 13.0, "std": 1.1}
        }
    }

settings = Settings()
