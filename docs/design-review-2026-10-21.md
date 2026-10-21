# Chip reliability review and implementation handoff

Reviewed: 2026-10-21. Repository: `/Users/flo/Documents/ChatGPT/chip`.

## Purpose and conclusion

The user's main concern is that the fabricated chip might not work. This review
looked for functional failures, physical-verification gaps, misleading evidence,
and board bring-up problems. Three cheaper `gpt-6-luna` agents independently
reviewed RTL, firmware, and submission/signoff; the primary agent inspected the
physical/analog evidence and ran additional checks.

**No confirmed silicon-killing defect was found.** Current evidence supports an
experimental measurement chip. The highest-value remaining pre-fabrication work
is simulation of the integrated oscillator-to-divider path with extracted wiring.
This is a verification gap, not a demonstrated hardware failure. Do not redesign
the architecture merely because the gap exists.

The design is not a validated cryptographic random-number generator. Functional
operation and entropy quality are separate acceptance criteria. Do not describe
simulation, balanced bit counts, or passing layout checks as proof of entropy.

This handoff records findings and recommended actions. No RTL, firmware, design
constraints, or submission files were changed during the review. Supplemental
timing scripts/logs were created under ignored `build/review-20261021/`; tests
also refreshed generated build outputs. The toolchain VM was stopped afterward.

## Scope and source map

- Canonical internal RTL: `examples/resilient-probe/*.v`.
- Canonical wrapper and constraints: `tinytapeout/src/tt_um_entropy_probe.v` and
  `tinytapeout/src/constraints.sdc`.
- Generated submission RTL: `src/*.v`. These matched the canonical design during
  review, allowing for the intentional wrapper module rename.
- Internal top: `tt_um_entropy_probe`.
- Submitted top: `tt_um_florianmodel_entropy_probe`.
- Interface version: **2**.
- Physical build: `build/tinytapeout/src/runs/verified/`.
- Physical checker: `scripts/inspect-tt.py`.
- Analog experiments: `scripts/spice.py` and `submission/evidence/spice*.json`.
- Packaging: `scripts/package-submission.py`; CI: `.github/workflows/gds.yaml`.
- Board helpers: `firmware/entropy_probe.py`, `firmware/fixed_capture.py`.

The reviewed HEAD was `a6cddc5e7aa0c83178442b29bcf88d9cb78ac768`.
The historically recorded fabrication candidate was
`aaa7e7e813dd9bc09d255d821831e47f86648dd8`; do not silently replace it with HEAD
or a new revision without identifying the exact newly validated candidate.
At review time all 14 source hashes and nine artifact hashes in
`submission/manifest.json` matched their files. The internal GDS hash was
`90a2db31e5de3ac458acb6232422c9ca1698dba48ec9802672c890a0eb59f8da`.
The renamed submission GDS has a different file hash; geometry-equivalence
evidence, not binary identity, connects those layouts.

## Recommended work order

Do the inexpensive documentation and evidence-pipeline repairs first. Then work
on integrated physical simulation. Keep hardware-dependent validation clearly
open until a compatible board and chip are available. The IDs below indicate
work items, not proven silicon-defect severity.

### R1 — Validate the integrated oscillator-to-divider path

**Classification:** highest-priority pre-fabrication verification gap.

Evidence:

- `scripts/spice.py`, especially `case()` and circuit construction, simulates a
  NAND/inverter ring and output buffer. Wiring is approximated by per-stage
  capacitors. The output load is another capacitor.
- Although the script extracts the `dfrtp_1` cell definition, its generated
  circuit does not instantiate the actual divider or selection logic.
- `scripts/verify-physical.sh` uses functional cell models without SDF.
  `tinytapeout/test/physical_tb.v` exercises deterministic test modes, not
  transistor-level physical oscillation through the complete circuit.
- `tinytapeout/src/constraints.sdc` assumes a 2 ns internal clock period
  (500 MHz). Static timing does not prove that a real oscillator starts or that
  its waveform satisfies that assumption.

