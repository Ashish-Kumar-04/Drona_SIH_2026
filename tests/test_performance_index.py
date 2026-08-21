"""
Unit tests for Benchmarking Norms and Athletic Performance Index (API) Engine.
"""

import pytest
from datetime import datetime
from app.scoring_engine.benchmarker import BenchmarkingEngine
from app.scoring_engine.performance_index import AthleticPerformanceIndexCalculator
from app.models.db_models import Assessment

def test_score_normalization():
    # Sit-ups test for 15-year-old male: mean=28, std=6
    norm_score, status, src = BenchmarkingEngine.normalize_score(
        raw_score=34.0, test_type="sit_up", age=15, category="Male"
    )

    assert norm_score > 75.0 # Above average
    assert status in ["Above Benchmark", "Elite"]
    assert "Prototype / Research Benchmark" in src

def test_athletic_performance_index_calculator():
    assessments = [
        Assessment(
            assessment_id="A1", athlete_id="ATH-100", test_type="sit_up",
            raw_score=30, normalized_score=80.0, confidence=95.0,
            validation_score=97.0, timestamp=datetime.utcnow(), status="VALID"
        ),
        Assessment(
            assessment_id="A2", athlete_id="ATH-100", test_type="vertical_jump",
            raw_score=45, normalized_score=85.0, confidence=94.0,
            validation_score=96.0, timestamp=datetime.utcnow(), status="VALID"
        ),
        Assessment(
            assessment_id="A3", athlete_id="ATH-100", test_type="shuttle_run",
            raw_score=12.0, normalized_score=82.0, confidence=93.0,
            validation_score=95.0, timestamp=datetime.utcnow(), status="VALID"
        )
    ]

    index_data = AthleticPerformanceIndexCalculator.calculate_index(assessments)

    assert index_data["strength_score"] == 80.0
    assert index_data["power_score"] == 85.0
    assert index_data["speed_score"] == 82.0
    assert index_data["overall_index"] > 80.0
