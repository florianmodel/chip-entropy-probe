# Entropy-probe hardware bring-up

This is a procedure for the first compatible Tiny Tapeout board after the
`tt_um_florianmodel_entropy_probe` design is fabricated and present in that
shuttle's SDK index. It is intentionally staged: stop at the first failed check
and record the failure. Host tests and routed-netlist simulation do not validate
the board, the PIO assembly, DMA behavior, or entropy quality. The return value
from `fixed_capture.capture()` therefore continues to say
`hardware_validated: False` until a human records and reviews real hardware
observations.

## 1. Prepare the board and project

Use the devkit and SDK revision for the purchased shuttle. Copy
`firmware/entropy_probe.py` and `firmware/fixed_capture.py` to the board as
`entropy_probe.py` and `fixed_capture.py`. Connect a logic analyzer if available:

- project clock (`clk`),
- sample output (UIO0),
- sample-valid output (UIO1),
- reset, if accessible.

Check voltage and pin directions against the board and shuttle documentation.
The MCU drives only UIO4..UIO6 for test controls; UIO0..UIO3 and UIO7 remain
inputs to the MCU. Do not connect a second clock source while the MCU owns the
project clock.

Start in the board REPL. The SDK project entry below is expected only after
fabrication and shuttle-index inclusion:

```python
from ttboard.demoboard import DemoBoard
from ttboard.mode import RPMode
from entropy_probe import EntropyProbe

tt = DemoBoard.get()
tt.mode = RPMode.ASIC_RP_CONTROL
tt.shuttle.tt_um_florianmodel_entropy_probe.enable()
p = EntropyProbe(tt)
p.reset()
assert p.read(7) == 2, p.read(7)  # Interface version 2
```

If the import, project entry, or version check fails, record board model, shuttle,
SDK revision and observed error. Do not continue as if the intended chip were
selected.

## 2. Verify manual clocking, reset and deterministic sources

The test source is selected with `source=3`. `test_mode=0` is constant zero,
`1` constant one, `2` alternating, and `3` the external test bit. For each mode,
the following checks sample/valid before each generated rising edge. Two initial
pipeline samples are masked by hardware validity; the helper returns only valid
samples. Configuration changes abort an in-progress monitor window, so configure
before enabling and start a fresh capture each time.

```python
def check_mode(mode, external_bit=0):
    p.reset()
    p.configure(source=3, test_mode=mode, external_bit=external_bit)
    p.enable()
    bits = p.capture_stepwise(256)
    assert len(bits) == 256, len(bits)
    if mode == 0:
        assert set(bits) == {0}, set(bits)
    elif mode == 1:
        assert set(bits) == {1}, set(bits)
    elif mode == 2:
        assert set(bits) == {0, 1}, set(bits)
        assert sum(a != b for a, b in zip(bits, bits[1:])) >= 250
    else:
        assert set(bits) == {external_bit}, set(bits)
    print('mode', mode, 'external', external_bit, 'first 32:', list(bits[:32]))
    p.enable(False)

check_mode(0)
check_mode(1)
check_mode(2)
check_mode(3, 0)
check_mode(3, 1)
```

This validates both polarities of the external test input and the four deterministic
waveforms through the on-chip synchronizer. It is not a test of the oscillator.
If a mode fails, capture the analyzer trace and REPL output before changing setup.

Check report/register access with a completed constant-one window. The report
read itself takes an extra clock edge to freeze the report; do not mix report
reads into a stream capture.

```python
p.reset()
p.configure(source=3, test_mode=1)
p.enable()
bits = p.capture_stepwise(260)
report = p.report()
assert report is not None, report
assert report['ones'] == 256, report
assert report['source'] == 3 and report['test_mode'] == 1, report
assert p.read(7) == 2
print(report)
p.enable(False)
```

The monitor counts 256 valid samples per report window. A 260-sample capture is
used so at least one full window can complete after reset and synchronizer
warm-up. If the report is not ready, capture additional valid samples and read
again; do not infer a bad chip from a window that has not completed.

## 3. Exercise finite PIO/DMA capture and rate

Run a short deterministic capture first. This code requests 10 kHz and checks
that the returned stream has exactly the requested count and expected bit value.
Repeat for zero, alternating and external modes; test the external mode at both
levels. `fixed_capture.capture()` uses a PIO state machine to clock and sample
before each rising edge, while DMA drains the FIFO.

