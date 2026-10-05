"""Rename only the GDS top cell and prove geometry/hierarchy are preserved."""
from pathlib import Path
import hashlib,json
import klayout.db as k
root=Path('/work');old='tt_um_entropy_probe';new='tt_um_florianmodel_entropy_probe'
final=root/'build/tinytapeout/src/runs/verified/final';out=root/'submission'
layout=k.Layout();layout.read(str(final/f'gds/{old}.gds'))
assert [c.name for c in layout.top_cells()]==[old]
def signature(db):
 rows=[]
 for cell in db.each_cell():
  name=new if cell.name==old else cell.name
  for layer in db.layer_indices():
   info=db.get_info(layer)
   for shape in cell.shapes(layer).each():rows.append(f'{name}|{info.to_s()}|{shape.to_s()}')
  for inst in cell.each_inst():rows.append(f'{name}|instance|{db.cell(inst.cell_index).name}|{inst.cplx_trans.to_s()}|{inst.a.to_s()}|{inst.b.to_s()}|{inst.na}|{inst.nb}')
 return hashlib.sha256('\n'.join(sorted(rows)).encode()).hexdigest()
before=signature(layout);layout.cell(old).name=new
(out/'gds').mkdir(parents=True,exist_ok=True);layout.write(str(out/f'gds/{new}.gds'))
roundtrip=k.Layout();roundtrip.read(str(out/f'gds/{new}.gds'));assert signature(roundtrip)==before
(out/'evidence').mkdir(parents=True,exist_ok=True)
(out/'evidence/geometry.json').write_text(json.dumps({'status':'PASS','old_top':old,'new_top':new,'geometry_hierarchy_sha256':before,'top_only_rename':True,'cell_count':layout.cells()},indent=2)+'\n')
print('PASS: submission top renamed; complete geometry and hierarchy unchanged')
