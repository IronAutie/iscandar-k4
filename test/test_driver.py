"""Test driver: replay a reduced alloc/free stream through a Beam.

Specification (Andrew, 2026-11-05): a Beam of 4 cubes, and trace
byte requests mapped to sectors at the 4 KiB grain:

    sectors = ceil(bytes / 4096)

so the arena is 4 x 32768 = 131072 sectors = 512 MiB, the size of
the machine the control run booted on.  Occupancy is the beam's own
counter read in sectors.  LPFR (largest possible fit remaining) is
sampled, not tracked per event: at each sample point it is the
largest contiguous free run of sectors in any one cube, read off
the engines' sector maps.  A run of free sectors is an upper bound
on what that cube's search could grant at that instant.

The driver keeps the live set itself: stream pointer -> CPUPointer.
A free for a pointer the driver never saw (allocated before the
trace was armed) is counted and skipped.  A refused allocation is
counted, with the largest refused request kept.  A free whose
engine status is not GEAR_SUCCESS is counted as an anomaly: by
doctrine that is debugger time, never silently absorbed.

Honest policy on reborn pointers (Andrew's ruling, 2026-11-05):
when an allocation arrives for a pointer the driver still holds
live, the kernel cannot have reissued a live pointer, so a free
must have happened through a path the tracepoints do not cover.
The driver frees the old pointer first, counts it as an inferred
free, and then allocates.  The old allocation is never orphaned
with its sectors left marked.

Usage:
    python3 test_driver.py <stream.csv> <series.csv>
                           [sample_every] [grain] [cubes]

Defaults are the first fair-test configuration: grain 4096, 4 cubes.
"""

import sys
from pathlib import Path

K4 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(K4))

from Beam import Beam
from Status import Status

GRAIN = int(sys.argv[4]) if len(sys.argv) > 4 else 4096
CUBES = int(sys.argv[5]) if len(sys.argv) > 5 else 4


def sectors_for(byte_request):
    return -(-byte_request // GRAIN)   # ceiling division


def largest_free_run(engine):
    # engine.sectors is 1024 words of 32 sector bits, in
    # displacement order: bit p of the whole store is sector p.
    # Read it as one integer and take the longest run of zeros.
    bits = int.from_bytes(engine.sectors.tobytes(), 'little')
    return max(len(run) for run in format(bits, '032768b').split('1'))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2

    stream_path, series_path = sys.argv[1], sys.argv[2]
    sample_every = int(sys.argv[3]) if len(sys.argv) > 3 else 1000

    beam = Beam(CUBES)
    live = {}

    events = 0
    refusals = 0
    largest_refused = 0
    unknown_frees = 0
    inferred_frees = 0
    free_anomalies = 0
    zero_requests = 0
    peak_sectors = 0
    peak_objects = 0

    with open(stream_path) as stream, open(series_path, 'w') as series:
        series.write('event,live_sectors,live_objects,lpfr_sectors\n')
        for line in stream:
            events += 1
            parts = line.rstrip('\n').split(',')
            if parts[0] == 'A':
                ptr, req = parts[1], int(parts[2])
                if req == 0:
                    zero_requests += 1
                    continue
                old = live.pop(ptr, None)
                if old is not None:
                    inferred_frees += 1
                    if beam.free(old) != Status.GEAR_SUCCESS:
                        free_anomalies += 1
                pointer = beam.allocate(sectors_for(req))
                if pointer is None:
                    refusals += 1
                    if req > largest_refused:
                        largest_refused = req
                else:
                    live[ptr] = pointer
            else:
                pointer = live.pop(parts[1], None)
                if pointer is None:
                    unknown_frees += 1
                elif beam.free(pointer) != Status.GEAR_SUCCESS:
                    free_anomalies += 1

            if beam.count_overall > peak_sectors:
                peak_sectors = beam.count_overall
            if len(live) > peak_objects:
                peak_objects = len(live)

            if events % sample_every == 0:
                lpfr = max(largest_free_run(e) for e in beam.engines)
                series.write(f'{events},{beam.count_overall},'
                             f'{len(live)},{lpfr}\n')

    print(f'events            {events}')
    print(f'refusals          {refusals}')
    print(f'largest refused   {largest_refused} bytes')
    print(f'unknown frees     {unknown_frees}')
    print(f'inferred frees    {inferred_frees}')
    print(f'free anomalies    {free_anomalies}')
    print(f'zero requests     {zero_requests}')
    print(f'peak live sectors {peak_sectors}')
    print(f'peak live objects {peak_objects}')
    print(f'live at end       {len(live)} objects, '
          f'{beam.count_overall} sectors')
    return 0


if __name__ == '__main__':
    sys.exit(main())
