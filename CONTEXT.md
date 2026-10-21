# Project context

## User intent

- Create a real fabricated chip for learning, with a total budget below €500.
- Use open source design software that the assistant can operate.
- Proceed step by step: establish and verify the toolchain before designing the
  first chip.
- Investigate cryptography and secure communication in a hypothetical
  post-apocalyptic setting where computational cryptography is broken.

## Interpretation and recommendation — 2026-10-04

The phrase "P PN is solved" is interpreted as **P = NP with a practical solver
capable of defeating computational cryptography**. Merely resolving P versus NP
does not imply that outcome, and a polynomial algorithm need not be practical.

The recommended first custom chip remains an experimental physical entropy
source / TRNG. It supplies a necessary ingredient for one-time pads, but is not
a complete secure communication device. Pad transport, authentication, storage,
one-time consumption and endpoint security remain separate requirements.

For this threat model, extraction should have an information-theoretic basis.
A future seeded universal-hash extractor requires an independent uniform seed
and a justified entropy bound; a cryptographic hash or PRNG cannot simply be
assumed to supply either. Architecture and entropy guarantees remain unverified.

## Implemented software

- Project command: `python3 scripts/chip.py`.
- Pinned versions and image digest: `toolchain.lock.json`.
- Open runtime: Colima/Lima, named VM `chip`, Docker context `colima-chip`.
- Target PDK: SKY130, revision pinned to the LibreLane 3.0.14 metadata.
- Counter example verifies the software flow, not a TRNG or full shuttle design.

See README.md and build outputs for commands and verification evidence. Keep
plans separate from measured behavior. Reconfirm the shuttle-required tool/PDK
versions and complete price before any fabrication submission.

Verified on 2026-10-04: counter RTL and final gate-level functional simulation
passed; the complete physical flow produced GDS with zero Magic/KLayout DRC,
Netgen LVS, routing and antenna errors. At a 20 ns clock period, worst setup slack
was 13.129 ns and worst hold slack was 0.112 ns across the configured corners.
Evidence: `build/verification.json` and `build/counter/runs/verified/final/metrics.json`.

## Cryptography findings

- With a practical P = NP solver, conventional one-way-function-based security
  is unsuitable. This is a stronger assumption than quantum attacks alone.
- A uniform secret one-time pad of message length, used once and independent of
  the message, provides perfect confidentiality regardless of computation.
- Information-theoretic message authentication is possible with universal-hash
  constructions and appropriately managed secret randomness.
- An entropy source does not solve secret key distribution. Independently
  generated random pads on two devices will not match.
- A small ASIC tile does not provide bulk pad storage, tamper resistance or
  persistent pad-consumption state by default.

Sources:

