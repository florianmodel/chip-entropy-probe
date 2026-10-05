"""Verify the synthesized and routed entropy-probe experiment with OpenROAD."""
import hashlib
import json
import os
from pathlib import Path
import re
import odb

root = Path('/work')
tt = os.environ.get('CHIP_INSPECT') == 'tt'
run = root / ('build/tinytapeout/src/runs/verified' if tt else 'build/entropy-probe/runs/verified')
design = 'tt_um_entropy_probe' if tt else 'entropy_probe'
prefix = 'probe.' if tt else ''
raw_net = 'probe.monitor.raw_in' if tt else 'raw_out'
m = json.loads((run / f'06-yosys-synthesis/{design}.nl.v.json').read_text())['modules'][design]
db = odb.dbDatabase.create()
odb.read_db(db, str(run / f'final/odb/{design}.odb'))
block = db.getChip().getBlock()
scale = block.getDbUnitsPerMicron()
expected = {
    'osc.ro_gate': ('nand2_1', {'A': 'osc.ro4', 'B': 'osc.enable', 'Y': 'osc.ro0'}),
    **{f'osc.ro_inv{i}': ('inv_1', {'A': f'osc.ro{i-1}', 'Y': f'osc.ro{i}'}) for i in range(1, 5)},
    'osc.ro_output': ('buf_1', {'A': 'osc.ro4', 'X': 'raw_out'}),
}
if tt:
    expected = {prefix + name: (kind, {p: prefix + net if net.startswith('osc.') else raw_net for p, net in ports.items()})
                for name, (kind, ports) in expected.items()}
positions = {}
for name, (kind, ports) in expected.items():
    c = m['cells'][name]
    inst = block.findInst(name)
    assert c['type'] == inst.getMaster().getName() == 'sky130_fd_sc_hd__' + kind, name
    for port, net in ports.items():
        assert c['connections'][port] == m['netnames'][net]['bits'], (name, port)
        assert inst.findITerm(port).getNet().getName() == net, (name, port, net)
    for port, net in {'VPWR': 'VPWR', 'VPB': 'VPWR', 'VGND': 'VGND', 'VNB': 'VGND'}.items():
        assert inst.findITerm(port).getNet().getName() == net, (name, port)
    assert inst.isPlaced(), name
    b = inst.getBBox()
    positions[name] = [b.xMin()/scale, b.yMin()/scale, b.xMax()/scale, b.yMax()/scale]

# Identify the actual mapped flops by their preserved output nets.
flops = []
for signal in (prefix + 'monitor.sync_meta', prefix + 'monitor.sync_sample'):
    bits = m['netnames'][signal]['bits']
    drivers = [(n, c) for n, c in m['cells'].items() if c['connections'].get('Q') == bits]
    assert len(drivers) == 1 and '__dfxtp_' in drivers[0][1]['type'], signal
    flops.append(drivers[0])
assert flops[0][1]['connections']['D'] == m['netnames'][raw_net]['bits']
assert flops[1][1]['connections']['D'] == m['netnames'][prefix + 'monitor.sync_meta']['bits']
physical = []
for signal in (prefix + 'monitor.sync_meta', prefix + 'monitor.sync_sample'):
    net = block.findNet(signal)
    drivers = [t for t in net.getITerms() if t.getIoType() == 'OUTPUT']
    assert len(drivers) == 1 and '__dfxtp_' in drivers[0].getInst().getMaster().getName(), signal
    physical.append(drivers[0].getInst())
meta_net = block.findNet(prefix + 'monitor.sync_meta')
loads = [t for t in meta_net.getITerms() if t.getIoType() == 'INPUT']
assert len(loads) == 1 and loads[0].getInst().getName() == physical[1].getName() and loads[0].getMTerm().getName() == 'D', 'First-stage fanout must be only second-stage D'
assert physical[0].findITerm('D').getNet().getName() == raw_net, 'No mux before physical first stage'
for inst in physical:
    assert inst.isPlaced()
    b = inst.getBBox()
    positions[inst.getName()] = [b.xMin()/scale, b.yMin()/scale, b.xMax()/scale, b.yMax()/scale]

metrics = json.loads((run / 'final/metrics.json').read_text())
required = ['design__lint_error__count', 'design__inferred_latch__count',
            'design__instance_unmapped__count', 'synthesis__check_error__count',
            'design__disconnected_pin__count', 'design__max_slew_violation__count',
            'design__max_cap_violation__count', 'design__max_fanout_violation__count',
            'route__drc_errors', 'route__antenna_violation__count',
            'magic__drc_error__count', 'klayout__drc_error__count',
            'magic__illegal_overlap__count', 'design__lvs_error__count']
for k in required:
    if tt and k == 'design__disconnected_pin__count':
        assert metrics[k] == 10 and metrics['design__critical_disconnected_pin__count'] == 0
        unused_inputs = {t.getName() for t in block.getBTerms()
                         if t.getIoType() == 'INPUT' and t.getNet() and not t.getNet().getITerms()}
        assert unused_inputs == {'ui_in[6]', 'ui_in[7]'} | {f'uio_in[{i}]' for i in range(8)}
        continue
    assert metrics.get(k) == 0, (k, metrics.get(k))
for prefix in ('timing__setup__ws', 'timing__hold__ws'):
    assert prefix in metrics
    for k, v in metrics.items():
        if k == prefix or k.startswith(prefix + '__corner:'):
            assert isinstance(v, (int, float)) and v >= 0, (k, v)
lint = (run / '01-verilator-lint/verilator-lint.log').read_text()
warnings = re.findall(r'%Warning-([^:]+):[^\n]+', lint)
assert len(warnings) == 24 and set(warnings) == {'PINMISSING'}, warnings
assert all(p in {'VPWR', 'VGND', 'VPB', 'VNB'} for p in re.findall(r"missing pin: '([^']+)'", lint))
for name in ('test.log', 'gates.log'):
    assert 'PASS:' in (root / 'build/probe-rtl' / name).read_text()
assert 'Flow complete.' in (run / 'flow.log').read_text()
gds = run / f'final/gds/{design}.gds'
assert gds.stat().st_size > 0
report = {
    'status': 'PASS', 'design': design,
    'feedback_preserved': True, 'direct_two_flop_chain_preserved': True,
    'first_stage_fanout': 1, 'positions_um': positions,
    'clock_period_ns': 20, 'setup_slack_ns': metrics['timing__setup__ws'],
    'hold_slack_ns': metrics['timing__hold__ws'],
    'zero_error_checks': {k: metrics[k] for k in required if not (tt and k == 'design__disconnected_pin__count')},
    'gds_sha256': hashlib.sha256(gds.read_bytes()).hexdigest(),
    'reviewed_lint': '24 logical supply/body pin omissions; physical oscillator supply/body connections verified.',
    'limits': ['Monitor gate simulation is functional, without SDF, and separate from the complete physical netlist.',
              'No entropy, oscillator frequency or metastability failure-rate claim.',
              'Local macro validation; not a fabricated chip or submitted order.']
}
if tt:
    assert 'PASS:' in (root / 'build/tt-rtl/test.log').read_text()
    report['tile_um'] = [161, 111.52]
    report['reviewed_unused_inputs'] = sorted(unused_inputs)
(root / ('build/tt-verification.json' if tt else 'build/probe-verification.json')).write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
