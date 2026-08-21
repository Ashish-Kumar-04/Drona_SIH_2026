"""
Benchmarking System & Score Normalization Engine.
Implements Section 15 of SIH 25073 specification (Raw Result -> Age/Category Norms -> Normalized Score -> Performance Category).
"""

from scipy.stats import norm
from typing import Dict, Any, Tuple
from app.core.config import settings

class BenchmarkingEngine:
    @staticmethod
    def get_benchmark_key(age: int, category: str) -> str:
        """Determines appropriate demographic benchmark group key."""
        cat_suffix = "Male" if "male" in category.lower() and "female" not in category.lower() else "Female" if "female" in category.lower() else "General"
        
        if 10 <= age <= 12:
            return f"10-12_{cat_suffix}"
        elif 13 <= age <= 15:
            return f"13-15_{cat_suffix}"
        elif 16 <= age <= 18:
            return f"16-18_{cat_suffix}"
        else:
            return "General"

    @classmethod
    def normalize_score(cls, raw_score: float, test_type: str, age: int, category: str) -> Tuple[float, str, str]:
        """
        Normalizes a raw test result to a 0-100 score relative to age & category peer group.
        Returns: (normalized_score, performance_status, benchmark_source)
        """
        key = cls.get_benchmark_key(age, category)
        benchmarks = settings.NORMATIVE_BENCHMARKS.get(key, settings.NORMATIVE_BENCHMARKS["General"])
        test_norm = benchmarks.get(test_type, {"mean": 20.0, "std": 5.0})

        mean = test_norm["mean"]
        std = test_norm["std"]

        if std <= 0:
            std = 1.0

        # For shuttle run, LOWER raw time is BETTER score
        if test_type == "shuttle_run":
            z_score = (mean - raw_score) / std
        else:
            # For sit-up and vertical jump, HIGHER raw score is BETTER
            z_score = (raw_score - mean) / std

        # Convert Z-score to 0-100 percentile score using CDF
        percentile = norm.cdf(z_score) * 100.0
        
        # Scale & clamp score between 10.0 and 99.0
        normalized_score = round(float(max(10.0, min(99.0, percentile))), 1)

        # Categorize performance status
        if normalized_score >= 85.0:
            status = "Elite"
        elif normalized_score >= 70.0:
            status = "Above Benchmark"
        elif normalized_score >= 45.0:
            status = "Average"
        else:
            status = "Below Benchmark"

        return normalized_score, status, settings.BENCHMARK_SOURCE_LABEL
