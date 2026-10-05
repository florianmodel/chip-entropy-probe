"""Check chronological PIO word unpacking and validity; hardware remains untested."""
import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('capture',Path(__file__).resolve().parents[1]/'firmware/fixed_capture.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class Test(unittest.TestCase):
 def test_order_and_warmup(self):
  bits=[i%3==0 for i in range(64)];words=[]
  for offset in range(0,64,16):
   word=0
   for i in range(offset,offset+16):word=(word<<2)|(int(bits[i])|(2 if i>=2 else 0))
   words.append(word)
  self.assertEqual(module.unpack_samples(words),bytearray(bits[16:]))
 def test_routed_chip_to_capture_decoder(self):
  path=Path(__file__).resolve().parents[1]/'build/tt-rtl/physical-capture.txt'
  self.assertTrue(path.exists(), 'Run the full physical-netlist simulation first')
  pairs=[int(v) for v in path.read_text().splitlines()]
  self.assertEqual(len(pairs),4112)
  words=[]
  for offset in range(0,len(pairs),16):
   word=0
   for pair in pairs[offset:offset+16]:word=(word<<2)|pair
   words.append(word)
  samples=module.unpack_samples(words)
  self.assertEqual(len(samples),4096)
  self.assertEqual(sum(samples),2048)
  self.assertTrue(all(a!=b for a,b in zip(samples,samples[1:])))
 def test_invalid_interior_rejected(self):
  with self.assertRaises(RuntimeError):module.unpack_samples([0xffffffff,0xfffffffc])
unittest.main()
