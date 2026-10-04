# Harness changes — `solidworks-0001-playstation-controller`

This document summarises what changed in `tests/task/harness/harness.py`
relative to the original, AI-generated version, and why — per the README
requirement to *"Include a short note on what you changed and why"*.

Starting point for the diagnosis: **the official reference
`solution/solution.SLDPRT` did not pass the original harness** (it failed
`clusters at mirrored positions` and `left-handed layout achieved`), despite
being defined in `task.toml` as the file that must score full marks. That
was the signal that the problem was in the harness, not the model — in line
with the README's instruction to treat the existing harness as a starting
point, not a fixed reference.

---

## 1. `dpad` ↔ `face_buttons` label swap (critical bug)

**Function:** `assign_roles()`

**Symptom:** on `solution.SLDPRT` (the official reference), `c2_spacing`
reported `dpad centre x: expected 168.5, got -7.5` and `face_buttons centre
x: expected -7.5, got 168.5` — the values exactly swapped.

**Cause:** the original heuristic labelled the two button diamonds (`dpad`
vs `face_buttons`) independently in each model, sorting by **average
small-engraved-face count** ("more faces = dpad"). That assumption isn't
stable across models — after remodelling, the `face_buttons` cluster
(4 distinct symbols: △○✕□) could end up with a higher face count than
`dpad`, flipping the sort order **only in the candidate** and silently
swapping the labels, even though the physical diamond groups themselves
were correctly identified.

**Fix:** candidate diamonds are now matched to baseline by **expected
geometric position** (the mirror+widen transform), not the unstable
face-count heuristic. The heuristic remains only as a fallback when
building the baseline itself (where there's nothing yet to compare
against).

---

## 2. Numerically unstable `housing_side_signature`

**Function:** `housing_signature()`

**Symptom:** on a model with correctly-mirrored port lights and text
(independently confirmed by `port_lights_side` and `body_chirality`),
`housing_side_signature` still returned `FAIL` — `baseline_moment3` and
`measured_moment3` had opposite signs but comparable magnitude.

**Cause:** the original formula summed a 3rd-order moment over **every**
face of the housing. Large, near-symmetric panels (present on both sides of
the plane) contribute huge, nearly-cancelling terms, and the real signal
(the handful of genuinely one-sided features) is a tiny, numerically
unstable **residual** of that cancellation. A few percent difference in how
precisely symmetric panels were reproduced during the +15mm widen could
flip the sign of that residual with no real handedness error.

**Fix:** `housing_signature()` now sums the moment only over faces
**without a mirror-symmetric counterpart** (`_unpaired_faces()`) — matched,
symmetric panels are filtered out up front, so there's nothing unstable
left to cancel.

**The baseline needs recomputing** after this change — see
`recompute_baseline.py`.

---

## 3. Demoting `housing_side_signature` to a corroborating-only signal

**Function:** `c4_handedness()`

Even after the fix in #2, this metric remains the most indirect and
sensitive of the four handedness witnesses. When the other three — more
direct and physically interpretable (`cluster_sides`, `body_chirality`,
`port_lights_side`; the latter is, per `task.toml`'s own notes, the
intended *"naive-flip guard"*) — all agree the mirror is correct, a
conflicting sign on `housing_side_signature` no longer fails the criterion
and is **excluded from the continuous score** (not just from the failure
list) — a signal demoted from failing the criterion shouldn't still be
allowed to cost it points, which would otherwise leave `score` and
`passed` disagreeing with each other.

---

## 4. Wrong body correspondence within a cluster when width is wrong

**Function:** `_match()`

**Symptom:** on an example with correctly mirrored but **unwidened**
clusters, `c2_spacing` reported chaotic diamond-rigidity values
(`intra dpad: 20.9 -> 71.9mm` instead of two repeating, consistent values).

**Cause:** `_match()` picked which specific body corresponds to which
(e.g. which physical button is which) by matching against a position that
assumes the **full +15mm width growth**. When a candidate is correctly
mirrored but not widened, that assumed target diverges from reality enough
that the permutation search sometimes picked the wrong body-to-body
pairing — mixing up which physical button is which.

