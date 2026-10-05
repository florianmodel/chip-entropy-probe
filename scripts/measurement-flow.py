"""Pinned Classic flow with one explicit oscillator placement step."""
from librelane.flows import Flow
from librelane.flows.classic import Classic
from librelane.steps.odb import OdbpyStep
from librelane.steps import Step
@Step.factory.register()
class CompactRings(OdbpyStep):
 id='Chip.CompactRings';name='Compact Oscillator Placement'
 def get_script_path(self):return '/work/scripts/compact-rings.py'
@Flow.factory.register()
class MeasurementFlow(Classic):
 Steps=Classic.Steps.copy()
 Steps.insert(next(i for i,s in enumerate(Steps) if s.id=='OpenROAD.GlobalPlacement'),CompactRings)
if __name__=='__main__':
 import sys
 from librelane.__main__ import cli
 cli(['--flow','MeasurementFlow',*sys.argv[1:]])
