# Fitness Benchmarks & Normative Standards — Provenance and Validation

**Problem statement:** SIH 25073 — AI Sports Talent Assessment Platform (Sports Authority of India).

> ⚠️ **Honesty note.** The numeric norms in this platform are **documented, cited best-estimates**
> aligned to published youth fitness batteries (Khelo India, Eurofit, AAHPERD / FITNESSGRAM) and
> IAP / WHO BMI percentiles. They are **NOT** SAI's official percentile tables — those are not
> publicly available for automated ingestion. Every norm is clearly labelled "Prototype …
> validate vs SAI tables" in the API responses and on certificates. Section 6 below is the checklist
> for swapping in the official numbers before any production / decision-making use.

---

## 1. How a raw result becomes a score

The pipeline (Section 15 of the spec) is:

```
raw result ──► age/sex norm lookup ──► z-score ──► percentile (normal CDF) ──► clamp 1–99 ──► tier label
```

Implemented in [`app/scoring_engine/benchmarker.py`](../app/scoring_engine/benchmarker.py):

- **Direction** is read from `settings.TEST_REGISTRY[test]["direction"]` — not hardcoded:
  - `higher` → larger raw value is better (reps, cm): `z = (raw − mean) / std`
  - `lower` → smaller raw value is better (seconds): `z = (mean − raw) / std`
  - `optimal_band` → closeness to a healthy band is better (BMI): two-sided scoring (§4).
- **Per-year interpolation.** Norms are anchored at age-band *midpoints* and **linearly
  interpolated per exact age**, so a 10- and a 12-year-old are no longer scored identically.
  Ages below the youngest / above the oldest anchor clamp to the terminal band.
- **"General" sex** (unknown/other) is the average of the Male and Female anchors.
- **Clamp** to `[1, 99]` (never 0) so downstream geometric means stay finite.

### Tier thresholds (percentile bands)

| Score | Tier |
|------:|------|
| ≥ 90 | Elite |
| ≥ 75 | Excellent |
| ≥ 60 | Above Average |
| ≥ 40 | Average |
| ≥ 20 | Developing |
| < 20 | Needs Improvement |

Labels are display-only strings (rendered in `AthleteProfileView.jsx` / `LiveMetricsHUD.jsx`); changing
them breaks no enum.

---

## 2. The test battery (registry)

Single source of truth: `settings.TEST_REGISTRY` in [`app/core/config.py`](../app/core/config.py),
mirrored on the frontend by [`frontend/src/utils/tests.js`](../frontend/src/utils/tests.js).

| Test id | Component / domain | Unit | Direction | Capture | Feasibility rationale |
|---|---|---|---|---|---|
| `sit_up` | Strength (core) | reps/60s | higher | **CV** | pose FSM on hip/torso angle |
| `vertical_jump` | Explosive power | cm | higher | **CV** | flight-time kinematics |
| `shuttle_run` | Agility | sec | lower | **CV** | 2D trajectory + boundary crossings |
| `broad_jump` | Leg power | cm | higher | **CV** (+ manual fallback) | horizontal COM displacement; tape value authoritative when officiated |
| `sprint_50m` | Speed | sec | lower | **manual** | can't reliably time 50 m from one phone clip |
| `endurance_run` (600 m) | Endurance | sec | lower | **manual** | not CV-measurable from a single clip |
| `sit_and_reach` | Flexibility | cm | higher | **manual** | needs a physical box; CV calibration unreliable |
| `bmi` | Body composition | kg/m² | optimal_band | **computed** | from profile height + weight |

`plausible_min` / `plausible_max` in the registry are hard sanity bounds used to reject typos / fraud
on manual entry (`POST /assessment/manual-entry`).

---

## 3. Normative anchor values (per age-band midpoint × sex)

Age-band midpoints used for interpolation: **8.5 (8–9), 11 (10–12), 14 (13–15), 17 (16–18), 22 (Adult 19+)**.
Values below are `mean` (reps/cm/sec); each stored entry also carries a `std`.

### Male

| Age band | sit_up (reps) | vertical_jump (cm) | shuttle_run (s) | sprint_50m (s) | endurance_run 600m (s) | sit_and_reach (cm) | broad_jump (cm) |
|---|--:|--:|--:|--:|--:|--:|--:|
| 8–9 | 16 | 22 | 13.5 | 9.8 | 165 | 2 | 120 |
| 10–12 | 22 | 28 | 12.6 | 8.9 | 150 | 3 | 145 |
| 13–15 | 30 | 38 | 11.3 | 7.9 | 135 | 4 | 180 |
| 16–18 | 37 | 48 | 10.5 | 7.1 | 125 | 6 | 210 |
| Adult | 34 | 50 | 10.3 | 6.9 | 120 | 7 | 215 |

### Female

| Age band | sit_up (reps) | vertical_jump (cm) | shuttle_run (s) | sprint_50m (s) | endurance_run 600m (s) | sit_and_reach (cm) | broad_jump (cm) |
|---|--:|--:|--:|--:|--:|--:|--:|
| 8–9 | 14 | 20 | 14.2 | 10.2 | 175 | 4 | 110 |
| 10–12 | 19 | 25 | 13.3 | 9.4 | 162 | 6 | 135 |
| 13–15 | 25 | 31 | 12.3 | 8.7 | 150 | 9 | 155 |
| 16–18 | 29 | 36 | 11.6 | 8.3 | 145 | 12 | 170 |
| Adult | 27 | 37 | 11.5 | 8.2 | 142 | 13 | 172 |

### BMI optimal band (kg/m², both sexes per band)