Recommended implementation:

1. Build a reproducible transistor-level test of the routed ring, selection and
   enable logic, and divider path. Use extracted resistance/capacitance for the
   relevant nets and the actual mapped cells, including inserted buffers.
2. If simulation cost requires a partitioned approach, document the partition
   and preserve realistic loading and interface waveforms. Do not relabel a
   lumped-capacitance schematic as extracted simulation.
3. Exercise all three ring selections, enable/disable/re-enable, reset release,
   and source changes. Sweep process, voltage and temperature, with particular
   attention to fastest operation and slow startup. Include relevant supply
   and enable ramp variations rather than only the existing single ramp.
4. Measure steady-state frequency, clock high/low widths, edge slew, and divider
   ratio. Observe enough settled cycles to verify /1024 at the output; a short
   trace that only establishes ring oscillation does not verify the divider.
5. Keep startup phase unspecified as the current design documents. Irregular
   initial pulses alone are not a failure; failure to settle or sustained
   misdivision is.

Acceptance:

- A tracked command regenerates the circuit, runs the simulation, and produces
  machine-readable measurements tied to the exact design/model inputs.
- It fails on absent sustained oscillation, incorrect settled division,
  inadequate clock pulses, or frequencies outside the timing envelope.
- Results distinguish modeled guarantees from untested silicon behavior.
- If a failure is found, reproduce it before changing RTL or placement. Any
  physical change requires rebuilding the layout and rerunning relevant signoff.

### R2 — Prevent stale analog/timing reports from appearing current

**Classification:** confirmed evidence-pipeline defect; not proof the current
layout is faulty.

Evidence:

- `scripts/package-submission.py:27-28` copies optional timing/SPICE reports only
  if their `build/` files exist. Otherwise older files already in
  `submission/evidence/` remain.
- `.github/workflows/gds.yaml` does not run `scripts/spice.py`. A fresh checkout
  contains committed evidence that can survive packaging of a new build.
- Manifest hashes authenticate file contents but do not prove a report was
  generated for the current layout, circuit, or model revision.
- No tracked generator was found for `build/timing-review-verification.json` or
  for the appended `digital_checks`, `analog_model_checks`, and
  `timing_endpoint_review` summaries in the committed physical report.
  `scripts/inspect-tt.py` generates the core physical report, not those extras.
- `scripts/spice.py` currently checks for at least three rising crossings after
  50 ns. It does not enforce the 500 MHz ceiling. Its normal entry point also
  does not regenerate the nine unloaded cases.

Recommended implementation and acceptance:

- Give required reports reproducible tracked generators, including unloaded
  fast-corner measurements and the frequency-limit assertion.
- Bind evidence to the inputs relevant to that analysis: circuit/source or GDS,
  extraction, constraints, PDK/model content, tool version, and test parameters.
- Reject missing or mismatched required evidence instead of silently retaining
  it. If an analysis is intentionally optional, mark it absent/unverified.
- Reuse expensive results only when their complete input fingerprints match.
  The present SPICE cache's deck comparison alone is not a model-content check.
- Add focused negative tests: missing report, changed input, over-limit
  frequency, and obsolete committed report. These must not yield a misleading
  fully validated package.
- Do not erase immutable iteration archives to solve stale packaging.

### R3 — Correct the documented board bring-up example

**Classification:** confirmed documentation defect; cheap fix.

In `README.md:337-340`, the example selects `tt_um_entropy_probe` and asserts
`p.read(7) == 1`. The submitted project name is
`tt_um_florianmodel_entropy_probe`, and current RTL returns **2**.

Acceptance:

- The example uses the submitted name and expects version 2.
- Retain the explanation that the SDK entry exists only after fabrication and
  inclusion in the shuttle index; do not claim a currently available board entry.
- Check other current instructions for those same mistakes. Preserve clearly
  labeled historical version-1 descriptions rather than blindly replacing them.

### R4 — Validate acquisition on a real board when available

