"""Host tests for the SDK adapter; no attached board or entropy simulation."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('entropy_probe', Path(__file__).resolve().parents[1] / 'firmware/entropy_probe.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class Port:
    def __init__(self, value=0): self.value = value

class Board:
    def __init__(self):
        self.ui_in = Port(); self.uio_in = Port(); self.uio_out = Port(); self.uio_oe_pico = Port(255)
        self.pins = self
        self.ticks = 0; self.in_reset = False; self.valid = True; self.fail_read = False
        self.clock_owned = False; self.level = 1; self.frozen_edges = 0; self.history = []
        self.registers = [18, 7, 0, 1, 0, 0, 0, 1]
    def clock_project_stop(self): pass
    def project_clk_driven_by_RP2(self, value): self.clock_owned = value
    def clk(self, value): self.level = value
    def reset_project(self, value): self.in_reset = value
    def clock_project_once(self):
        self.history.append((self.ui_in.value, self.uio_out.value))
        assert self.clock_owned and self.level == 0
        if self.in_reset or not self.ui_in.value & 8: self.ticks = 0
        else: self.ticks += 1
        self.uio_in.value = ((self.ticks & 1) | 2) if self.valid and self.ticks >= 2 else 0
        if self.ui_in.value & 16: self.frozen_edges += 1
    @property
    def uo_out(self):
        if self.fail_read: raise RuntimeError('Disconnected board')
        return Port(self.registers[self.ui_in.value & 7])

class Tests(unittest.TestCase):
    def setUp(self): self.board = Board(); self.probe = module.EntropyProbe(self.board)
    def test_reset_capture_alignment_and_direction(self):
        self.assertEqual(self.board.uio_oe_pico.value, 0)
        self.assertEqual(self.board.level, 0)
        self.probe.reset(); self.probe.enable()
        self.assertEqual(self.probe.capture_stepwise(6), bytearray([0, 1, 0, 1, 0, 1]))
    def test_report_freeze_and_nine_bit_decode(self):
        self.probe.enable()
        self.assertEqual(self.probe.report(), {'generation': 7, 'ones': 256, 'transitions': 0, 'constant_window': True})
        self.assertEqual(self.board.frozen_edges, 1)
        self.assertFalse(self.board.ui_in.value & 16)
        self.assertTrue(self.board.ui_in.value & 8)
        self.board.registers = [2, 8, 128, 0, 255, 0, 0, 1]
        self.assertEqual(self.probe.report(), {'generation': 8, 'ones': 128, 'transitions': 255, 'constant_window': False})
    def test_new_metadata_and_safe_test_inputs(self):
        self.probe.configure(3, 1, 1)
        self.assertEqual(self.board.uio_oe_pico.value, 0x70)
        self.assertEqual(self.board.uio_out.value, 0x50)
        self.assertEqual(self.board.ui_in.value >> 6, 3)
        self.board.registers = [18, 7, 0, 27, 0, 0, 0, 2]
        report = self.probe.report()
        self.assertEqual((report['ones'],report['source'],report['test_mode']), (256,3,1))
        with self.assertRaises(ValueError): self.probe.configure(4)
    def test_configure_disables_before_request_and_restores_after_settling(self):
        self.probe.enable()
        self.board.history.clear()
        self.probe.configure(source=1, test_mode=2)
        self.assertEqual(len(self.board.history),7)
        self.assertTrue(all(not control & 8 and control >> 6 == 0 and uio == 0
                            for control,uio in self.board.history[:3]))
        self.assertTrue(all(not control & 8 and control >> 6 == 1 and uio == 0x20
                            for control,uio in self.board.history[3:6]))
        self.assertTrue(self.board.history[6][0] & 8)
        self.assertTrue(self.probe.control & 8)

    def test_failed_configuration_does_not_restore_acquisition(self):
        self.probe.enable()
        original=self.board.clock_project_once
        calls=[]
        def fail_on_new_configuration():
            calls.append(1)
            if len(calls)==4:
                raise RuntimeError('configuration clock failed')
            original()
        self.board.clock_project_once=fail_on_new_configuration
        with self.assertRaises(RuntimeError):
            self.probe.configure(source=1)
        self.assertFalse(self.probe.control & 8)
        self.assertFalse(self.board.ui_in.value & 8)

    def test_failure_releases_freeze(self):
        self.board.fail_read = True
        with self.assertRaises(RuntimeError): self.probe.report()
        self.assertFalse(self.board.ui_in.value & 16)
    def test_capture_is_bounded_and_requires_enable(self):
        with self.assertRaises(RuntimeError): self.probe.capture_stepwise(1)
        self.probe.enable(); self.board.valid = False
        with self.assertRaises(RuntimeError): self.probe.capture_stepwise(2)
        self.assertLess(self.board.ticks, 10)
        for count in (-1, 4097, 1.5):
            with self.assertRaises(ValueError): self.probe.capture_stepwise(count)
    def test_addresses_checked(self):
        for address in (-1, 8):
            with self.assertRaises(ValueError): self.probe.read(address)

unittest.main()