| Age band | optimal_low | optimal_high |
|---|--:|--:|
| 8–9 | 14.0 | 18.5 |
| 10–12 | 14.5 | 20.5 |
| 13–15 | 16.0 | 22.5 |
| 16–18 | 17.5 | 24.5 |
| Adult | 18.5 | 25.0 |

*(Full `std` values are in `NORMATIVE_BENCHMARKS`; they widen with age to reflect greater spread.)*

### Basis / citation per test

| Test | Aligned to | Registry `source` string |
|---|---|---|
| sit_up | AAHPERD / Khelo India 60 s sit-up | "Prototype norm aligned to AAHPERD / Khelo India 60s sit-up data - validate vs SAI tables" |
| vertical_jump | Eurofit / FITNESSGRAM vertical jump | "… Eurofit / FITNESSGRAM vertical-jump data …" |
| shuttle_run | Eurofit 4×10 m shuttle | "… Eurofit 4x10m shuttle data …" |
| sprint_50m | Khelo India 50 m dash | "… Khelo India 50m dash data …" |
| endurance_run | Khelo India 600 m run | "… Khelo India 600m run data …" |
| sit_and_reach | Eurofit sit-and-reach | "… Eurofit sit-and-reach data …" |
| broad_jump | Eurofit standing broad jump | "… Eurofit standing broad-jump data …" |
| bmi | IAP / WHO youth BMI percentiles | "Prototype optimal band aligned to IAP / WHO youth BMI percentiles - validate vs SAI tables" |

---

## 4. Two-sided BMI (optimal band) scoring

BMI is **not** "higher is better." `_score_optimal_band` (benchmarker.py):

- centre of `[optimal_low, optimal_high]` → **95**
- either band edge → **70** (linear inside the band)
- outside the band → drops **~24 points per std** away from the nearest edge, floored at 1.

So a BMI far *below* the band and a BMI far *above* it both score low — under- and over-weight are
each penalised, which a one-sided z-score cannot express.

---

## 5. Composite: Athletic Performance Index

[`app/scoring_engine/performance_index.py`](../app/scoring_engine/performance_index.py):

- Domains ← real measured tests only (the old magic-constant proxies
  `agility = shuttle*0.96+3` and `endurance = situp*0.95+5` are **removed**):
  speed ← `sprint_50m`, agility ← `shuttle_run`, strength ← `sit_up`,
  power ← avg(`vertical_jump`, `broad_jump`), endurance ← `endurance_run`.
  Reported extras: flexibility ← `sit_and_reach`, body-composition ← `bmi`.
- Overall index = **weighted geometric mean over the athletic domains that have data**, with
  weights renormalised for a partial battery (so an untested domain neither counts as zero nor as
  a fake 50). The geometric mean penalises a single very weak domain more than an arithmetic mean —
  it rewards all-round athletes.
- Untested domains display a neutral `50.0` placeholder that **never** contributes to the overall.

---

## 6. ✅ SAI validation checklist (do this before production)

Everything here is a swap-in; the engine, interpolation, tiers, and composite math stay as-is.

1. **Replace `NORMATIVE_BENCHMARKS`** in `app/core/config.py` with SAI's official per-age/sex
   `mean` + `std` (or percentile tables) for each of the 8 tests. Keep the `{band}_{sex}` key shape.
2. **Confirm the age bands** match SAI's (currently 8–9 / 10–12 / 13–15 / 16–18 / Adult). If SAI
   publishes single-year norms, add them as more `AGE_BAND_MIDPOINTS` anchors — interpolation adapts
   automatically.
3. **Confirm test protocols & units** match SAI's exactly (e.g. sit-ups in 60 s; 4×10 m shuttle;
   50 m from standing start; 600 m vs 1.6 km run — update `endurance_run` norms & label if 1.6 km).
4. **Confirm BMI bands** against the SAI/IAP age-sex healthy ranges; adjust `optimal_low/high/std`.
5. **Update each `source` string** in `TEST_REGISTRY` to cite the official SAI document + version,
   and drop the "Prototype … validate" wording once verified.
6. **Re-tier if required.** If SAI mandates specific cut-offs (e.g. selection thresholds), adjust
   `BenchmarkingEngine.classify`.
7. **Recompute history.** After swapping numbers, run:

   ```bash
   python recompute_benchmarks.py
   ```

   This re-normalizes every stored assessment with the new norms, **re-signs** each changed record
   (so `/verify` stays authentic), and rebuilds every Performance row (incl. flexibility + body
   composition) via the API's own persistence path.
8. **Re-run the tests:** `python -m pytest tests/ -q`. The assertions in
   `tests/test_performance_index.py` encode *behaviour* (direction, interpolation, two-sided BMI,
   geometric mean) not specific magic numbers, but the smoke-test expected ranges may need nudging
   if official means differ materially.

---

## 7. Files

| Concern | File |
|---|---|
| Norm tables + registry | `app/core/config.py` |
| Normalizer (z→percentile, interpolation, BMI band, tiers) | `app/scoring_engine/benchmarker.py` |
| Composite index (domains, geometric mean) | `app/scoring_engine/performance_index.py` |
| Manual-entry endpoint | `app/api/routes.py` (`POST /assessment/manual-entry`) |
| Frontend test registry mirror | `frontend/src/utils/tests.js` |
| History recompute / re-sign / backfill | `recompute_benchmarks.py` |
| Column migration (flexibility, body composition) | `app/database/session.py` |
| Tests | `tests/test_performance_index.py`, `tests/test_manual_entry.py` |