**Classification:** hardware-dependent gap, already disclosed in the project.

The firmware tests use a simplified host fake. Capture tests validate packed-bit
decoding and routed-netlist sample pairs, not execution of PIO assembly or DMA
on the actual SDK/MCU. No concrete firmware defect was found by inspection.

Before physical oscillator characterization:

1. Validate manual low-rate version/register reads and zero, one, alternating,
   and external-input modes.
2. Test finite PIO/DMA capture against the deterministic modes, checking sample
   order, sample/valid alignment, requested versus actual rate, missing or extra
   samples, and FIFO-related clock stretching.
3. Exercise timeout/abort and cleanup, then verify ordinary manual clocking
   still works. Check SDK/MCU compatibility and pin ownership.
4. Measure the divided output separately for each oscillator after settling.

Acceptance: retained hardware observations with board, SDK and firmware versions.
Do not change `hardware_validated: False` in `firmware/fixed_capture.py` merely
because host tests pass. Until hardware exists, keep this item open and provide
a runnable bring-up procedure.

## Additional cleanup identified during review

These are lower priority than R1/R2 and are not demonstrated current chip failures.

- **Invalid timing-exception startpoints:** current SDC uses `-from` on the
  combinational `ro_output/X` pins. Fresh OpenSTA reports “not a valid start
  point” for all three. Investigate a precise exception through the source path
  or to the intended asynchronous sampler endpoint. Do not blanket-false-path
  the monitor or divider. Acceptance: no invalid-object warnings, intended
  asynchronous crossing excluded, synchronous sampler-to-monitor and divider
  feedback paths still timed, and independently checked timing results.
- **Misleading generic check command:** `scripts/chip.py check` calls
  `scripts/check-results.py`, which checks the historical counter design.
  Label that scope explicitly or provide an unambiguous current-chip check.
  This is not a failure of the current CI sequence, which uses the TT checker.
- **Disconnected-pin guard:** `scripts/inspect-tt.py` checks critical
  disconnections and the exact unused external input set, but does not assert
  the total disconnected-pin metric. Current total is five, all expected.
  Tighten the check so an extra noncritical internal disconnection cannot pass
  unnoticed; verify the actual disconnected-pin report before defining the rule.

## Verification performed in this review

Freshly executed and passing:

- Wrapper/configuration/test-mode/pin tests and isolated /1024 divider test:
  `python3 scripts/chip.py tool bash /work/scripts/verify-tt.sh`.
- Monitor RTL lint, simulation, synthesis, and mapped-cell simulation:
  `python3 scripts/chip.py tool bash /work/scripts/verify-resilient.sh`.
- Complete routed functional netlist deterministic tests:
  `python3 scripts/chip.py tool bash /work/scripts/verify-physical.sh`.
- Six host adapter tests: `python3 scripts/test-firmware.py`.
- Three capture-decoder tests: `python3 scripts/test-capture.py`.
- Routed connectivity, preserved structures, supplies, and saved physical
  metric inspection:
  `python3 scripts/chip.py tool openroad -exit -python /work/scripts/inspect-tt.py`.
- Supplemental extracted-netlist static timing across the nine configured
  process/RC corners, reproducing minimum setup slack **0.495743 ns**.
  Clock pulse-width checks passed, with minimum reported margin **0.488380 ns**.
  Those pulse results assume the SDC's 500 MHz, 50% duty-cycle clock; they do not
  measure a physical oscillator waveform. Scripts/logs are in
  `build/review-20261021/` and are not committed.

Inspected existing evidence; not regenerated in this review:

- Zero reported Magic/KLayout DRC, LVS, routing, antenna and electrical-limit
  violations. Minimum saved hold slack **0.204241 ns**.
- Archived hosted official precheck:
  `build/hosted-ci/precheck/results.xml`, 15 cases, zero failures or errors.
- 81 loaded schematic SPICE cases: **26.978–167.130 MHz**.
- Nine unloaded fast cases: maximum **390.874 MHz**, below the 500 MHz timing
  assumption. No new transistor-level corner sweep was run during this review.
