#!/usr/bin/env python3
"""Telezart sector calibration.

Reads a reduced kmalloc trace (CSV with header: op,bytes,ptr where
op is 'alloc' or 'free', bytes is bytes_req for allocs, ptr is the
allocation's pointer token) and reports, for each candidate sector
size, the peak live sector count the load would need in an Iscandar
pool of 32768 sectors, plus the internal waste at that peak.

The point (Andrew's design, 2026-11-03): trace the real byte load
from Debian first, then calibrate the sector size to the load.
No sector size is assumed here; the table is the evidence.

Usage: python3 calibrate_sector.py reduced-trace.csv

Andrew's calibration rule (2026-11-03): the sector size sits at the
bottom 20% of observed requests or below (Pareto). In practice: take
P20 of the observed request sizes; the pick is the largest candidate
sector that does not exceed P20, so at most the smallest fifth of
requests under-fill a sector and the other 80% span at least one
full sector.

The Pareto line is the ceiling of a feasible window, not the whole
rule. Two floors come from the geometry itself:
- capacity floor: sector >= peak live bytes / 32768, or the arena
  cannot hold the live set at k=3 no matter the waste;
- largest-request floor: sector >= max request / 32767, or the
  biggest single request exceeds the Huge mode ceiling.
If the floors rise above the Pareto ceiling, no sector at k=3
satisfies all three, which is the condition for Andrew's k=4 branch
(pool 32^4 = 1,048,576 sectors, floors fall by a factor of 32).

One exclusion, Andrew's ruling 2026-11-03: there is no mode beyond
Huge and there will not be one; requests above the Huge ceiling at
the sector in question cannot be included in the k=3 load at all.
They are counted here as out-of-contract per sector size, a
statistic of the run, never an allocator failure.
"""

import csv
import sys

POOL_SECTORS = 32768
CANDIDATES = [4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096]


def load(path):
    events = []
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            events.append((row['op'], int(row['bytes']), row['ptr']))
    return events


def replay_stats(events, sector):
    live = {}          # ptr -> sectors held
    live_sectors = 0
    live_bytes = 0
    peak_sectors = 0
    peak_bytes = 0
    held_bytes_at_peak = 0
    unmatched_free = 0
    out_of_contract = 0
    for op, nbytes, ptr in events:
        if op == 'alloc':
            sectors = -(-nbytes // sector) if nbytes > 0 else 0
            if sectors > POOL_SECTORS - 1:  # beyond the Huge ceiling
                out_of_contract += 1
                continue
            if ptr in live:  # pointer reuse without free: count as replace
                live_sectors -= live[ptr][0]
                live_bytes -= live[ptr][1]
            live[ptr] = (sectors, nbytes)
            live_sectors += sectors
            live_bytes += nbytes
            if live_sectors > peak_sectors:
                peak_sectors = live_sectors
                peak_bytes = live_bytes
                held_bytes_at_peak = live_sectors * sector
        elif op == 'free':
            if ptr in live:
                sectors, nbytes = live.pop(ptr)
                live_sectors -= sectors
                live_bytes -= nbytes
            else:
                unmatched_free += 1
    return (peak_sectors, peak_bytes, held_bytes_at_peak,
            unmatched_free, out_of_contract)


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    events = load(sys.argv[1])
    allocs = sum(1 for e in events if e[0] == 'alloc')
    sizes = sorted(e[1] for e in events if e[0] == 'alloc')
    print(f'events: {len(events)}  allocs: {allocs}')
    if sizes:
        print(f'request bytes: min {sizes[0]}  median '
              f'{sizes[len(sizes)//2]}  max {sizes[-1]}')
    if sizes:
        p20 = sizes[int(0.20 * (len(sizes) - 1))]
        # peak live bytes from the finest replay (sector 1 = bytes)
        peak_bytes_live = replay_stats(events, 1)[0]
        cap_floor = -(-peak_bytes_live // POOL_SECTORS)
        max_floor = -(-sizes[-1] // (POOL_SECTORS - 1))
        floor = max(cap_floor, max_floor)
        pick = max((c for c in CANDIDATES if floor <= c <= p20),
                   default=None)
        print(f'Pareto ceiling: P20 of observed requests is {p20} '
              f'bytes')
        print(f'geometry floors: capacity floor {cap_floor} bytes '
              f'(peak live {peak_bytes_live:,} bytes), '
              f'largest-request floor {max_floor} bytes '
              f'(max request {sizes[-1]:,} bytes)')
        if pick is not None:
            print(f'feasible window at k=3: [{floor}, {p20}]; '
                  f'pick {pick}')
        else:
            print(f'feasible window at k=3 is EMPTY (floor {floor} '
                  f'> ceiling {p20}): this is the k=4 condition')
    else:
        pick = None
    print()
    print(f'{"sector":>7} {"peak sectors":>13} {"of 32768":>9} '
          f'{"arena at peak":>14} {"waste at peak":>14} {"excluded":>9}')
    for sector in CANDIDATES:
        peak, peak_bytes, held, unmatched, ooc = replay_stats(
            events, sector)
        arena = peak * sector
        waste = (held - peak_bytes) / held * 100 if held else 0.0
        fits = 'fits' if peak <= POOL_SECTORS else 'OVERFLOW'
        mark = '  <- Pareto pick' if sector == pick else ''
        print(f'{sector:>7} {peak:>13} {fits:>9} '
              f'{arena:>14,} {waste:>13.1f}% {ooc:>9}{mark}')
    unmatched = replay_stats(events, CANDIDATES[0])[3]
    if unmatched:
        print(f'\nnote: {unmatched} frees named a pointer with no '
              'matching alloc in the trace (freed from before the '
              'capture window, most likely)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
