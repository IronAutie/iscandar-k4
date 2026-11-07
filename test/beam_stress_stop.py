"""Replay the stream through a Beam and stop at a chosen event.

Built to answer a matched-instant question: what does the Beam
look like at the exact stream event where the buddy control hit
its peak stress?  Same mapping (sectors = ceil(bytes / grain)) and
same honest policy as test_driver.py: a reborn pointer frees its
old allocation first (inferred free), unknown frees are counted
and skipped.

The stop dump reports the beam counter, live objects, refusals and
free anomalies to that point, and for each cube: sectors in use,
sectors free, the largest contiguous free run (that cube's LPFR),
and the number of separate free runs.

Usage:
    python3 beam_stress_stop.py <stream.csv> <stop_event>
                                [grain] [cubes]
"""

import sys
from pathlib import Path

K4 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(K4))
sys.path.insert(0, str(K4.parent))

from Beam import Beam
from Status import Status

SECTORS_PER_CUBE = 32768


def sectors_for(byte_request, grain):
    return -(-byte_request // grain)


def cube_free_stats(engine):
    bits = format(
        int.from_bytes(engine.sectors.tobytes(), 'little'), '032768b')
    runs = [len(run) for run in bits.split('1') if run]
    return (max(runs) if runs else 0), len(runs)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2

    stream_path = sys.argv[1]
    stop_event = int(sys.argv[2])
    grain = int(sys.argv[3]) if len(sys.argv) > 3 else 4096
    cubes = int(sys.argv[4]) if len(sys.argv) > 4 else 2

    beam = Beam(cubes)
    live = {}

    events = 0
    refusals = 0
    largest_refused = 0
    unknown_frees = 0
    inferred_frees = 0
    free_anomalies = 0
    zero_requests = 0

    with open(stream_path) as stream:
        for line in stream:
            events += 1
            parts = line.rstrip('\n').split(',')
            if parts[0] == 'A':
                ptr, req = parts[1], int(parts[2])
                if req == 0:
                    zero_requests += 1
                else:
                    old = live.pop(ptr, None)
                    if old is not None:
                        inferred_frees += 1
                        if beam.free(old) != Status.GEAR_SUCCESS:
                            free_anomalies += 1
                    got = beam.allocate(sectors_for(req, grain))
                    if got is None:
                        refusals += 1
                        if req > largest_refused:
                            largest_refused = req
                    else:
                        live[ptr] = got
            else:
                old = live.pop(parts[1], None)
                if old is None:
                    unknown_frees += 1
                elif beam.free(old) != Status.GEAR_SUCCESS:
                    free_anomalies += 1
            if events == stop_event:
                break

    print(f'stopped after event {events}')
    print(f'grain {grain}, cubes {cubes}')
    print(f'refusals {refusals}')
    print(f'largest refused {largest_refused} bytes')
    print(f'unknown frees {unknown_frees}')
    print(f'inferred frees {inferred_frees}')
    print(f'free anomalies {free_anomalies}')
    print(f'zero requests {zero_requests}')
    print(f'live objects {len(live)}')
    print(f'live sectors (beam counter) {beam.count_overall}')
    print(f'total free sectors '
          f'{beam.sectors_supported - beam.count_overall}')
    overall_lpfr = 0
    for index, engine in enumerate(beam.engines):
        lpfr, run_count = cube_free_stats(engine)
        overall_lpfr = max(overall_lpfr, lpfr)
        print(f'cube {index}: used {engine.count_overall}, '
              f'free {SECTORS_PER_CUBE - engine.count_overall}, '
              f'LPFR {lpfr}, free runs {run_count}')
    print(f'beam LPFR {overall_lpfr}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