- Submission manifest hashes and saved geometry-equivalence evidence.

There was no full new place-and-route/DRC/LVS run and no silicon test. Existing
physical results were inspected against the saved layout; do not represent this
review as fresh fabrication signoff.

## Guidance for the next agent

- Read this file, current `CONTEXT.md`, and relevant source before acting.
  Some older context sections describe superseded design iterations.
- Prefer the existing pinned container/PDK and scripts. Start with
  `python3 scripts/chip.py start`; stop the VM after work if you started it.
- Edit canonical design sources, not only the generated copies under `src/`.
- Preserve `build/iterations/*` archives. Do not fabricate, order, publish, or
  select a new fabrication revision as part of these repairs without the user's
  corresponding instruction.
- Keep verified defects, verification gaps, and speculative risks separate.
  Avoid speculative RTL changes to address an unobserved physical failure.
- R3 and the check-command clarification are suitable small tasks for a cheaper
  agent. R2 is bounded tooling work. R1 requires careful circuit/extraction work;
  an agent should report concrete limitations rather than claim equivalence to
  an extracted simulation it has not performed.
- Finish each implemented item with its changed files, executed checks, result,
  and remaining limitations. Update this handoff's status only with evidence.

For later entropy validation, reference
[NIST SP 800-90B](https://csrc.nist.gov/pubs/sp/800/90/b/final). The current design's
ones/transition counts and constant-window flag are diagnostics, not a complete
entropy assessment or health-test system.

## Implementation follow-up — 2026-10-21

The review above is preserved as the original handoff. The local implementation
adds the following repairs; it does not select a new fabrication revision.

- **R2 implemented:** `scripts/spice.py` regenerates all 81 loaded and nine
  unloaded experiments, enforces the 500 MHz ceiling, and binds cache reuse to
  deck, model/device-model, cell-library and actual simulator-image inputs.
  A fresh sweep passed: loaded 26.978–167.130 MHz; unloaded maximum
  390.874 MHz. `scripts/package_evidence.py` validates exact corner sets,
  finite frequencies, source fingerprints and tool identity. Packaging removes
  stale managed optional reports, labels absent evidence, and drops the older
  manually appended physical annotations. Immutable iteration archives remain
  untouched. Negative tests exercise missing/stale inputs, duplicate/missing
  corners, changed tools, excessive frequency and negative timing slack.
- **R3 implemented:** README points to the submitted name and interface v2,
  with the fabrication/shuttle-index prerequisite. Full runnable examples are
  in `firmware/BRINGUP.md`; historical v1 descriptions remain labeled.
- **R4 procedure supplied; hardware validation still open:** the new bring-up
  guide covers manual modes, report reads, finite PIO/DMA capture, analyzer
  rate/phase checks, timeout/abort and cleanup. Six firmware and three decoder
  host tests pass. No physical board test occurred; `hardware_validated: False`
  is unchanged.
- **SDC repair implemented:** the asynchronous exception targets only the D
  pin of the first sampler, discovered through the preserved `sync_meta` net.
  `scripts/timing-review.py` runs all nine Liberty/SPEF combinations, requires
  setup/hold, parsed min-period and pulse-width diagnostics, and checks every
  divider feedback path plus both synchronizer-to-monitor path groups. The
  fresh run passed without invalid-object errors: minimum setup 0.495743 ns,
  hold 0.204241 ns. Each corner contains 154 pulse checks. These remain timing
  results under the declared clocks, not oscillator waveform measurements.
- **Other cleanup implemented:** `chip.py check` help/README explicitly says
  historical counter only. `inspect-tt.py` now requires exactly five total
  disconnections and the precise expected unused-input set; the updated checker
  passed on the saved ODB, with negative tests for extra/missing disconnections.
- **R1 model implemented:** see `docs/routed-verification.md` and
  `scripts/verify-routed-spice.py`. The model uses routed signal RC and actual
  mapped cells, adjacent divider partitions, measured waveform-train replay,
  and explicit boundary assumptions. The authoritative completion status and
  coverage are in `build/routed-spice/matrix.json`; a partial/quick matrix is
  not a completed verification. Full-layout transistor extraction, supply-noise
  interaction and real silicon remain outside this model's scope.

The hosted workflow now builds its SPICE image and runs the schematic sweep,
fresh timing generator, and evidence negative tests. This changed workflow has
not been dispatched to GitHub in this follow-up. Saved GDS geometry is unchanged;
there has been no new place-and-route/DRC/LVS run, fabrication order or publication.
The exporter preserves an already geometry-equivalent GDS byte-for-byte so
evidence-only packaging does not churn GDS timestamps. Final local source and
artifact hashes are recorded when `package-submission.py` is run.

### Routed matrix outcome and newly observed switch-model failure

The full attempted matrix did **not** pass: `build/routed-spice/matrix.json`
records `FAIL_OR_INCOMPLETE`. All nine steady scenarios and their six adjacent
partitions passed. Source-clock frequencies span 67.678–420.654 MHz; composed
divider-Q ratios span 1023.783–1024.736 (within 0.08% of /1024). Every local
divider partition requires exact input-edge counts over multiple output periods.
The nominal slow-ramp disable/re-enable/reset experiment passed its three phases
and inactive intervals.

The default source-switch experiment found a sustained adverse middle phase:
ring95 measured 585.078 MHz, with 0.548070 ns high and 0.276070 ns low pulses.
This exceeds the 500 MHz envelope, fails the 0.5 ns experiment low-pulse floor,
and is slightly below the slew-interpolated Liberty requirement (0.277290 ns).
The separately started nominal ring95 case was 195.196 MHz. The approximately
threefold frequency is consistent with a higher oscillation mode, but its
physical cause has not been established. It must not be dismissed as one
initial glitch or turned into a claim of a confirmed silicon defect.

The switch stimulus changes requested pins, then drives the cut configuration-Q
outputs 1 ns later. Actual configuration registers update on `clk`; the cut
experiment is not a cycle-accurate model of that update. Original failed
outputs and matrix are preserved under
`build/routed-spice/reproductions/first-switch-failure/`. The report/trace stem is
`source-nom-tt-0-1.8-25-50-switch-en5`. R1 remains open for this modeled transition
until a clocked control-register experiment distinguishes boundary sensitivity
from a realizable circuit failure. No architecture or physical design was
changed in response.

Cached control scenarios are now always re-simulated so a prior PASS cannot
bypass newer phase/quiet-window checks. Packaging independently checks the
Liberty requirement for every control phase. The failed full matrix cannot
produce a packaged routed PASS; its absence/unverified reason is explicit in
`submission/evidence/status.json`. The terminal divider observation is stage-9 Q,
not the pad/output-gating waveform.

Reproduction and sensitivity result: an exact second run reproduced the failed
1 ns case with byte-identical deck **and waveform**. A separately named
`--configuration-latency-ns 50` experiment passed all three phases at
261.620/195.201/146.600 MHz; middle-phase high/low pulses were
2.703046/2.414555 ns. Its stem is
`source-nom-tt-0-1.8-25-50-switch-en5-cfg50`. This establishes sensitivity to the
modeled control timing; it does not validate every realizable request/clock
alignment or remove the failed default case. Further work should include the
actual clocked configuration path and its timing before prescribing a physical
fix. For board bring-up, disable acquisition, apply configuration, then re-enable
as separate steps and verify behavior on delivered silicon.

Final local packaging verified all 23 recorded source hashes and all ten
artifact hashes. Submission GDS remains byte-identical to the pre-change tracked
file; the internal GDS hash remains `90a2db31e5de3ac458acb6232422c9ca1698dba48ec9802672c890a0eb59f8da`.

## Clocked configuration implementation follow-up

The later user request authorized implementation of the next investigation.
`scripts/routed-spice.py --control-model clocked` now includes the four actual
mapped configuration registers and routed clock tree, rather than forcing their
Q states to follow requests after an artificial delay. Two nominal live-switch
alignments (1 ns and 10 ns before the host clock edge) and a guarded nominal
sequence passed; no 585 MHz phase appeared in those clocked cases. The SS/max
guarded sequence passed at 121.116/90.298/67.739 MHz. These observations narrow
the earlier adverse result to its boundary stimulus; they do not establish that
all realizable live transitions are safe. The original failed traces and full
matrix remain preserved.

The firmware helper now disables acquisition before an enabled configure call,
clocks the old request for three cycles, applies/clocks the new request for three
cycles, then restores enable. Failed configuration clocks leave acquisition
disabled. This conservative operating protocol avoids depending on a short
configuration-mismatch interval. Eight host firmware tests pass, including
ordering of old/new requests, enable restoration and failure behavior.

`scripts/verify-clocked-switch.py` separately verifies the guarded protocol at
TT/nom, FF/min and SS/max, retaining two nominal live diagnostics. It regenerates
and compares decks before reusing simulations and recomputes the full current
phase/configuration/pulse/quiet/reset checks from raw traces. Original simulator
provenance is retained alongside the current analyzer hash. Its safe-protocol
acceptance does not promote the failed legacy matrix to a full routed PASS.
No RTL/layout change is justified by the clocked results observed so far.

### Final clocked-protocol result

The separate five-case report completed `PASS_SAFE_SWITCH_PROTOCOL`. All three
guarded cases passed actual configuration-state, sustained oscillation, /2,
pulse/slew and inactive clock/reset checks. Both nominal live-switch diagnostics
also passed; those two alignments do not qualify arbitrary live switching.

| Model / RC | Ring71 MHz | Ring95 MHz | Ring127 MHz |
| --- | ---: | ---: | ---: |
| TT / nom | 260.391 | 194.496 | 146.106 |
| FF / min | 420.180 | 316.843 | 238.878 |
| SS / max | 121.116 | 90.298 | 67.739 |

The highest observed source clock was 420.180 MHz, below the 500 MHz timing
envelope. The minimum measured safe-phase high/low widths were respectively
1.151716/0.982671 ns. The current analyzer independently rechecked retained
waveforms; original simulation-generator fingerprints remain unchanged in their
source reports. Host-adapter tests and firmware/test hashes are recorded.

No silicon RTL or layout edit was needed on this evidence. The implemented
change is a guarded firmware operating protocol plus a clocked verification
model, regression tests, documentation and freshness-checked evidence packaging.
The legacy ideal-Q matrix remains failed and preserved. Delivered-board checks,
entropy characterization and a fresh hosted workflow remain outstanding.

Final packaging included the validated clocked-protocol report as
`submission/evidence/clocked-switch.json`, while the legacy routed evidence
remains explicitly absent/unverified. All 28 source and 11 artifact hashes
matched, and the submission GDS remains byte-identical to its pre-change tracked
file. Final local regression checks passed: 9 routed-model tests, 18 evidence
tests, 8 firmware tests, 3 capture-decoder tests, 4 timing-parser tests and the
disconnected-pin negative checks. No hosted workflow, board test, fabrication
order or new fabrication revision selection occurred.

## Hosted release retry — 2026-10-21

The first fresh hosted GDS run for commit `6a74e807c13fa4ea85b88d382285ff5457b4939e`
passed the 90-case schematic sweep and physical signoff/ODB inspection, then
failed in snapshot creation: the snapshot reader still accessed the obsolete
loaded-SPICE `cases` key. `snapshot-iteration.py` now reads `loaded_cases`, keeps
unloaded reports separate, skips invalid/missing ring coverage, and hashes copied
reports. Three regression tests cover the current schema and negative inputs.
Cheap regression checks now run before the hosted expensive simulations.
This fixes archive/tooling behavior; it does not change RTL or layout. A fresh
passing revision is still required before submission.
