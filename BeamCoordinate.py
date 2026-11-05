import sys
from pathlib import Path

K3 = Path(__file__).resolve().parent.parent / "iscandar"
sys.path.insert(0, str(K3))

from Coordinate import Coordinate


class BeamCoordinate            (Coordinate):
    'k=4 coordinate, extending theorem from k=3 to k=4'
    
    def __init__                (self, cube, sector, row, plane):
    
        Coordinate.__init__     (self, sector, row, plane)
        self.cube = cube 
        

    def k3                      (self):

        'return k=3 coordinate from k=4 coordinate'
        
        return Coordinate       (self.sector, self.row, self.plane)
  
    def __eq__                  (self, other):

        if not isinstance       (other, BeamCoordinate):
            return isinstance   (other, Coordinate) and False or NotImplemented


        return (self.cube, self.sector, self.row, self.plane) == \
               (other.cube, other.sector, other.row, other.plane)


    def __hash__                (self):

        return hash             ((self.cube, self.sector, self.row, self.plane))


    def __repr__                (self):

        return f"BeamCoordinate(cube={self.cube}, sector={self.sector}, row={self.row}, plane={self.plane})"
