"""Run with openroad -python: verify physical feedback and export cell positions."""
import json
import re
from pathlib import Path
import odb

run = Path('/work/build/ring-oscillator/runs/verified')
expected = {
    'ro_gate': ('nand2_1', {'A': 'ro4', 'B': 'enable', 'Y': 'ro0'}),
    **{f'ro_inv{i}': ('inv_1', {'A': f'ro{i-1}', 'Y': f'ro{i}'}) for i in range(1, 5)},
    'ro_output': ('buf_1', {'A': 'ro4', 'X': 'raw_out'}),
}
module = json.loads((run / '06-yosys-synthesis/ring_oscillator.nl.v.json').read_text())['modules']['ring_oscillator']
for name, (kind, connections) in expected.items():
    cell = module['cells'][name]
    assert cell['type'] == 'sky130_fd_sc_hd__' + kind, (name, cell['type'])
    for port, net in connections.items():
        assert cell['connections'][port] == module['netnames'][net]['bits'], (name, port, net)

db = odb.dbDatabase.create()
odb.read_db(db, str(run / 'final/odb/ring_oscillator.odb'))
block = db.getChip().getBlock()
scale = block.getDbUnitsPerMicron()
cells = {}
for name, (kind, connections) in expected.items():
    inst = block.findInst(name)
    assert inst is not None and inst.getMaster().getName() == 'sky130_fd_sc_hd__' + kind, name
    actual = {p.getMTerm().getName(): p.getNet().getName() for p in inst.getITerms() if p.getNet()}
    for port, net in connections.items():
        assert actual[port] == net, (name, port, actual, net)
    for port, net in {'VPWR': 'VPWR', 'VPB': 'VPWR', 'VGND': 'VGND', 'VNB': 'VGND'}.items():
        assert actual[port] == net, (name, port, actual)
    assert inst.isPlaced(), name
    b = inst.getBBox()
    cells[name] = {'type': kind, 'connections': actual,
                   'bbox_um': [b.xMin()/scale, b.yMin()/scale, b.xMax()/scale, b.yMax()/scale]}
required = ['design__lvs_error__count', 'magic__drc_error__count', 'klayout__drc_error__count',
            'route__drc_errors', 'route__antenna_violation__count', 'design__instance_unmapped__count']
metrics = json.loads((run / 'final/metrics.json').read_text())
for key in required:
    assert key in metrics and metrics[key] == 0, (key, metrics.get(key))
assert (run / 'final/gds/ring_oscillator.gds').stat().st_size > 0
lint = (run / '01-verilator-lint/verilator-lint.log').read_text()
warnings = re.findall(r"%Warning-([^:]+):[^\n]+", lint)
assert len(warnings) == 24 and set(warnings) == {'PINMISSING'}, warnings
assert all(pin in {'VPWR', 'VGND', 'VPB', 'VNB'} for pin in re.findall(r"missing pin: '([^']+)'", lint))
report = {'feedback_preserved_in_synthesis': True, 'feedback_preserved_in_physical_database': True,
          'checks': {k: metrics[k] for k in required}, 'cells': cells,
          'reviewed_lint_warnings': '24 missing supply/body pins in logical RTL; all connected and verified in final physical database.',
          'limitations': 'No silicon measurements: oscillation, frequency and entropy are unverified.'}
Path('/work/build/oscillator-verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
