# Routed-clock verification model

This is an additional deterministic verification experiment for the existing
`tt_um_entropy_probe` layout. It does not modify RTL, placement or geometry, and
does not select a new fabrication revision.

## Commands and outputs

With the pinned PDK, saved routed build and `chip-ngspice:39` image available:

```sh
python3 scripts/chip.py start
python3 scripts/test-routed-spice.py
python3 scripts/verify-routed-spice.py --workers 3
python3 scripts/timing-review.py
python3 scripts/package-submission.py
python3 scripts/chip.py stop
```

The matrix writes `build/routed-spice/matrix.json`. Only
`PASS_SCOPED_PARTITION_MODEL` means the requested matrix finished. A quick run
(`--quick`) deliberately reports `INCOMPLETE_QUICK_CHECK`. Failures and ongoing
runs do not count as completed evidence. Per-experiment `.sp`, cell definitions,
raw `.dat`, `.signals.json`, `.measure.json` and `.log` files are retained under
`build/routed-spice/`. Runner logs explain failures that occur before simulation.

The saved physical build is a prerequisite; this command does not rebuild it.
On a new checkout, prepare the pinned tools/PDK, build the SPICE image using
`toolchain/spice.Dockerfile`, and run `python3 scripts/chip.py tt` first.
The complete transistor matrix is intentionally a separate command; the hosted
GDS workflow runs the cheaper schematic and static-timing checks, not this
matrix. Do not infer a transistor-matrix pass from hosted GDS CI.

## Circuit and extraction

`scripts/routed-spice.py` reads the final powered mapped netlist and the
OpenRCX SPEF files, not an ideal RTL oscillator. It resolves each cell terminal
to its extracted SPEF pin node, instantiates standard-cell transistor circuits
from the PDK, and retains each selected net's distributed resistors and
capacitances. Inserted clock buffers and renamed feedback inverters are taken
from the routed netlist.

Partition A includes all three physical rings (only the selected one runs),
their enable and selection logic, the first clock tree, the actual first divider
flip-flop and its feedback. Control-register Q boundaries are driven with the
specified configuration; this is not simulation of the control registers or
the monitor processor interface.

Five following partitions contain adjacent actual mapped divider stages
`1–2`, `3–4`, `5–6`, `7–8`, and `9`. Each uses the preceding partition's measured
settled Q waveform at its actual output-pin boundary, followed by the next
partition's extracted clock tree. Each local `/4` (or final `/2`) is checked
against actual input-edge counts. The final measured period is compared to the
original ring-clock period to check the composed `/1024` ratio. This composition
avoids simulating thousands of high-frequency ring cycles while all lower
divider stages wait for their next edge.

Waveform replay checks source PASS, matching PVT/RC, selection, adjacency and
routed inputs. It retains the measured waveform, compressed with a maximum
sample error of 0.2% of supply, and records source data/report hashes. Replayed
startup phase is arbitrary; the first settled periods are what is compared.
It does not preserve cycle-to-cycle jitter and cannot establish entropy. The
final observed node is stage-9 Q; output gating, pad loading and package waveform
quality are outside these partitions.

Out-of-cone fanout uses the maximum rise/fall pin capacitance from the
corresponding Liberty corner. Supply wires are ideal and coupling to excluded
aggressor nodes is grounded. These are explicit partition boundary assumptions;
they are not full transistor-layout extraction, power-integrity analysis,
aggressor-activity simulation, or simultaneous whole-chip transistor simulation.

## Coverage and acceptance

The matrix runs all three ring selections under:

| Process | Supply | Temperature | Wiring |
| --- | --- | --- | --- |
| TT | 1.8 V | 25 °C | nominal RC |
| FF | 1.95 V | −40 °C | minimum RC |
| SS | 1.6 V | 100 °C | maximum RC |

These are nine selected scenarios, not the full Cartesian product of process,
voltage, temperature and RC. Additional nominal control experiments use a 50 ns
supply ramp and 5 ns enable-input ramp, exercise disable/re-enable and reset
release, and change selection `0 → 1 → 2`. Disabled intervals must stop the
clock and assert divider reset; each settled enabled phase must oscillate and
divide correctly. Ordinary experiments use a 5 ns supply ramp and 0.1 ns enable
ramp. Transition glitches and initial phase are not assigned a deterministic
value. In the switching experiment, cut configuration outputs change 1 ns after
the requested selection by default. This is an explicit boundary stimulus, not
a clock-accurate configuration-register simulation.
`--configuration-latency-ns 50` selects a separately named sensitivity experiment;
it does not change the required nine-case/default-control matrix.

