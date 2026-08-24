/**
 * Canonical fitness-test metadata for the frontend — mirrors the backend
 * `settings.TEST_REGISTRY` (app/core/config.py) so the full SAI battery is
 * defined in ONE place and consumed by TestSelection, the manual-entry form,
 * the athlete profile, and the scout dashboard.
 *
 * Keep `id` values in sync with the backend test_type strings.
 *   capture: 'cv'     -> measured from a pose video by a CV analyzer
 *           'manual'  -> officiated stopwatch / tape / sit-&-reach entry
 *           'computed'-> derived from profile height/weight (BMI; no capture step)
 *   domain:  which Athletic Performance Index domain the test feeds
 *   titleKey/descKey: keys into translations[lang].tests (see utils/i18n.js)
 */

export const TESTS = [
  { id: 'sit_up',        capture: 'cv',     unit: 'reps', domain: 'strength',        titleKey: 'sitUp',        descKey: 'sitUpDesc' },
  { id: 'vertical_jump', capture: 'cv',     unit: 'cm',   domain: 'power',           titleKey: 'verticalJump', descKey: 'verticalJumpDesc' },
  { id: 'shuttle_run',   capture: 'cv',     unit: 'sec',  domain: 'agility',         titleKey: 'shuttleRun',   descKey: 'shuttleRunDesc' },
  { id: 'broad_jump',    capture: 'cv',     unit: 'cm',   domain: 'power',           titleKey: 'broadJump',    descKey: 'broadJumpDesc' },
  { id: 'sprint_50m',    capture: 'manual', unit: 'sec',  domain: 'speed',           titleKey: 'sprint50m',    descKey: 'sprint50mDesc' },
  { id: 'endurance_run', capture: 'manual', unit: 'sec',  domain: 'endurance',       titleKey: 'enduranceRun', descKey: 'enduranceRunDesc' },
  { id: 'sit_and_reach', capture: 'manual', unit: 'cm',   domain: 'flexibility',     titleKey: 'sitAndReach',  descKey: 'sitAndReachDesc' },
];

// bmi is computed from the profile, not a selectable test — kept here only so
// formatTestName() can label historical/derived rows.
const COMPUTED_TESTS = {
  bmi: { id: 'bmi', capture: 'computed', unit: 'kg/m²', domain: 'body_composition', titleKey: 'bmi' },
};

export const TEST_BY_ID = {
  ...Object.fromEntries(TESTS.map((x) => [x.id, x])),
  ...COMPUTED_TESTS,
};

export const isManualTest = (id) => TEST_BY_ID[id]?.capture === 'manual';
export const isCvTest = (id) => TEST_BY_ID[id]?.capture === 'cv';
export const testUnit = (id) => TEST_BY_ID[id]?.unit || '';

/**
 * Client-side plausibility bounds — mirror the backend TEST_REGISTRY
 * plausible_min/plausible_max so obvious typos are caught before the request.
 * The server re-validates these (this is a UX nicety, not the security boundary).
 */
export const MANUAL_BOUNDS = {
  sprint_50m:    { min: 5,   max: 25 },
  endurance_run: { min: 90,  max: 600 },
  sit_and_reach: { min: -30, max: 50 },
  broad_jump:    { min: 30,  max: 350 },
};

/** Human-readable test name for any id, using the active translations object. */
export function formatTestName(id, t) {
  const meta = TEST_BY_ID[id];
  if (meta && t?.tests?.[meta.titleKey]) return t.tests[meta.titleKey];
  return id;
}
