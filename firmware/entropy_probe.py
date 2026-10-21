"""MicroPython bring-up helper for the Tiny Tapeout DemoBoard SDK.

Single-stepping is for interface bring-up, not fixed-rate entropy assessment.
Use an external clock and synchronous logic-analyzer/PIO capture for that.
"""
class EntropyProbe:
    def __init__(self, board):
        self.board = board
        self.control = 0
        board.clock_project_stop()
        if hasattr(board, 'manual_project_clock'):
            board.manual_project_clock.monitoring = False
        board.pins.project_clk_driven_by_RP2(True)
        board.clk(0)  # clock_project_once toggles twice; establish rising-first.
        board.uio_oe_pico.value = 0  # MCU never drives the chip's output pins.
        board.ui_in.value = 0

    def _write(self, address=0):
        self.board.ui_in.value = self.control | address

    def reset(self):
        self.control = 0
        self._write()
        self.board.reset_project(True)
        self.board.clock_project_once()
        self.board.reset_project(False)

    def configure(self, source=0, test_mode=0, external_bit=0):
        if source not in range(4) or test_mode not in range(4) or external_bit not in (0, 1):
            raise ValueError('Source/test mode must be 0..3, external bit 0 or 1')
        # Configuration changes must not restart a ring through a brief
        # comparator/decoder transition while acquisition is enabled. Keep the
        # old request stable for three manual cycles after disabling, then
        # clock the new request for three cycles before restoring enable.
        was_enabled = bool(self.control & 8)
        if was_enabled:
            self.control &= ~8
            self._write()
            for _ in range(3):
                self.board.clock_project_once()
        self.control = (self.control & 63) | (source << 6)
        # Only bits 4..6 are MCU outputs. Never contend with sample/valid/report.
        self.board.uio_oe_pico.value = 0x70
        self.board.uio_out.value = (test_mode << 4) | (external_bit << 6)
        self._write()
        for _ in range(3):
            self.board.clock_project_once()
        # Deliberately do not restore enable in a finally block: a failed
        # configuration operation must leave acquisition disabled.
        if was_enabled:
            self.control |= 8
            self._write()
            self.board.clock_project_once()

    def enable(self, enabled=True):
        self.control = (self.control | 8) if enabled else (self.control & ~8)
        self._write()
        self.board.clock_project_once()

    def read(self, address):
        if not 0 <= address <= 7:
            raise ValueError('Register address must be 0..7')
        self._write(address)
        return int(self.board.uo_out.value)

    def report(self):
        self.control |= 16
        self._write()
        self.board.clock_project_once()  # Apply freeze at a clock edge.
        try:
            status = self.read(0)
            if not status & 2:
                return None
            version = self.read(7)
            high = self.read(3)
            report = {'generation': self.read(1),
                    'ones': self.read(2) | ((high & 1) << 8),
                    'transitions': self.read(4) | (self.read(5) << 8),
                    'constant_window': bool(status & 16)}
            if version >= 2:
                report['source'] = (high >> 3) & 3
                report['test_mode'] = (high >> 1) & 3
            return report
        finally:
            self.control &= ~16
            self._write()

    def capture_stepwise(self, count):
        if not isinstance(count, int) or not 0 <= count <= 4096:
            raise ValueError('Sample count must be an integer in 0..4096')
        if not self.control & 8:
            raise RuntimeError('Enable acquisition first')
        samples = bytearray()
        cycles = 0
        while len(samples) < count:
            # Read before the edge: this is exactly the sample counted by ASIC.
            pins = int(self.board.uio_in.value)
            if pins & 2:
                samples.append(pins & 1)
            self.board.clock_project_once()
            cycles += 1
            if cycles > count + 4:
                raise RuntimeError('Sample-valid never asserted; check project selection and reset')
        return samples
