import sys
from pathlib import Path

K3 = Path(__file__).resolve().parent.parent / "iscandar"
sys.path.insert(0, str(K3))


import bitstruct


from MPUPointer import MOTOROLA, INTEL


class CPUPointer: 
    _FORMATS = { MOTOROLA: 
                 bitstruct.CompiledFormat('u1u1p17u30u15'),  # V, R, pad, start, stored
   
                 INTEL:    
                 bitstruct.CompiledFormat('u15u30p17u1u1'),  # stored, start, pad, R, V
               }
