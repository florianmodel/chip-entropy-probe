"""Fixed two-row serpentine rings, respecting row orientation and fixed taps."""
import click,re
from reader import click_odb
@click.command()
@click_odb
def main(reader):
 block=reader.block;scale=block.getDbUnitsPerMicron()
 rings=sorted(int(re.search(r'ring(\d+)\.ro_gate',i.getName())[1]) for i in block.getInsts() if re.search(r'ring(\d+)\.ro_gate',i.getName()))
 rows=sorted([r for r in block.getRows() if r.getSite().getHeight()>1000],key=lambda r:r.getOrigin()[1])
 # Rows share origin and form the legal SKY130 site grid.
 unique={r.getOrigin()[1]:r for r in rows};rows=[unique[y] for y in sorted(unique)]
 occupied=[i.getBBox() for i in block.getInsts() if i.isFixed()]
 instmap={i.getName().replace('\\',''):i for i in block.getInsts()}
 def pack(insts,row,reverse=False):
  y=row.getOrigin()[1];site=row.getSite().getWidth();x=row.getOrigin()[0]+site*12
  slots=[]
  for inst in insts:
   width=inst.getMaster().getWidth();height=inst.getMaster().getHeight()
   while any(x<b.xMax() and x+width>b.xMin() and y<b.yMax() and y+height>b.yMin() for b in occupied):x+=site
   assert x+width < block.getCoreArea().xMax()
   slots.append((inst,x,y,row.getOrient()));x+=width+site
  if reverse:
   # All inverter cells in the bottom half have identical widths.
   slots=[(i,slot[1],slot[2],slot[3]) for i,slot in zip(insts,reversed(slots))]
  for inst,x,y,orient in slots:
   inst.setOrient(orient);inst.setLocation(x,y);inst.setPlacementStatus('FIRM');occupied.append(inst.getBBox())
 for index,n in enumerate(rings):
  base=f'probe.bank.ring{n}.';chain=[instmap[base+'ro_gate']]+[instmap[base+f'chain[{j}].ro_inv'] for j in range(1,n)]
  row_index=4+index*9
  pack(chain[:n//2+1],rows[row_index]);pack(chain[n//2+1:]+[instmap[base+'ro_output']],rows[row_index+1],True)
  print('Fixed compact ring',n,'at rows',row_index,row_index+1)
if __name__=='__main__':main()