**Fix:** body-to-body correspondence is now computed from each body's
position **relative to its own role-group's centroid** (mirrored about the
plane), not an absolute, width-dependent target. This decouples
correspondence correctness from width correctness — the two are graded
independently, where they should be (cluster *position* in `c2` still
intentionally depends on width, per `instruction.md`'s *"re-space the
button clusters to match the wider stance"*).

---

## 5. Continuous [0,1] scoring instead of PASS/FAIL (README requirement)

**Functions:** `c1_width`, `c2_spacing`, `c3_interference`,
`c4_handedness`, `PS3Harness.checks()`

Each scored criterion now returns a `"score"` in `[0,1]`
(`score_error(error, TOL[...], ZERO_AT[...])` — full credit up to the
tolerance threshold, linear falloff to zero at the newly added `ZERO_AT`
thresholds), instead of a plain `PASS`/`FAIL`. `c1`/`c2` use the
**worst-case** result among all checked pairs/roles (not an average), so
one bad pair can't hide behind good ones. `c4_handedness` combines its four
witnesses into a weighted average (`cluster_sides` 0.40, `body_chirality`
0.30, `port_lights_side` 0.25, `housing_side_signature` 0.05, excluded
entirely when demoted — see #3), skipping any that came back
`UNVERIFIABLE` for that candidate.

`no unrequested changes` remains a hard gate (`MUST_PASS`), score-neutral
by the `harness_base.finalize()` contract.

Empirically validated against the full `examples/` set: partially-correct
candidates (e.g. `adversarial_only_one_button_cluster_mirrored` — only one
of two clusters moved) now receive meaningful intermediate scores (~0.68),
not just 0 or 1.

---

## 6. Rebuild health as its own criterion, not a measurement-blocking switch

**Function:** `Grader.grade()`

**Symptom:** `adversarial_unwidened_shell_with_correct_clusters` (which,
per `task.toml`, should only fail on width) scored `FAIL(0.00)` on **all
five** criteria at once.

**Cause:** the original `grade()` skipped computing `c1`–`c4` entirely
whenever the model's rebuild had errors, substituting hard zeroes
everywhere — losing the granularity the README asks for (*"loses points on
the component(s) it actually gets wrong, and only those"*). SolidWorks
generates body geometry **independently** of whether the rebuild has
errors, so measurement was possible; the harness just wasn't bothering.

**Fix:** `"rebuild health"` is now its own, sixth criterion — a `MUST_PASS`
gate (score-neutral, like `no unrequested changes`), not a switch. `c1`–`c4`
are always computed, from real geometry. The overall result is still `FAIL`
when the rebuild is broken (the gate), but the individual criterion scores
are now visible for diagnosis.

`max_score` in `task.toml` was unaffected by this change (the new gate is
score-neutral).

---

## 7. `score`/`passed` consistency

**Function:** `c4_handedness()`

When `housing_side_signature` is demoted to a corroborating-only signal
(#3), it's now also excluded from the weighted average, not just from the
failure list — so "doesn't count as a failure" and "doesn't cost points"
mean the same thing. Previously the demotion only affected status, so
`score` could come out `0.95` while status was `PASS`, disagreeing with
`harness_base.finalize()`'s `passed = all(subscores >= 1.0)`.

---

## 8. Results saved to file

**Functions:** `grade_candidate()`, new `_save_result()`

Every harness run now writes the full report (every criterion's
status/score/checks, not just the final envelope) to
`tests/task/results/<candidate_filename>_<timestamp>.json`. Previously the
result only existed in the console and disappeared when the terminal
closed.

---

## 9. Cluster position decoupled from the fixed width target

**Function:** new `_measured_half_m()`, used by `c2_spacing`

**Symptom:** `adversarial_widened_by_30mm` lost points on `clusters at
mirrored positions` (0.31) in addition to `widened by 15mm` (0.00), even
though `task.toml` describes it as a width-only defect ("widened 30 mm
instead of 15").

**Cause:** `c2_spacing`'s expected cluster-centre position was computed
using a **fixed** 15mm target (`POLICY["half_m"]`), baked into
`mirror_widen_x()`. A candidate that correctly re-spaced its clusters to
match its **own** (wrong) width got penalised a second time for the same
single error — once on `c1_width` for the wrong width, and again on
`c2_spacing` for not matching a width it was never asked to match in the
first place.

**Fix:** `_measured_half_m()` derives the actual achieved half-width
growth from the same sticks/triggers/bumpers pairs `c1_width` already
measures, and `c2_spacing` grades cluster position against that measured
value, not the fixed target. Width correctness stays solely `c1_width`'s
job. Per `instruction.md`: *"re-space the button clusters to match the
wider stance"* — their own stance, not a hardcoded number.

Confirmed: `clusters at mirrored positions` now scores a clean `1.00` on
`adversarial_widened_by_30mm`, with no regression elsewhere.

---

## 10. New criterion: glyph presence

**Function:** new `c6_glyphs()`

**Symptom:** `adversarial_missing_glyphs` (and several other adversarial
examples that, on visual inspection, genuinely lack button-glyph detail)
scored full marks, because `symbol_glyphs` in `c4_handedness` was
permanently hardcoded to `UNVERIFIABLE` (PS symbol faces are left-right
symmetric, so a mirror can't be read from them geometrically — but that
says nothing about whether they're *present*).

**Approach:** counts small engraved faces (`small_face_counts`, already
computed by `capture()`) on the `dpad`/`face_buttons` bodies, baseline vs
candidate, penalising only **decreases** — remodelling can legitimately add
small faces (fillets, split surfaces) without removing any glyphs, so
increases are never penalised.

Two earlier, whole-housing-based candidate signals (total housing volume,
largest-body volume) were tried first and rejected: both known-good
references differ from baseline by a far larger margin on those signals
than the actual defect does, because they model the housing shell
differently — the real signal was swamped by legitimate style variance.
Targeting the much smaller, less-remodelled button bodies instead avoids
that noise floor: the two known-good references differ from baseline by
only 0 and +18 small button faces, while genuinely defective examples drop
by -24 or more — a clean, well-separated signal, confirmed against the full
`examples/` set (visually verified file-by-file).

**This adds a fifth scored criterion.** `max_score` in `task.toml` was
updated from `4` to `5` accordingly, per the README's explicit allowance to
edit/add scoring components as long as `max_score` matches their sum.

---

## Known, unresolved limitations

- **`c5_unrequested` cannot detect changes placed on the housing.** The
  existing check explicitly exempts the housing from its shape-drift
  detection, because the housing is expected to be extensively remodelled
  by the legitimate widen+mirror edit. `adversarial_unrequested_change_
  elsewhere`'s defect (an added recess) is placed exactly there, so it's
  invisible to the check by design. Four independent whole-part aggregate
  signals were tried as replacements and all failed for the same reason:
  total housing volume, largest-body volume, small-face count on the
  housing, and whole-part centre of mass. Measured values:

  | File | Volume (mm³) | Centre-of-mass shift vs baseline (mm) |
  |---|---|---|
  | baseline (`input.SLDPRT`) | 1,580,472 | – |
  | `solution.SLDPRT` (reference) | 309,446 | dX +2.06, dY +4.33, dZ −6.41 |
  | `solutionTG.SLDPRT` (correct) | 1,628,279 | dX −0.07, dY +0.23, dZ −0.60 |
  | `adversarial_unrequested_change_elsewhere` | 309,543 | dX +2.01, dY +4.35, dZ −6.41 |

  Root cause (confirmed by inspecting the files): the reference solution
  and the examples derived from it have a **hollowed (shelled) housing**,
  while the baseline and `solutionTG` have a **solid** one — about 80% of
  the volume differs between two equally correct constructions. Any
  aggregate signal is dominated by that difference. The actual defect (a
  small recess) is on the order of 100 mm³, roughly 0.006% of the baseline
  volume, and `adversarial_unrequested_change_elsewhere` is nearly
  indistinguishable from `solution.SLDPRT` on every aggregate measure, so it
  could only be told apart by fitting to that one reference file, which
  would violate the requirement that a different correct solution still
  scores full marks.

  Grading the outer shape only (treating every candidate as solid) would be
  the right principle, but no reliable way to fill a hollow body through
  the SolidWorks COM API was found. A geometrically precise fix (boolean
  symmetric-difference between the candidate's housing and an expected
  baseline-derived shape, built by translating the baseline's two grip
  halves apart by the measured half-width) also required a body-transform
  call (`IMathUtility.CreateTransform` / `IBody2.ApplyTransform`, and
  `FeatureManager.InsertMoveCopyBody2`) that failed across six attempted
  call signatures (`DISP_E_MEMBERNOTFOUND` / `DISP_E_TYPEMISMATCH`),
  without access to the SDK documentation to resolve the expected
  signature. Documented here rather than shipped as an unreliable proxy.

- **`c4_handedness` does not literally evaluate text orientation.**
  `instruction.md` requires that labels (START/SELECT) **move** to their
  new position but remain legible (not mirrored backwards as literal text).
  The current witnesses (`cluster_sides`, `body_chirality`,
  `port_lights_side`) don't inspect the text itself — a model with
  incorrectly mirrored text does lose some score on handedness
  (`adversarial_text_mirrored_incorrectly` scores 0.74, not 1.0), but this
  is likely a side effect of other geometry changes that accompany a bad
  mirror, not a direct, targeted check on legibility.

---

## Validation

Final regression over the official reference, two independent solutions and
all eight adversarial examples (`run_examples.py`). Score is the sum of the
five scored criteria; a failed gate (rebuild health, no unrequested changes)
zeroes the total.

| File | Rebuild (gate) | Widened | Clusters | Interference | Handedness | Glyphs | Unrequested (gate) | Score / 5 |
|---|---|---|---|---|---|---|---|---|
| `solution.SLDPRT` (reference, shelled housing) | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | pass | **5.00** |
| `solutionTG.SLDPRT` (independent, shelled housing) | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | pass | **5.00** |
| `solutionTG_old.SLDPRT` (independent, solid housing) | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | pass | **5.00** |
| `adversarial_feature_tree_with_errors` | 0.00 | 0.00 | 0.00 | 0.00 | 0.68 | 0.00 | pass | 0.00 (gate) |
| `adversarial_missing_glyphs` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | pass | 4.00 |
| `adversarial_only_one_button_cluster_mirrored` | 1.00 | 1.00 | 0.00 | 1.00 | 0.68 | 0.00 | pass | 2.68 |
| `adversarial_text_mirrored_incorrectly` | 1.00 | 1.00 | 1.00 | 1.00 | 0.74 | 0.00 | pass | 3.74 |
| `adversarial_unrequested_change_elsewhere` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | pass | 4.00 |
| `adversarial_unwidened_shell_with_correct_clusters` | 0.00 | 0.01 | 0.00 | 0.00 | 0.84 | 0.00 | pass | 0.00 (gate) |
| `adversarial_widened_15mm_clusters_at_original_spacing` | 1.00 | 0.00 | 0.00 | 0.00 | 0.70 | 1.00 | pass | 1.70 |
| `adversarial_widened_by_30mm` | 1.00 | 0.00 | 1.00 | 1.00 | 1.00 | 0.00 | pass | 3.00 |

Notes:

- The three correct solutions use different constructions (the reference and
  `solutionTG` have a hollowed housing, `solutionTG_old` and the input part
  have a solid one) and all score full marks, so the grading does not depend
  on how the housing was built.
- `adversarial_unrequested_change_elsewhere` scores 4/5 only because of the
  glyph-presence criterion. Its own defect (the added recess) is still not
  detected; see the first limitation above.
- `adversarial_feature_tree_with_errors` and
  `adversarial_unwidened_shell_with_correct_clusters` are zeroed by the
  rebuild-health gate. The per-criterion scores are still computed and shown
  for diagnosis.