- [One-way functions and randomness extraction, Daniel Wichs course notes](https://www.khoury.northeastern.edu/home/wichs/class/crypto-fall15/lecture4.pdf)
- [One-time pads, Princeton](https://introcs.cs.princeton.edu/java/99crypto/)
- [Information-theoretic Wegman–Carter authentication](https://eprint.iacr.org/2013/126)

## Planned next milestone

Completed on 2026-10-04: standalone gated NAND + four-inverter ring, plus output
buffer. Complete physical flow passed with zero Magic/KLayout DRC, Netgen LVS,
routing and antenna errors. Exact signal connectivity was checked in synthesized
JSON and final OpenROAD database; all six functional cells and their supply/body
connections survived. KLayout renders and cell positions are in `build/`.
Evidence: `build/oscillator-verification.json`. Reviewed 24 missing supply-pin
RTL lint warnings; supply/body pins are explicitly checked in final database.
The NAND feedback timing arc is disabled only in STA, not in physical wiring.
No claimed frequency, jitter or entropy validation. Macro is 100 × 100 µm.

Completed on 2026-10-05: `entropy_probe` combines the ring with a directly
connected two-flop sampler, raw/sample/validity outputs, and nonoverlapping
256-sample windows counting ones and internal transitions. An eight-address
readout exposes frozen report counts, generation, status and live progress.
Freeze preserves reports while acquisition continues; disable discards partial
windows and retains completed reports. This is a measurement experiment, not an
entropy estimator or complete health-test implementation.

RTL and separately SKY130-mapped monitor simulations passed deterministic stream,
boundary, freeze, disable, reset and generation-wrap tests. Complete physical
flow passed with zero DRC/LVS/routing/antenna/electrical-limit errors, and setup
slack 11.907 ns / hold slack 0.202 ns at a 20 ns clock period across configured
corners. Ring connectivity, direct sampler chain and first-stage fanout of one
were checked in the final database. Evidence: `build/probe-verification.json`.
Current macro: 120 × 120 µm; GDS and KLayout views in `build/`. These dimensions
and pins are not a selected shuttle footprint. Asynchronous source timing is
excluded; no oscillator frequency, entropy or metastability MTBF claim.

Completed on 2026-10-05: Tiny Tapeout wrapper `tt_um_entropy_probe`, 1x1 SKY130
fixed footprint 161 × 111.52 µm. Pinned template/support/SDK/action commits in
`tinytapeout.lock.json`. `prepare-tt.py` stages canonical sources and mirrors the
official config merge. Wrapper pin/selection/reset/freeze tests and exact port
signature passed; flow DRC/LVS/routing/antenna/electrical checks passed. Setup
slack 11.723 ns, hold 0.203 ns at 20 ns. Exact ring and direct sampler preserved.
Ten unused required input pins are explicitly reviewed; critical disconnections
zero. Evidence: `build/tt-verification.json` and precheck `results.xml`.
All 15 cases of the pinned unmodified local precheck passed. Geometry uses host
packages; Magic/KLayout run in container; native Yosys replaces only the upstream
WebAssembly syntax command. Hosted shuttle CI has not been run.

Pin map: UI0–2 address, UI3 enable, UI4 report freeze, UI5 raw pin opt-in; UO byte
readout; UIO0 sample, 1 valid, 2 ready, 3 optional raw; remaining pins unused.
SDK bring-up helper `firmware/entropy_probe.py` has five passing host adapter
tests, not real-board validation. Stepwise capture is irregular and unsuitable
for fixed-rate entropy assessment. README has continuous acquisition plan.
Raw ring may exceed the documented 33 MHz output rating: leave raw output off
and add a divided frequency monitor before fabrication.

Calculator observation: regular one tile + devkit + economy shipping €385;
limited individual discount €185. Final taxes/checkout unconfirmed; no order.
Candidate TTSKY26d public deadline 2026-11-30, estimated shipping 2027-06-09;
recheck volatile details before submission. Author metadata and final unique
submission name remain unset. Sources and limitations in README.

Next: divided frequency measurement, oscillator-speed analysis, continuous
capture and health tests; complete submission metadata and hosted shuttle CI.
Do not represent statistical tests or simulations as proof of security.


2026-10-05 revision work: integrated source is now `examples/resilient-probe`,
interface version 2. Three selectable 71/95/127-stage physical rings, one active;
source 3 selects zero/one/alternating/external test input. UI6..7 select source,
UIO4..5 test mode, UIO6 external test bit. Report register 3 has ones bit 8 at
bit 0 and completed configuration at bits 4:1. Mode changes invalidate samples
and abort partial windows. UIO3 is oscillator /1024, gated by UI5. There are five
intentionally unused inputs (UIO0..3 and UIO7), zero critical disconnections.

Local physical iteration 003 passes structural, timing, DRC/LVS, routing,
antenna and electrical checks; setup 0.496 ns and hold 0.204 ns. Timing assumes
20 ns external clock and at most 500 MHz internal ring clock. `compact-rings.py`
fixes rings in legal two-row serpentine groups before global placement, through
`measurement-flow.py`, a pinned Classic extension. This custom step must be
included in hosted hardening. All 15 local prechecks passed again. Full routed
functional netlist test modes and capture pairs passed (no SDF/no physical noise).
Mapped-monitor tests pass, including generation wrap. Six firmware adapter and
three capture-decoder tests pass; one feeds the decoder routed-netlist waveforms.
Finite PIO/DMA helper is written but has not run on an actual board; no validated
million-sample acquisition, noise model, online health tests or entropy guarantee.

Numbered snapshots under build/iterations preserve baseline, rejected short-ring
revision 001 (divider timing), rejected revision 002 (slew/capacitance and too-fast
unloaded oscillator), and passing compact revision 003. Real KLayout full-tile,
detail and per-ring PNGs plus Pillow architectural PNGs are generated. Keep
snapshots immutable and generate PNGs for every subsequent physical iteration.

ngspice 39.3 is installed in a project Docker image, recorded under toolchain/.
SPICE is deterministic schematic transistor startup/frequency with lumped loads,
not extracted RC/noise. Fast unloaded corners for all rings peak at 390.9 MHz,
below the timing assumption. All 81 loaded corner cases passed (27.0–167.1 MHz), plus nine unloaded fast
cases (maximum 390.9 MHz). Evidence: build/spice/results.json and
build/spice/unloaded-results.json. Three rising edges after 50 ns are required;
retained longer runs cover some slow cases. Register-only asynchronous endpoint
cleanup was rechecked on the same extracted layout in the timing-review run,
with unchanged slack and no invalid-endpoint warnings.
No fabrication order, publication, hosted shuttle CI or board validation completed.
Keep the one-tile target and €500 total budget; final checkout remains unconfirmed.

Final iteration snapshot: build/iterations/003-compact-rings contains six PNGs
(architecture, full tile, detail, three ring views), GDS/final physical outputs,
source and verification evidence. Snapshot source matches the physical design
plus reviewed SDC endpoint cleanup. After snapshot, the current chip.py tt
command was enhanced to automatically render/archive every completed physical
build and return failure when signoff metrics fail; no physical design changed.
Automatic snapshots include failed signoff status and never overwrite prior ones.
Architecture renderer now supports macOS Arial and Linux DejaVu Sans fonts.

## Hosted submission preparation — 2026-10-05

Created private repository https://github.com/florianmodel/chip-entropy-probe
under the existing signed-in GitHub account. Root Apache-2.0 license preserves
the upstream template license. Provisional author is florianmodel. Unique
submitted top is tt_um_florianmodel_entropy_probe; canonical internal build top
remains tt_um_entropy_probe. package-submission.py exports GDS/LEF/powered
netlist, root source copies/info.yaml and SHA manifests. export-layout.py proves
the top-cell rename preserves every geometry/hierarchy element.

Initial committed design revision: aaa7e7e813dd9bc09d255d821831e47f86648dd8.
Hosted GDS workflow: https://github.com/florianmodel/chip-entropy-probe/actions/runs/37302707223
Hosted docs workflow: https://github.com/florianmodel/chip-entropy-probe/actions/runs/37302707126
Docs passed; generated three-page official PDF rendered and visually inspected.
Hosted ARM64 build passed RTL/mapped/routed tests, capture tests and full physical
signoff using compact placement. Official custom-GDS packaging passed. All 15 official
hosted shuttle prechecks passed; the overall GDS workflow is successful. The official precheck uses its standard PDK
0536d02d875c8f67dd7cca3902ac457e62f20005; hardening remains pinned to 8afc8346.

Hosted layout geometry/hierarchy fingerprint equals local iteration 003:
e0dfdac4a490ba38e47af64030ee95bca129f9d5b274b43d6bd5ae67908c1561.
Cell positions, check counts and timing margins also match. Binary GDS hashes
differ; do not claim file-level identity. Archived hosted package, report and
six newly generated PNGs as build/iterations/004-hosted-rebuild. PDF is at
build/hosted-ci/docs/datasheet.pdf. Existing iteration archives remain immutable.

Current calculator observed regular SKY130 one tile + one board + economy
shipping €385; final tax/checkout total remains unverified. TTSKY26d currently
closes 2026-11-30, estimated shipping 2027-06-09. No order or Tiny Tapeout portal
submission has been performed. Human actions: author/publication decision,
Tiny Tapeout GitHub login/project creation, exact successful fabrication revision
selection, compatible board choice and final checkout under €500. Shipping
address is collected later according to Tiny Tapeout's FAQ. Hardware bring-up
and entropy characterization require delivered silicon; no board validation yet.

Checklist-only README/CONTEXT updates follow the verified source revision and
skip redundant CI. Submit revision aaa7e7e813dd9bc09d255d821831e47f86648dd8,
which has both successful workflows. No RTL, constraints or package changed.


## Review implementation — 2026-10-21

See `docs/design-review-2026-10-21.md` for the original findings and dated
implementation follow-up. Current working-tree repairs change SDC, tooling,
evidence and documentation; the historical statement above about unchanged
constraints/package applies only to the earlier checklist update. RTL and GDS
geometry are unchanged. No new fabrication revision has been selected.

Evidence packaging now removes stale managed optional reports and validates
analysis inputs/models/tools. Fresh schematic SPICE: 81 loaded plus nine
unloaded cases passed; unloaded maximum 390.874 MHz. The tracked timing
generator passed nine Liberty/SPEF combinations after the precise first-sampler
exception repair, retaining all divider feedback and downstream sampler paths:
minimum setup 0.495743 ns and hold 0.204241 ns. The disconnected-pin checker
requires exactly the five expected unused inputs. See `firmware/BRINGUP.md` for
interface-v2/submitted-top bring-up and outstanding physical PIO/DMA checks.

Routed transistor/RC partition verification is documented in
`docs/routed-verification.md`; only a complete `PASS_SCOPED_PARTITION_MODEL` in
`build/routed-spice/matrix.json` is completed coverage. It uses measured waveform
replay and explicit boundary assumptions, not whole-chip simultaneous transistor
simulation or entropy proof. The updated hosted workflow has not been dispatched.
Delivered-silicon operation and entropy quality remain unvalidated.

The attempted routed matrix ended `FAIL_OR_INCOMPLETE`: nine steady conditions
and nominal restart passed, but the default 1 ns cut-configuration switch case
produced a sustained ring95 phase near 585.078 MHz with 0.276070 ns low pulses.
See the dated review follow-up and preserved first-failure traces. This is an
adverse boundary-model result requiring clocked configuration-register follow-up,
not a confirmed silicon defect. Do not promote it to routed PASS evidence.

The failed switch experiment was reproduced with byte-identical deck/waveform.
A separate 50 ns configuration-response case passed at 261.620/195.201/146.600
MHz, establishing modeled transition-timing sensitivity. It does not supersede
the failed default case; actual clocked configuration-path validation is next.


### Clocked-control follow-up and host protocol

The user authorized investigation and necessary fixes after the switching-model
failure. `routed-spice.py --control-model clocked` now retains the four mapped
configuration registers, their input/reset logic and routed host clock tree.
Two nominal live-switch alignments (1 ns and 10 ns before the host edge) passed
without reproducing the ideal-cut 585 MHz phase. This does not qualify arbitrary
live source changes. `EntropyProbe.configure()` now pauses an enabled request,
clocks three cycles with old controls, applies/clocks new controls for three
cycles, then restores enable. Configuration-stage failures leave enable low.
Direct hosts must use the documented disabled protocol. No RTL/GDS change.

`scripts/verify-clocked-switch.py` generates a separate protocol report at
`build/routed-spice/clocked-switch-matrix.json`: three guarded PVT/RC cases and
two nominal live diagnostics. It rechecks current full raw-trace analysis while
preserving original simulation provenance. Its `PASS_SAFE_SWITCH_PROTOCOL`
status applies only to the stated control/source cone plus first divider stage,
and does not relabel the failed historical full-divider/cut-control matrix.
Packaging validates the separate report before including `clocked-switch.json`;
stale/missing results are removed and labeled absent. See the dated review and
routed-verification document for final measurements and scope. Hardware and
entropy validation remain open, as does fresh hosted CI for these changes.

Final clocked protocol report: `PASS_SAFE_SWITCH_PROTOCOL`; all three guarded
PVT/RC cases and both nominal live diagnostics passed current trace reanalysis.
Safe-source frequencies span 67.739–420.180 MHz; minimum high/low widths
1.151716/0.982671 ns. This supports the guarded firmware protocol without a
silicon redesign; it does not supersede the failed ideal-Q matrix or validate
arbitrary live switching, board operation or entropy.


## Hosted release verification request — 2026-10-21

The user authorized committing/pushing final files, running hosted GDS, Docs
and official precheck, fixing failures, and identifying the exact passing
revision. No order is authorized. The older `aaa7e7e...` fabrication candidate
is historical; the current review fixes require a fresh passing candidate.
A later documentation-only release record does not change the selected design
revision. Keep local experimental evidence distinct from freshly hosted proofs.
