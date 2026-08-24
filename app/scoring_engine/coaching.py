"""
Corrective Coaching Feedback Engine.

Turns the numeric signals an assessment already produces — the CV analyzer output
(`invalid_reps`, `min_angle_recorded`, `takeoff_detected`, `boundary_crossed`, …), the
anti-cheat `flags`, and the age/sex-normalized score — into plain-language feedback the
athlete can act on: *what went wrong* and *how to fix it*.

`generate_feedback(...)` is a **pure function** (no DB, no I/O). That lets it run both at
capture time (results endpoints) and on the fly for historical rows when a profile/scout
view is rebuilt, so every result — old or new, CV or manual — shows guidance.

Nothing here is a signed certificate field, so adding it to an assessment's `details`
never affects the tamper-evident HMAC signature.
"""

from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.scoring_engine.benchmarker import BenchmarkingEngine

# Sit-up FSM thresholds (mirror SitUpAnalyzer defaults) used to phrase range-of-motion faults.
_SITUP_UP_THRESHOLD = 65.0     # hip angle at the top of a full sit-up (torso toward knees)
_SITUP_DOWN_THRESHOLD = 135.0  # hip angle when lying back down

# Per-test training tips used by the norm-based layer when a result is below the peer group.
_TRAINING_TIPS: Dict[str, str] = {
    "sit_up": "Build core strength with planks, leg raises and slow controlled crunches 3-4 times a week.",
    "vertical_jump": "Train explosive power: squats, jump squats and box jumps; focus on a fast, deep dip before you jump.",
    "broad_jump": "Build leg power with broad-jump practice, lunges and single-leg bounds, driving both arms forward.",
    "shuttle_run": "Sharpen agility with ladder drills and cone shuttles; practise braking hard and re-accelerating out of the turn.",
    "sprint_50m": "Work on speed with short sprint intervals and standing-start acceleration drills; keep your running form tall and relaxed.",
    "endurance_run": "Build endurance with tempo runs and intervals (e.g. 4-6 x 200m) three times a week, and pace yourself evenly.",
    "sit_and_reach": "Improve flexibility with daily hamstring and lower-back stretching, holding each stretch 20-30 seconds.",
}


def _fault(issue: str, severity: str = "medium") -> Dict[str, str]:
    return {"issue": issue, "severity": severity}


def _fmt(value: float, digits: int = 0) -> str:
    """Compact numeric formatting for feedback strings (drops a trailing .0)."""
    try:
        v = round(float(value), digits)
    except (TypeError, ValueError):
        return str(value)
    return str(int(v)) if digits == 0 or v == int(v) else str(v)


def _flag_faults(flags: List[str]) -> (List[Dict[str, str]], List[str]):
    """Map anti-cheat / capture flags to recording-quality faults and fixes."""
    faults: List[Dict[str, str]] = []
    improvements: List[str] = []
    seen = set()

    def add(issue, sev, fix):
        key = (issue, fix)
        if key in seen:
            return
        seen.add(key)
        faults.append(_fault(issue, sev))
        improvements.append(fix)

    for f in flags or []:
        if f in ("INSUFFICIENT_VIDEO_FRAMES", "ATHLETE_DISAPPEARED_MID_TEST"):
            add("Part of the test wasn't captured — you left the frame or the clip was too short.",
                "high",
                "Keep your whole body in view for the entire movement and record a slightly longer, continuous clip.")
        elif f == "PROTOCOL_VIOLATION_OR_INCOMPLETE":
            add("The movement didn't fully match the test protocol.",
                "high",
                "Follow each step of the on-screen protocol and complete the full test before stopping.")
        elif f in ("SUDDEN_PERSON_POSITION_JUMP", "UNNATURAL_MOTION_SPEED_SPIKE"):
            add("The video showed sudden jumps in motion (camera movement or an edited clip).",
                "medium",
                "Use a fixed, propped-up camera and record the whole test in one unedited take.")
    return faults, improvements


# ─────────────────────────────────────────────────────────────────────────────
# Per-test rule sets — each reads only from `details` (the analyzer output).
# Returns (faults, improvements, strengths).
# ─────────────────────────────────────────────────────────────────────────────

