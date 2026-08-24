"""
Unit tests for the Benchmarking Norms and Athletic Performance Index engines.

These lock in the Phase 0-2 fitness-scoring upgrades:
  * the sit-up benchmark key bug is fixed (a mid rep count is no longer scored ~99),
  * norms are interpolated per year (a 10- and a 12-year-old score differently),
  * direction is registry-driven ("lower is better" for timed tests),
  * BMI is a two-sided optimal-band score (both under- and over-weight are penalised),
  * the overall index is a weighted GEOMETRIC mean over the domains that have data,
  * every one of the eight battery tests normalises in the correct direction.
"""

import pytest
from datetime import datetime, timedelta

from app.scoring_engine.benchmarker import BenchmarkingEngine
from app.scoring_engine.performance_index import AthleticPerformanceIndexCalculator
from app.core.config import settings
from app.models.db_models import Assessment

# The performance tiers classify() may return (display-only strings).
VALID_TIERS = {"Elite", "Excellent", "Above Average", "Average", "Developing", "Needs Improvement"}


def _score(raw, test_type, age, category="Male"):
    """Convenience: return just the numeric normalized score."""
    return BenchmarkingEngine.normalize_score(raw, test_type, age, category)[0]


def _assessment(test_type, normalized_score, ts=None):
    """A minimal VALID assessment row carrying a normalized score for index tests."""
    return Assessment(
        assessment_id=f"A-{test_type}", athlete_id="ATH-100", test_type=test_type,
        raw_score=1.0, normalized_score=normalized_score, confidence=95.0,
        validation_score=96.0, timestamp=ts or datetime(2026, 1, 1, 12, 0, 0), status="VALID",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Correctness regression: the sit-up benchmark key ("situp" -> "sit_up").
# Before the fix, every sit-up lookup missed and fell back to mean=20/std=5, so an
# average rep count scored ~99. With the key fixed it scores near its true percentile.
# ─────────────────────────────────────────────────────────────────────────────
def test_situp_key_regression_not_inflated():
    # 17yo male, 35 reps: sits just below the 16-18 male mean (37) -> clearly sub-average,
    # NOT the ~99 the old "situp"-key bug produced.
    score = _score(35, "sit_up", 17, "Male")
    assert score < 60.0, "sit-up 35 reps @17M must not be inflated (was ~99 under the key bug)"
    assert 30.0 <= score <= 50.0

    # A mid rep count for a 15yo male is around average, never elite.
    assert _score(34, "sit_up", 15, "Male") < 70.0


def test_score_normalization():
    # 15yo male, 34 sit-ups: interpolated mean ~32.3 -> a hair above average.
    norm_score, status, src = BenchmarkingEngine.normalize_score(
        raw_score=34.0, test_type="sit_up", age=15, category="Male"
    )
    assert 50.0 < norm_score < 70.0
    assert status in VALID_TIERS
    assert status == "Average"
    assert "Prototype" in src  # per-test provenance is surfaced


# ─────────────────────────────────────────────────────────────────────────────
# Per-year interpolation: coarse 3-year buckets are gone.
# ─────────────────────────────────────────────────────────────────────────────
def test_norms_interpolate_per_year():
    # Same raw reps, different ages -> different scores (older peers have a higher mean).
    s10 = _score(25, "sit_up", 10, "Male")
    s12 = _score(25, "sit_up", 12, "Male")
    s13 = _score(25, "sit_up", 13, "Male")

    assert s10 != s12, "a 10- and a 12-year-old must not score identically (per-year norms)"
    assert s10 > s12 > s13, "for fixed reps, older peers (higher mean) score lower"
    assert (s10 - s12) > 10.0, "the per-year difference should be material, not cosmetic"


# ─────────────────────────────────────────────────────────────────────────────
# Direction is registry-driven: for timed tests, lower is better.
# ─────────────────────────────────────────────────────────────────────────────
def test_lower_is_better_for_timed_tests():
    fast = _score(10.0, "shuttle_run", 14, "Male")
    slow = _score(13.0, "shuttle_run", 14, "Male")
    assert fast > slow, "a faster (lower) shuttle time must score higher"
    assert fast > 80.0 and slow < 20.0

    # Same story for the two new manual timed tests.
    assert _score(6.5, "sprint_50m", 16, "Male") > _score(8.0, "sprint_50m", 16, "Male")
    assert _score(110, "endurance_run", 16, "Male") > _score(160, "endurance_run", 16, "Male")


# ─────────────────────────────────────────────────────────────────────────────
# BMI is a two-sided optimal band: both under- and over-weight reduce the score.
# ─────────────────────────────────────────────────────────────────────────────
def test_bmi_two_sided_optimal_band():
    assert settings.TEST_REGISTRY["bmi"]["direction"] == "optimal_band"

    center = _score(21.0, "bmi", 16, "Male")   # near the healthy-band centre
    under = _score(13.0, "bmi", 16, "Male")    # well underweight
    over = _score(30.0, "bmi", 16, "Male")     # well overweight

    assert center > 80.0, "a mid-band BMI should score high"
    assert under < center and over < center, "both directions must be penalised"
    assert under < 50.0 and over < 50.0, "far from the band scores poorly either way"


# ─────────────────────────────────────────────────────────────────────────────
# Every new battery test normalises in the correct direction, with provenance.
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("test_type,better,worse,age", [
    ("sprint_50m", 6.5, 8.0, 16),        # seconds, lower better
    ("endurance_run", 110.0, 170.0, 16), # seconds, lower better
    ("sit_and_reach", 15.0, 0.0, 16),    # cm, higher better
    ("broad_jump", 240.0, 150.0, 16),    # cm, higher better
])
def test_new_tests_normalize_directionally(test_type, better, worse, age):
    hi, _st_hi, src = BenchmarkingEngine.normalize_score(better, test_type, age, "Male")
    lo, _st_lo, _src = BenchmarkingEngine.normalize_score(worse, test_type, age, "Male")
    assert hi > lo, f"{test_type}: {better} should out-score {worse}"
    assert 1.0 <= lo <= 99.0 and 1.0 <= hi <= 99.0
    assert "Prototype" in src


def test_unknown_test_does_not_crash():
    # An unregistered test type falls back to neutral norms rather than raising.
    score, status, _src = BenchmarkingEngine.normalize_score(20.0, "made_up_test", 15, "Male")
    assert 1.0 <= score <= 99.0
    assert status in VALID_TIERS


# ─────────────────────────────────────────────────────────────────────────────
# Athletic Performance Index: real domain mapping + weighted geometric mean.
# ─────────────────────────────────────────────────────────────────────────────
def test_athletic_performance_index_calculator():
    assessments = [
        _assessment("sit_up", 80.0),        # -> strength
        _assessment("vertical_jump", 85.0), # -> power
        _assessment("shuttle_run", 82.0),   # -> agility (NOT speed)
    ]
    index_data = AthleticPerformanceIndexCalculator.calculate_index(assessments)

    assert index_data["strength_score"] == 80.0
    assert index_data["power_score"] == 85.0
    assert index_data["agility_score"] == 82.0
    # Speed now comes from sprint_50m only; with none recorded it shows the display placeholder
    # and does NOT contribute to the overall index.
    assert index_data["speed_score"] == 50.0
    assert index_data["endurance_score"] == 50.0
    assert index_data["overall_index"] > 80.0
    assert index_data["tests_completed"] == 3


def test_partial_battery_renormalises_weights():
    # A single measured domain -> the overall index equals that domain (weights renormalise),
    # instead of being dragged toward zero by the untested four.
    index_data = AthleticPerformanceIndexCalculator.calculate_index([_assessment("sit_up", 70.0)])
    assert index_data["overall_index"] == 70.0
    assert index_data["strength_score"] == 70.0
    assert index_data["speed_score"] == 50.0  # placeholder, not counted


def test_geometric_mean_penalises_imbalance():
    # Balanced {60,60,60}: geometric == arithmetic == 60.
    balanced = AthleticPerformanceIndexCalculator.calculate_index([
        _assessment("sit_up", 60.0), _assessment("vertical_jump", 60.0), _assessment("shuttle_run", 60.0),
    ])["overall_index"]

    # Unbalanced {20,100,60}: same arithmetic mean (60) but the geometric mean is lower,
    # because one very weak domain is penalised more heavily.
    unbalanced = AthleticPerformanceIndexCalculator.calculate_index([
        _assessment("sit_up", 20.0), _assessment("vertical_jump", 100.0), _assessment("shuttle_run", 60.0),
    ])["overall_index"]

    assert abs(balanced - 60.0) < 0.5
    assert unbalanced < balanced
    assert unbalanced < 60.0, "geometric mean must sit below the arithmetic mean when domains are unbalanced"


def test_power_domain_averages_vertical_and_broad_jump():
    # Power is fed by BOTH vertical_jump and broad_jump; the domain averages their latest scores.
    index_data = AthleticPerformanceIndexCalculator.calculate_index([
        _assessment("vertical_jump", 80.0), _assessment("broad_jump", 90.0),
    ])
    assert index_data["power_score"] == 85.0
