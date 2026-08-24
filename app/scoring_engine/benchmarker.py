"""
Benchmarking System & Score Normalization Engine.
Implements Section 15 of SIH 25073 specification
(Raw Result -> Age/Sex Norms -> Normalized Score -> Performance Category).

Upgrades over the prototype:
  * Direction ("higher"/"lower"/"optimal_band") is read from settings.TEST_REGISTRY
    instead of hardcoded per-test branches.
  * Norms are linearly interpolated PER YEAR between age-band midpoints, so a 10- and a
    12-year-old are no longer scored identically.
  * "General" sex is derived by averaging the Male/Female anchors.
  * BMI uses a two-sided "optimal band" model (both under- and over-weight reduce the score).
  * Each test returns its own provenance string (settings.TEST_REGISTRY[test]["source"]).
"""

from scipy.stats import norm
from typing import Dict, Any, Tuple, Optional
from app.core.config import settings

# Normalized-score clamp. Floor is >= 1 (never 0) so downstream geometric means stay finite.
SCORE_FLOOR = 1.0
SCORE_CEIL = 99.0


class BenchmarkingEngine:
    # ─── Helpers ───
    @staticmethod
    def get_gender_suffix(category: str) -> str:
        """Maps a free-form category string to a Male / Female / General norm suffix."""
        c = (category or "").lower()
        if "female" in c or c in ("f", "girl", "woman", "women"):
            return "Female"
        if "male" in c or c in ("m", "boy", "man", "men"):
            return "Male"
        return "General"

    @staticmethod
    def get_benchmark_key(age: int, category: str) -> str:
        """
        Human-readable band label for the given age & category (e.g. "13-15_Male").
        Kept for backwards compatibility / display; scoring itself interpolates per year.
        """
        suffix = BenchmarkingEngine.get_gender_suffix(category)
        for _, band in settings.AGE_BAND_MIDPOINTS:
            lo, hi = _band_range(band)
            if lo <= age <= hi:
                return f"{band}_{suffix}"
        # Below youngest / above oldest -> clamp to the nearest defined band.
        youngest = settings.AGE_BAND_MIDPOINTS[0][1]
        oldest = settings.AGE_BAND_MIDPOINTS[-1][1]
        band = youngest if age < settings.AGE_BAND_MIDPOINTS[0][0] else oldest
        return f"{band}_{suffix}"

    @staticmethod
    def _norms_for_band(band: str, suffix: str, test_type: str) -> Optional[Dict[str, float]]:
        """Norm parameters for one band; averages Male/Female when suffix is General."""
        B = settings.NORMATIVE_BENCHMARKS
        if suffix == "General":
            m = B.get(f"{band}_Male", {}).get(test_type)
            f = B.get(f"{band}_Female", {}).get(test_type)
            if m and f:
                return {k: (float(m[k]) + float(f[k])) / 2.0 for k in m}
            return dict(m) if m else (dict(f) if f else None)
        entry = B.get(f"{band}_{suffix}", {}).get(test_type)
        if entry is None:
            # Fall back to the General (M/F averaged) value for this band.
            return BenchmarkingEngine._norms_for_band(band, "General", test_type)
        return dict(entry)

    @classmethod
    def resolve_norms(cls, test_type: str, age: float, category: str) -> Optional[Dict[str, float]]:
        """
        Age-interpolated norm parameters for a test, sex, and exact age.
        Linearly interpolates every parameter between the two bracketing age-band midpoints.
        """
        suffix = cls.get_gender_suffix(category)
        mids = settings.AGE_BAND_MIDPOINTS  # ordered ascending by age

        # Clamp outside the defined range to the terminal bands.
        if age <= mids[0][0]:
            return cls._norms_for_band(mids[0][1], suffix, test_type)
        if age >= mids[-1][0]:
            return cls._norms_for_band(mids[-1][1], suffix, test_type)

        # Find the bracketing pair and interpolate.
        for i in range(len(mids) - 1):
            a0, band0 = mids[i]
            a1, band1 = mids[i + 1]
            if a0 <= age <= a1:
                n0 = cls._norms_for_band(band0, suffix, test_type)
                n1 = cls._norms_for_band(band1, suffix, test_type)
                if n0 is None or n1 is None:
                    return n0 or n1
                t = (age - a0) / (a1 - a0) if a1 > a0 else 0.0
                return {k: n0[k] + (n1[k] - n0[k]) * t for k in n0 if k in n1}
        return None

    # ─── Scoring ───
    @staticmethod
    def _percentile_from_z(z: float) -> float:
        return float(norm.cdf(z) * 100.0)

    @classmethod
    def _score_directional(cls, raw: float, norms: Dict[str, float], direction: str) -> float:
        mean = float(norms.get("mean", 0.0))
        std = float(norms.get("std", 1.0))
        if std <= 0:
            std = 1.0
        if direction == "lower":
            z = (mean - raw) / std          # lower raw time -> better
        else:
            z = (raw - mean) / std          # higher raw value -> better
        return cls._percentile_from_z(z)

    @staticmethod
    def _score_optimal_band(raw: float, norms: Dict[str, float]) -> float:
        """
        Two-sided score for metrics with a healthy band (e.g. BMI): best at the band centre,
        falling off symmetrically towards each edge and dropping further outside the band.
        """
        low = float(norms.get("optimal_low", 18.5))
        high = float(norms.get("optimal_high", 25.0))
        std = float(norms.get("std", 3.0)) or 3.0
        center = (low + high) / 2.0
        half = max((high - low) / 2.0, 1e-6)
        d = abs(raw - center) / half        # 0 at centre, 1 at either edge
        if d <= 1.0:
            # Inside the healthy band: 95 at centre -> 70 at the edge.
            return 95.0 - d * (95.0 - 70.0)
        # Outside the band: 70 at the edge, dropping 24 points per std.
        edge = high if raw > center else low
        z = abs(raw - edge) / std
        return max(SCORE_FLOOR, 70.0 - z * 24.0)

    @staticmethod
    def classify(score: float) -> str:
        """Percentile-band performance tier (labels are display-only strings)."""
        if score >= 90.0:
            return "Elite"
        if score >= 75.0:
            return "Excellent"
        if score >= 60.0:
            return "Above Average"
        if score >= 40.0:
            return "Average"
        if score >= 20.0:
            return "Developing"
        return "Needs Improvement"

    @classmethod
    def normalize_score(cls, raw_score: float, test_type: str, age: int,
                        category: str) -> Tuple[float, str, str]:
        """
        Normalizes a raw test result to a 1-99 score relative to the age & sex peer group.
        Returns: (normalized_score, performance_status, benchmark_source)
        """
        reg = settings.TEST_REGISTRY.get(test_type, {})
        direction = reg.get("direction", "higher")
        source = reg.get("source", settings.BENCHMARK_SOURCE_LABEL)

        norms = cls.resolve_norms(test_type, float(age), category)
        if norms is None:
            # Unknown test with no norms — neutral fallback keeps the pipeline alive.
            norms = {"mean": 20.0, "std": 5.0}

        if direction == "optimal_band":
            percentile = cls._score_optimal_band(raw_score, norms)
        else:
            percentile = cls._score_directional(raw_score, norms, direction)

        normalized_score = round(float(max(SCORE_FLOOR, min(SCORE_CEIL, percentile))), 1)
        return normalized_score, cls.classify(normalized_score), source

    # ─── BMI convenience ───
    @staticmethod
    def compute_bmi(height_cm: Optional[float], weight_kg: Optional[float]) -> Optional[float]:
        """Body Mass Index = kg / m^2, or None if height/weight are missing/implausible."""
        if not height_cm or not weight_kg or height_cm <= 0:
            return None
        m = height_cm / 100.0
        return round(weight_kg / (m * m), 1)


def _band_range(band: str) -> Tuple[float, float]:
    """Inclusive age range implied by a band key like '13-15' or 'Adult'."""
    if band == "Adult":
        return (19.0, 200.0)
    try:
        lo, hi = band.split("-")
        return (float(lo), float(hi))
    except ValueError:
        return (0.0, 200.0)