def _situp_rules(details: Dict[str, Any]):
    faults, improvements, strengths = [], [], []
    total = int(details.get("total_reps", 0) or 0)
    valid = int(details.get("valid_reps", 0) or 0)
    invalid = int(details.get("invalid_reps", 0) or 0)
    form = float(details.get("form_score", 0.0) or 0.0)
    cadence = float(details.get("rhythm_consistency_score", 100.0) or 100.0)
    min_angle = float(details.get("min_angle_recorded", 0.0) or 0.0)
    max_angle = float(details.get("max_angle_recorded", 180.0) or 180.0)

    # Range of motion — coming up.
    if min_angle > 90.0:
        faults.append(_fault(
            f"You're not sitting up far enough — your torso only closed to about {_fmt(min_angle)}deg "
            f"(a full sit-up brings it under {_fmt(_SITUP_UP_THRESHOLD)}deg).", "high"))
        improvements.append("Curl all the way up until your chest is close to your thighs and your elbows reach your knees.")
    elif min_angle > _SITUP_UP_THRESHOLD + 8.0:
        faults.append(_fault("You're stopping just short of a full sit-up at the top.", "medium"))
        improvements.append("Squeeze a little higher at the top of each rep so you reach the full up position.")

    # Range of motion — going back down.
    if max_angle < _SITUP_DOWN_THRESHOLD - 15.0:
        faults.append(_fault("You aren't lowering all the way back down between reps.", "medium"))
        improvements.append("Lower under control until your shoulder blades touch the floor before the next rep.")

    # Incomplete reps.
    if total > 0 and invalid > 0:
        ratio = invalid / total
        if ratio >= 0.3:
            faults.append(_fault(
                f"{_fmt(ratio * 100)}% of your reps ({invalid} of {total}) didn't count because the range of motion was incomplete.",
                "high"))
            improvements.append("Slow down slightly and complete the full up-and-down range on every rep — quality beats speed.")
        elif ratio > 0.0:
            faults.append(_fault(f"{invalid} of your {total} reps didn't count as full sit-ups.", "low"))
            improvements.append("Focus on completing each rep fully so more of them count.")

    # Cadence.
    if cadence < 60.0 and total >= 3:
        faults.append(_fault(f"Your rep timing was uneven (rhythm score {_fmt(cadence)}%).", "low"))
        improvements.append("Aim for a steady tempo — roughly one sit-up every 1.5-2 seconds.")

    # Strengths.
    if valid >= 1 and form >= 90.0:
        strengths.append(f"Excellent form — {_fmt(form)}% of your reps were full, valid sit-ups.")
    if cadence >= 85.0 and total >= 5:
        strengths.append("Your pacing was smooth and consistent throughout.")
    return faults, improvements, strengths


def _jump_rules(details: Dict[str, Any], horizontal: bool):
    """Shared take-off/landing/framing rules for vertical and broad jump."""
    faults, improvements, strengths = [], [], []
    takeoff = bool(details.get("takeoff_detected", False))
    landing = bool(details.get("landing_detected", False))
    flight = float(details.get("flight_time_sec", 0.0) or 0.0)
    view = "from the side" if horizontal else "so your whole body (head to feet) is in view"

    if not takeoff:
        faults.append(_fault("A clear take-off wasn't detected — you may have started out of frame or not left the ground cleanly.", "high"))
        improvements.append(f"Stand {view} and begin with both feet flat, then perform one clear, committed jump.")
    if not landing:
        faults.append(_fault("Your landing wasn't captured — you likely moved out of frame.", "high"))
        improvements.append("Move the camera back far enough that you stay fully in frame through the whole jump and landing.")

    if takeoff and landing and 0.0 < flight < 0.35:
        faults.append(_fault(f"Your flight time was short ({_fmt(flight, 2)}s), which limits the measured jump.", "medium"))
        if horizontal:
            improvements.append("Swing both arms back then explosively forward and drive your knees out to extend the jump.")
        else:
            improvements.append("Add a deeper counter-movement dip and a full arm swing to drive higher off the ground.")

    if horizontal:
        # Technique + officiating note that's always useful for broad jump.
        improvements.append("Land softly on both feet with bent knees; for an official record have the distance tape-measured and entered.")

    if takeoff and landing and flight >= 0.45:
        strengths.append("Strong, clean jump — take-off and landing were both captured with good air time.")
    return faults, improvements, strengths


def _shuttle_rules(details: Dict[str, Any]):
    faults, improvements, strengths = [], [], []
    boundary = bool(details.get("boundary_crossed", False))
    valid = bool(details.get("valid_run", False))
    turn = float(details.get("turnaround_time_sec", 0.0) or 0.0)

    if not boundary:
        faults.append(_fault("You didn't reach the far line, so the shuttle is incomplete.", "high"))
        improvements.append("Run all the way past the far line before you turn — a full 10m each way.")
    if not valid and boundary:
        faults.append(_fault("The run didn't register as a valid out-and-back shuttle.", "high"))
        improvements.append("Complete the full course with a clear touch and turn at each line.")
    if turn > 1.0:
        faults.append(_fault(f"Your turn was slow (about {_fmt(turn, 1)}s at the line).", "medium"))
        improvements.append("Plant your foot on the line, drop your hips low, and push off hard to change direction faster.")

    if valid and turn > 0 and turn <= 0.7:
        strengths.append("Sharp, low turns — you changed direction efficiently.")
    return faults, improvements, strengths


