import sys
from pathlib import Path

K3 = Path(__file__).resolve().parent.parent / "iscandar"
sys.path.insert(0, str(K3))


import bitstruct

from collections import namedtuple

from MPUPointer     import MOTOROLA, INTEL
from BeamCoordinate import BeamCoordinate
from Bijection      import Bijection
from Cube           import Cube


Fields = namedtuple('Fields', ['virtual', 'reserved', 'start', 'count'])


class CPUPointer:
    'k=4 pointer, extending theorem from k=3 to k=4'

    _FORMATS = { MOTOROLA:
                 bitstruct.CompiledFormat('u1u1p17u30u15'),  # V, R, pad, start, stored

                 INTEL:
                 bitstruct.CompiledFormat('u15u30p17u1u1'),  # stored, start, pad, R, V
               }

    MAX_WORD  = (1 << 64) - 1
    MAX_START = (1 << 30) - 1           # cube start over local start
    MAX_COUNT = Cube.SECTORS_PER_CUBE   # 32768, the whole cube

    def __init__                (self, coordinate, count,
                                 reserved=0, order=MOTOROLA):

        'creation: a BeamCoordinate and a count go in, the word is born'

        virtual = 1     # born virtual, as at k=3: creation raises it

        if reserved not in (0, 1):
            raise ValueError(f"reserved must be 0 or 1, not {reserved!r}")
        if not 1 <= count <= self.MAX_COUNT:
            raise ValueError(f"count must be 1..{self.MAX_COUNT}, "
                             f"not {count!r}")

        local = coordinate.k3 ()
        start = (coordinate.cube * Cube.SECTORS_PER_CUBE
                 + local.displacement)
        if not 0 <= start <= self.MAX_START:
            raise ValueError(f"start must be 0..{self.MAX_START}, "
                             f"not {start!r}")

        stored = count - 1
        if order == INTEL:
            data = self._FORMATS[INTEL].pack(stored, start,
                                             reserved, virtual)
        elif order == MOTOROLA:
            data = self._FORMATS[MOTOROLA].pack(virtual, reserved,
                                                start, stored)
        else:
            raise ValueError(f"unknown order: {order!r}")
        self.word = int.from_bytes(data, 'big')


    @classmethod
    def adopt                   (cls, word):

        'adoption: an existing word enters as it is, flag as it lies'

        if not 0 <= word <= cls.MAX_WORD:
            raise ValueError(f"not a 64-bit word: {word!r}")
        born = cls.__new__(cls)
        born.word = word
        return born


    def unload                  (self, order=MOTOROLA):

        'the word fields, with the count back in true form'

        data = self.word.to_bytes(8, 'big')
        if order == INTEL:
            stored, start, reserved, virtual = \
                self._FORMATS[INTEL].unpack(data)
        elif order == MOTOROLA:
            virtual, reserved, start, stored = \
                self._FORMATS[MOTOROLA].unpack(data)
        else:
            raise ValueError(f"unknown order: {order!r}")
        return Fields(virtual, reserved, start, stored + 1)


    # The fields at a glance, Motorola order.
    @property
    def virtual                 (self): return self.unload().virtual

    @property
    def reserved                (self): return self.unload().reserved

    @property
    def start                   (self): return self.unload().start

    @property
    def count                   (self): return self.unload().count


    def coordinate              (self, order=MOTOROLA):

        'the start of this block, as a BeamCoordinate'

        start = self.unload(order).start
        cube  = start // Cube.SECTORS_PER_CUBE
        local = Bijection().to_coordinate(start % Cube.SECTORS_PER_CUBE)
        return BeamCoordinate(cube, local.sector, local.row, local.plane)


    def __int__                 (self):

        return self.word


    def __eq__                  (self, other):

        if not isinstance       (other, CPUPointer):
            return NotImplemented

        return self.word == other.word


    def __hash__                (self):

        return hash             (self.word)


    def __repr__                (self):

        return f"CPUPointer(0x{self.word:016X})"