```python
import fixed_capture

p.reset()
p.configure(source=3, test_mode=2)
p.enable()
result = fixed_capture.capture(p, count=4096, sample_hz=10000, sm_id=0)
bits = result['samples']
assert len(bits) == 4096, len(bits)
assert set(bits) == {0, 1}, set(bits)
assert sum(a != b for a, b in zip(bits, bits[1:])) >= 4000
assert result['requested_sample_hz'] == 10000, result
assert result['hardware_validated'] is False
print({k: v for k, v in result.items() if k != 'samples'})
```

Use the analyzer to measure the actual project-clock period over the middle of
the finite burst and compare its mean frequency with `requested_sample_hz`. The
returned `elapsed_ms` is coarse wall-clock transfer duration, not an achieved
clock-rate measurement. Record requested rate, measured rate, count, analyzer
sample rate, and observed burst duration. Repeat at 1 kHz, 10 kHz, 50 kHz and
100 kHz. For each run, verify:

- exactly the expected number of clock rising edges and 4096 returned samples;
- sample and valid are stable in the pre-rising-edge phase used by the PIO;
- valid is asserted for every retained sample, with the startup prefix discarded;
- no unexplained clock pauses or stretched periods appear while DMA drains;
- requested and measured rates agree within the tolerance chosen before testing.

The PIO uses blocking autopush. If DMA falls behind, this prevents silent data
loss but can stretch the generated clock. Such a trace is an acquisition failure
for fixed-rate measurement even if the number of returned bits is correct. Save
the raw analyzer trace and REPL result; do not discard a run with missing edges.

## 4. Abort, cleanup and return to manual clocking

With a finite capture running, interrupt the REPL with Ctrl-C once. Python's
`finally` cleanup should stop the state machine and DMA, close DMA, and leave the
project clock low. Then verify the clock level on the analyzer and run a normal
manual capture:

```python
p.enable(False)
p.reset()
p.configure(source=3, test_mode=1)
p.enable()
manual = p.capture_stepwise(32)
assert len(manual) == 32 and set(manual) == {1}, manual
print(list(manual))
```

If control-C does not return to the REPL, the clock is not low, or manual capture
does not work afterward, power-cycle only according to the board instructions,
record the event, and classify cleanup as failed. Also test a normal finite
capture to completion after the abort test. Do not claim timeout/abort behavior
passed unless the analyzer and post-abort manual check support it.

## 5. Record hardware evidence before oscillator measurements

For each observation retain board and shuttle identity, SDK revision, firmware
file hashes, submitted GDS/revision, voltage, temperature, requested and measured
clock rates, capture mode/count, analyzer setup, reset history, test result, and
the raw trace. Repeat manual and PIO checks after a board restart. Resolve pin
ownership against the exact SDK/MCU version. Only after deterministic modes,
registers, finite capture, rate, alignment, no-loss behavior, and cleanup pass
should oscillator characterization begin.

The firmware metadata remains `hardware_validated: False` until a reviewed
hardware-validation record is deliberately added. Passing these steps validates
the acquisition path under the recorded conditions; it does not establish
randomness, entropy, cryptographic suitability, or manufacturing yield.

### Source changes

`EntropyProbe.configure()` now enforces a separate disable/configure/enable
sequence when acquisition is running. It clocks three cycles with the old
request disabled, clocks the new request for three cycles, then restores enable.
A failed configuration operation leaves acquisition disabled. An intentional
configuration call aborts the partial acquisition window; completed reports
retain their recorded configuration.

Ring enables are registered flip-flops gated only by `ena` and reset. A ring
starts one clock edge after its selection is captured; a selection change keeps
every ring off for at least one clock period, and test-mode pins (UIO4/UIO5)
cannot stop or restart a running ring. At the slowest simulated ring frequency
one 20 ns clock period only just exceeds the ring's half period, so the guarded
sequence's extra cycles, or the recommended 100 kHz–5 MHz clocks, keep a wide
margin.

The earlier ideal-control experiment reproducibly exceeded the timing envelope
for a 1 ns response. Nominal experiments including the actual mapped
configuration registers and routed clock tree pass for both tested live-switch
alignments. See `../docs/routed-verification.md` for the separate protocol sweep
and its limits. Use the helper's guarded sequence for characterization; do not
infer a guarantee for arbitrary direct enabled source changes.

```python
p.configure(source=1)  # pauses, applies/settles the request, restores prior enable
```

Repeat for each ring and measure the divided output only after settling. Retain
the enable/configuration timing and output waveform. Delivered-board operation
and entropy quality still require hardware validation.
