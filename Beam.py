import sys
from pathlib import Path

K3 = Path(__file__).resolve().parent.parent / "iscandar"
sys.path.insert(0, str(K3))

from MPUPointer import MPUPointer
from allocator  import Engine



class Beam:
  'line of Cubes, extending theorem from k=3 to k=4'

  def __init__  (self, cardinality):

    cardinality = [cardinality, 1] [cardinality <= 0]

    self.count_overall     = 0
    self.cardinality       = cardinality
    self.engines           = [ Engine () for i in range (cardinality) ]
    self.sectors_supported = self.engines [0].SECTORS_PER_CUBE * cardinality
    self.lead              = 0


  def rotate    (self):

    'rotate lead engine of beam'

    self.lead          = (self.lead + 1) % self.cardinality


  def scan      (self, request):

    'scan a single engine to allocate a virtual pointer from it'

    engine             = self.engines [self.lead]

    if (engine.SECTORS_PER_CUBE - engine.count_overall) < request:
      return

    return engine (request)


  def allocate  (self, request):

    'allocation loop for modelling, should be inline later'

    if (self.sectors_supported - self.count_overall) < request:
      return

    for index in range (self.cardinality):
      result = self.scan (request)

      if (isinstance (result, MPUPointer)):
        self.count_overall += request
        return result
      
      self.rotate ()