Each partition must show sustained operation, correct division, a clock at or
below 500 MHz, and adequate clock pulse widths. Rise/fall slew is measured using
20–80% crossings at the partition's input clock. Clock pulse widths are compared
to the worse rise/fall minimum-pulse table interpolated at the measured slew in
the corresponding `dfrtp_1` Liberty cell; an additional 0.5 ns experiment floor
is enforced. Clock-entry checks are not a transistor-level measurement of every
internal pin. Separate static timing checks all ten feedback paths and retains
the synchronizer-to-monitor paths.

Routed input netlist, GDS, SPEF, models (including device-model includes), standard
cell library, Liberty, SDC, generated deck and actual simulator image identity
are recorded. A cached result is reused only after physical inputs match and a
regenerated deck matches. Re-measurement must pass the current measurement code. Control scenarios are
always re-simulated, avoiding reuse that bypasses phase/quiet-window checks.
The original simulation generator fingerprint is retained; an old run is not
relabeled as having used newly edited generator code.

## Limits

Passing improves confidence in oscillator startup, clock selection and divider
function under the stated models. It does not guarantee manufacturing yield,
metastability failure rate, package/board behavior, power integrity or useful
entropy. Real board and PIO/DMA validation remains in `firmware/BRINGUP.md`.
If a modeled physical failure is observed, reproduce it before changing the
architecture; any actual layout change needs fresh physical signoff.

## Observed local outcome — 2026-10-21

Nine steady scenarios passed (67.678–420.654 MHz), as did nominal restart/reset.
The complete default matrix is `FAIL_OR_INCOMPLETE`: a 1 ns cut-control switching
case reproducibly settled ring95 near 585.078 MHz, with 0.276070 ns low pulses.
The exact repeat produced a byte-identical deck and waveform. A separate 50 ns
configuration-response experiment passed at the expected 261.620/195.201/146.600
MHz. This sensitivity requires clocked configuration-path follow-up; the passing
variant does not supersede the failed default experiment. See the dated design
review for report paths, pulse measurements and remaining scope.

## Clocked configuration follow-up and guarded host protocol

`python3 scripts/verify-clocked-switch.py --workers 3` generates a separate
`build/routed-spice/clocked-switch-matrix.json`. `--collect-only` requires matching
existing simulations and recomputes all current checks from their raw traces.
Only `PASS_SAFE_SWITCH_PROTOCOL` means this specific sweep completed; it does
not replace the legacy full-divider matrix or its failed cut-control experiment.

The `--control-model clocked` source partition includes the four actual mapped
configuration flip-flops, their reset/input logic and extracted host clock tree.
Configuration Q pins are observed, not forced voltage boundaries. The host clock
has a 20 ns period, with selection changes aligned 1 or 10 ns before a host
rising edge in the two nominal live-switch diagnostics. Both settled source
selection bits must match 0, 1 and 2 in their measured phases. The monitor and
other out-of-cone logic remain excluded with Liberty input-capacitance loads.
This remains a scoped transistor/RC experiment, not whole-chip simulation.

The supported host protocol uses `switch-safe`: disable before changing the
request, keep the old request stable for two host periods, capture the new
configuration on the host clock, and re-enable two periods after capture.
Separate checks require the divider clock to stop and its reset to remain
asserted inside each disabled interval. Settled measurement windows exclude
those intentional stopped intervals. The sweep requires TT/nom, FF/min and
SS/max safe cases; live-switch results are retained as diagnostics.

`EntropyProbe.configure()` now enforces this separation automatically, using
three manual cycles before changing an enabled request and three cycles after
applying it, then restoring the prior enabled state. A failure during those
disabled stages does not restore enable. This intentionally aborts any partial
acquisition window. Direct callers must follow the same disabled protocol;
arbitrary enabled source changes are not a qualified operating mode.

The nominal clocked tests passed both live alignments and the guarded sequence;
the slow-corner guarded test also passed. These results do not reproduce the
585 MHz phase from the ideal 1 ns configuration-Q stimulus. They establish a
more realistic model and a conservative supported operating sequence, while
leaving delivered-silicon validation, other alignments/PVT points and entropy
quality open. Final sweep status and measurements are in the separate report.

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