def _bmi_rules(raw_score: float, age: Optional[int], category: Optional[str]):
    faults, improvements, strengths = [], [], []
    band = None
    if age is not None:
        band = BenchmarkingEngine.resolve_norms("bmi", float(age), category or "General")
    if not band:
        return faults, improvements, strengths

    low = float(band.get("optimal_low", 18.5))
    high = float(band.get("optimal_high", 25.0))
    if raw_score < low:
        faults.append(_fault(
            f"Your BMI ({_fmt(raw_score, 1)}) is below the healthy range ({_fmt(low, 1)}-{_fmt(high, 1)}) for your age and sex.",
            "medium"))
        improvements.append("Focus on balanced nutrition with enough protein and healthy calories, alongside strength training, to build healthy mass.")
    elif raw_score > high:
        faults.append(_fault(
            f"Your BMI ({_fmt(raw_score, 1)}) is above the healthy range ({_fmt(low, 1)}-{_fmt(high, 1)}) for your age and sex.",
            "medium"))
        improvements.append("Combine regular aerobic activity with a balanced diet to move toward the healthy range; check with a coach or doctor for a personal plan.")
    else:
        strengths.append(f"Your BMI ({_fmt(raw_score, 1)}) sits in the healthy range for your age and sex.")
    return faults, improvements, strengths


_CV_RULES = {
    "sit_up": lambda d, raw, age, cat: _situp_rules(d),
    "vertical_jump": lambda d, raw, age, cat: _jump_rules(d, horizontal=False),
    "broad_jump": lambda d, raw, age, cat: _jump_rules(d, horizontal=True),
    "shuttle_run": lambda d, raw, age, cat: _shuttle_rules(d),
    "bmi": lambda d, raw, age, cat: _bmi_rules(raw, age, cat),
}


def generate_feedback(test_type: str, raw_score: float, normalized_score: float,
                      details: Optional[Dict[str, Any]] = None,
                      age: Optional[int] = None, category: Optional[str] = None) -> Dict[str, Any]:
    """
    Build corrective feedback for one assessment.

    Returns: {summary, score_band, faults: [{issue, severity}], improvements: [str], strengths: [str]}.
    Pure and defensive — always returns a well-formed dict even for unknown tests or empty details.
    """
    details = details or {}
    reg = settings.TEST_REGISTRY.get(test_type, {})
    unit = reg.get("unit", "")
    band = BenchmarkingEngine.classify(float(normalized_score or 0.0))

    faults: List[Dict[str, str]] = []
    improvements: List[str] = []
    strengths: List[str] = []

    # 1. Capture-quality faults from the anti-cheat flags (CV tests only).
    flags = (details.get("verification") or {}).get("flags", []) if isinstance(details.get("verification"), dict) else []
    f_faults, f_improvements = _flag_faults(flags)
    faults += f_faults
    improvements += f_improvements

    # 2. Test-specific technique faults, derived from the analyzer signals.
    rule = _CV_RULES.get(test_type)
    if rule:
        t_faults, t_improvements, t_strengths = rule(details, float(raw_score or 0.0), age, category)
        faults += t_faults
        improvements += t_improvements
        strengths += t_strengths

    # 3. Norm-based layer — applies to EVERY test (incl. manual sprint/run/reach), so a result
    #    with no rich CV signals still gets guidance relative to the athlete's peer group.
    norms = None
    if age is not None:
        norms = BenchmarkingEngine.resolve_norms(test_type, float(age), category or "General")
    peer_mean = norms.get("mean") if norms else None

    if normalized_score < 40.0:
        tip = _TRAINING_TIPS.get(test_type)
        if tip:
            improvements.append(tip)
        if peer_mean is not None and test_type != "bmi":
            better = "faster" if reg.get("direction") == "lower" else "higher"
            improvements.append(
                f"The typical result for your age and sex is about {_fmt(peer_mean, 1)} {unit} — "
                f"aim to move your score {better} toward that mark.")
    elif normalized_score >= 75.0 and not strengths:
        strengths.append(f"This is a {band} result for your age and sex group — strong work.")

    # De-duplicate while preserving order.
    def _dedupe(items):
        out, seen = [], set()
        for it in items:
            key = it["issue"] if isinstance(it, dict) else it
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out

    faults = _dedupe(faults)
    improvements = _dedupe(improvements)
    strengths = _dedupe(strengths)

    # 4. One-line summary.
    if faults:
        top = faults[0]["issue"]
        summary = f"{band} result. Biggest thing to fix: {top}"
    elif normalized_score >= 75.0:
        summary = f"{band} result — excellent work. Keep training to push it even higher."
    elif improvements:
        summary = f"{band} result. Your setup looked clean — follow the tips below to raise your score."
    else:
        summary = f"{band} result. Solid, balanced effort."

    return {
        "summary": summary,
        "score_band": band,
        "faults": faults,
        "improvements": improvements,
        "strengths": strengths,
    }
