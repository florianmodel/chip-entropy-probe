#!/usr/bin/env python3
"""Focused checks for routed extraction, waveform replay and misdivision."""
import importlib.util
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

spec=importlib.util.spec_from_file_location('routed',Path(__file__).with_name('routed-spice.py'))
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class RoutedSpiceTests(unittest.TestCase):
    def test_spef_units_and_pin_identity(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.spef'
            p.write_text('''*C_UNIT 1 PF
*R_UNIT 1 OHM
*NAME_MAP
*1 probe\\.ring\\[0\\]
*2 gate
*D_NET *1 0.01
*CONN
*I *2:Y O
*CAP
1 *2:Y 0.01
*RES
1 *2:Y *1:1 12.5
*END
''')
            n=r.parse_spef(p)['probe.ring[0]']
            self.assertEqual(n['connections'],[('gate:Y','O')])
            self.assertAlmostEqual(n['caps'][0][2],1e-14)
            self.assertEqual(n['resistors'][0][2],12.5)

    def test_wave_compression_error_bound(self):
        points=[(0.,0.),(.1,.002),(.2,.001),(.3,1.),(.4,1.),(.5,1.)]
        compressed=r.compress_wave(points,.005)
        self.assertLess(len(compressed),len(points))
        for t,v in points:
            for (a,x),(b,y) in zip(compressed,compressed[1:]):
                if a<=t<=b:
                    self.assertLessEqual(abs(v-(x+(y-x)*(t-a)/(b-a))),.005+1e-12)
                    break

    def test_clocked_cone_includes_configuration_register_and_clock(self):
        cs={'gate':{'kind':'sky130_fd_sc_hd__and2_1','pins':{'A':'cfg','B':'enable','X':'out'}},
            'config_ff':{'kind':'sky130_fd_sc_hd__dfxtp_2','pins':{'D':'request','CLK':'clk','Q':'cfg'}}}
        selected,bounds,_=r.cone(cs,['gate'])
        self.assertEqual(set(bounds),{'cfg','enable'})
        selected,bounds,_=r.cone(cs,['gate'],clocked_controls={'config_ff'})
        self.assertIn('config_ff',selected)
        self.assertEqual(set(bounds),{'request','clk','enable'})

    def test_clocked_configuration_must_actually_change(self):
        trace=self.trace()
        trace['config0']=[0.]*len(trace['time'])
        trace['config1']=[0.]*len(trace['time'])
        args=SimpleNamespace(voltage=1.8,stage_count=2,scenario='switch',control_model='clocked',selection=0,corner='tt')
        with patch.object(r,'liberty_pulse_floor',return_value=.25):
            result=r.analyze(trace,args,{'partition':'source'})
        self.assertEqual(result['status'],'FAIL')
        self.assertTrue(any('configuration bit' in failure for failure in result['failures']))

    def test_guarded_protocol_rejects_clock_and_reset_active_during_disable(self):
        times=[i*.1e-9 for i in range(15001)]
        def clock(t,period):return 1.8 if t%period>=period/2 else 0.
        trace={'time':times,'clock':[clock(t,4e-9) for t in times],
               'q0':[clock(t,8e-9) for t in times],
               'reset':[1.8]*len(times),
               'config0':[1.8 if 450e-9<=t<910e-9 else 0. for t in times],
               'config1':[1.8 if t>=910e-9 else 0. for t in times]}
        args=SimpleNamespace(voltage=1.8,stage_count=2,scenario='switch-safe',control_model='clocked',
                             selection=0,corner='tt',duration_ns=1500,host_period_ns=20,request_lead_ns=2)
        with patch.object(r,'liberty_pulse_floor',return_value=.25):
            result=r.analyze(trace,args,{'partition':'source'})
        self.assertEqual(result['status'],'FAIL')
        self.assertTrue(all(phase['status']=='PASS' for phase in result['phase_measurements']))
        self.assertEqual(result['failures'].count('safe switching did not stop divider clock during disabled interval'),2)
        self.assertEqual(result['failures'].count('safe switching did not hold divider reset during disabled interval'),2)

    def trace(self,divide=4):
        times=[i*.1e-9 for i in range(2401)]
        def clock(t,period):return 1.8 if t%period>=period/2 else 0.
        return {'time':times,'clock':[clock(t,4e-9) for t in times],
                'q0':[clock(t,8e-9) for t in times],
                'out':[clock(t,divide*4e-9) for t in times]}

    def test_two_stage_division(self):
        result=r.measure(self.trace(),1.8,'divider',2)
        self.assertEqual(result['status'],'PASS',result)
        self.assertTrue(all(n==4 for n in result['clock_edges_per_output_period']))

    def test_misdivision_rejected(self):
        self.assertEqual(r.measure(self.trace(3),1.8,'divider',2)['status'],'FAIL')

    def test_stuck_clock_rejected(self):
        t=self.trace();t['clock']=[0.]*len(t['time'])
        self.assertEqual(r.measure(t,1.8,'source')['status'],'FAIL')

    def test_over_limit_clock_rejected(self):
        t=self.trace()
        t['time']=[v/4 for v in t['time']]
        result=r.measure(t,1.8,'source')
        self.assertEqual(result['status'],'FAIL')
        self.assertIn('clock exceeds 500 MHz timing envelope',result['failures'])

if __name__=='__main__':unittest.main()
