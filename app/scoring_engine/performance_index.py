"""
Athletic Performance Index (API) Engine.
Implements Section 16 of SIH 25073 specification
(combines Speed, Agility, Strength, Explosive Power, and Endurance).

Upgrades over the prototype:
  * Every domain is now backed by a REAL measured test instead of magic-constant proxies
    (the old `agility = shuttle*0.96+3` / `endurance = situp*0.95+5` are gone).
  * Overall index is a true WEIGHTED GEOMETRIC MEAN over the domains that actually have data,
    with weights renormalised for a partial battery. Geometric mean rewards all-round athletes
    and penalises a single very weak domain more than an arithmetic mean would.
  * Flexibility (sit & reach) and Body Composition (BMI) are reported as extra indicators.
"""

import math
from typing import List, Dict, Any, Optional
from app.models.db_models import Assessment
from app.core.config import settings

# Domain -> the test(s) that feed it. A domain fed by several tests averages their latest scores.
DOMAIN_TESTS: Dict[str, List[str]] = {
    "speed": ["sprint_50m"],
    "agility": ["shuttle_run"],
    "strength": ["sit_up"],
    "power": ["vertical_jump", "broad_jump"],
    "endurance": ["endurance_run"],
    "flexibility": ["sit_and_reach"],
}

# The five domains that make up the headline Athletic Performance Index, and their weights.
ATHLETIC_DOMAINS = ["speed", "agility", "strength", "power", "endurance"]
DOMAIN_WEIGHTS: Dict[str, float] = {
    "speed": 0.20, "agility": 0.20, "strength": 0.20, "power": 0.20, "endurance": 0.20,
}

# Neutral placeholder shown for a domain the athlete has not yet been tested on.
# It is used for DISPLAY only — it never contributes to the overall index.
NO_DATA_PLACEHOLDER = 50.0


class AthleticPerformanceIndexCalculator:
    @staticmethod
    def _latest_valid(assessments: List[Assessment], test_type: str) -> Optional[Assessment]:
        rows = [a for a in assessments
                if a.test_type == test_type and a.status != "INVALID" and a.normalized_score is not None]
        return max(rows, key=lambda x: x.timestamp) if rows else None

    @classmethod
    def _domain_score(cls, assessments: List[Assessment], domain: str) -> Optional[float]:
        """Average of the latest valid normalized score for each test feeding this domain."""
        scores = []
        for test_type in DOMAIN_TESTS.get(domain, []):
            latest = cls._latest_valid(assessments, test_type)
            if latest is not None:
                scores.append(float(latest.normalized_score))
        if not scores:
            return None
        return round(sum(scores) / len(scores), 1)

    @classmethod
    def calculate_index(cls, assessments: List[Assessment],
                        bmi_score: Optional[float] = None) -> Dict[str, Any]:
        """
        Computes domain sub-scores and the overall Athletic Performance Index from an
        athlete's assessment history. `bmi_score` (0-100) may be supplied by the caller
        after computing BMI from the live profile; otherwise a stored 'bmi' assessment is used.
        """
        # Real domain scores (None when the athlete hasn't taken any feeding test).
        domain_scores: Dict[str, Optional[float]] = {
            d: cls._domain_score(assessments, d) for d in DOMAIN_TESTS
        }

        # Body composition: prefer a freshly computed BMI score, else a stored bmi assessment.
        if bmi_score is None:
            bmi_row = cls._latest_valid(assessments, "bmi")
            bmi_score = float(bmi_row.normalized_score) if bmi_row else None

        # Overall = weighted GEOMETRIC mean over the athletic domains that have real data.
        present = [(d, domain_scores[d]) for d in ATHLETIC_DOMAINS if domain_scores[d] is not None]
        if present:
            total_w = sum(DOMAIN_WEIGHTS[d] for d, _ in present)
            log_sum = sum(DOMAIN_WEIGHTS[d] * math.log(max(s, 1.0)) for d, s in present)
            overall_index = round(float(math.exp(log_sum / total_w)), 1)
        else:
            overall_index = 0.0

        def display(domain: str) -> float:
            v = domain_scores.get(domain)
            return round(v, 1) if v is not None else NO_DATA_PLACEHOLDER

        # Count distinct measured tests (battery completeness) for scouts.
        tested = {a.test_type for a in assessments if a.status != "INVALID"}
        if bmi_score is not None:
            tested.add("bmi")
        tests_completed = len([t for t in tested if t in settings.TEST_REGISTRY])

        return {
            "speed_score": display("speed"),
            "agility_score": display("agility"),
            "strength_score": display("strength"),
            "power_score": display("power"),
            "endurance_score": display("endurance"),
            "flexibility_score": display("flexibility"),
            "body_composition_score": round(bmi_score, 1) if bmi_score is not None else NO_DATA_PLACEHOLDER,
            "overall_index": overall_index,
            "tests_completed": tests_completed,
            "domains_assessed": [d for d, _ in present],
        }
