"""
One-off recompute / backfill utility for the fitness-scoring upgrade (SIH 25073, Phase 5).

Why this exists
---------------
Historical assessments were normalized by the *old* engine, which had a benchmark-key bug
(the sit-up table was keyed "situp" but looked up as "sit_up", so every sit-up silently used
the neutral fallback mean=20/std=5 and scored far too high). Derived Performance rows inherited
those wrong scores, and older rows predate the flexibility / body-composition domains entirely.

What it does (idempotent — safe to run repeatedly)
--------------------------------------------------
  1. Re-normalizes every stored Assessment with the fixed, registry-driven engine.
  2. Re-signs any assessment whose normalized_score changed, so the tamper-evident
     certificate signature stays valid (normalized_score is a signed field — leaving the
     old signature would make /verify report a false "signature_mismatch").
  3. Rebuilds every athlete's Performance row via the app's own _persist_performance(),
     folding in a freshly computed BMI and the new flexibility / body-composition domains,
     using the exact same code path the live API uses (single source of truth).

Run with:  python recompute_benchmarks.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.abspath("."))

from app.database.session import init_db, SessionLocal
from app.models.db_models import Athlete, Assessment
from app.scoring_engine.benchmarker import BenchmarkingEngine
from app.services import verification as cert_sig
# Reuse the API's persistence helper so the recompute matches the live scoring path exactly.
from app.api.routes import _persist_performance

# Scores are stored rounded to 1 dp; treat sub-0.05 differences as "unchanged".
_EPS = 0.05


def _recompute_assessment(athlete: Athlete, asm: Assessment) -> bool:
    """Re-normalize and (if changed) re-sign one assessment. Returns True if it changed."""
    new_score, _status, _src = BenchmarkingEngine.normalize_score(
        asm.raw_score, asm.test_type, athlete.age, athlete.category
    )
    old_score = float(asm.normalized_score) if asm.normalized_score is not None else None
    if old_score is not None and abs(new_score - old_score) < _EPS:
        return False

    asm.normalized_score = new_score
    # Re-sign over the corrected fields (sign_assessment reads the row's current values,
    # which is exactly what the public /verify endpoint recomputes).
    details = {}
    if asm.details_json:
        try:
            details = json.loads(asm.details_json)
        except (ValueError, TypeError):
            details = {}
    details[cert_sig.SIGNATURE_KEY] = cert_sig.sign_assessment(asm)
    asm.details_json = json.dumps(details)
    return True


def main():
    print("=" * 70)
    print("  RECOMPUTE BENCHMARKS & PERFORMANCE INDEX (fixed scoring engine)")
    print("=" * 70)

    init_db()  # applies the idempotent flexibility_score / body_composition_score migration
    db = SessionLocal()
    try:
        athletes = db.query(Athlete).all()
        total_assessments = 0
        total_changed = 0
        athletes_touched = 0

        for athlete in athletes:
            assessments = db.query(Assessment).filter(
                Assessment.athlete_id == athlete.athlete_id
            ).all()

            changed_here = 0
            for asm in assessments:
                total_assessments += 1
                if _recompute_assessment(athlete, asm):
                    changed_here += 1
            if changed_here:
                db.commit()  # persist corrected scores + signatures before rebuilding the index

            # Rebuild the Performance row from the (now-correct) assessments + live BMI.
            index_data, bmi = _persist_performance(db, athlete)

            total_changed += changed_here
            athletes_touched += 1
            print(f"  {athlete.athlete_id:<18} {athlete.name:<22} "
                  f"corrected {changed_here:>2}/{len(assessments):<2} assessments  "
                  f"| index={index_data['overall_index']:>5}/100  "
                  f"| BMI={bmi if bmi is not None else 'n/a'}")

        print("-" * 70)
        print(f"  Athletes processed        : {athletes_touched}")
        print(f"  Assessments re-normalized : {total_changed} changed / {total_assessments} total")
        print(f"  Performance rows rebuilt  : {athletes_touched} (incl. flexibility + body composition)")
        print("=" * 70)
        print("  Done. Re-signed every corrected record — /verify remains authentic.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
