"""Control replay: the same reduced stream through a binary buddy.

Matched-units control for the Beam replay (Paper 2, Real Debian
Numbers).  Same stream, same arena, same grain as test_driver.py:

    arena   512 MiB = 131072 pages of 4 KiB (orders 0..17)
    request sectors = ceil(bytes / 4096), as in the Beam driver
    grant   the smallest power-of-two block of pages that holds
            the request: 2^ceil(log2(sectors)) pages

Policy, stated so the model is not mistaken for the kernel itself:
deterministic lowest-address first-fit.  Allocation takes the
lowest-address free block of the smallest sufficient order and
splits it down, keeping the left piece.  Freeing coalesces with
the buddy while the buddy is free.  This is the classic buddy
geometry: power-of-two rounding, splitting, coalescing, and the
fragmentation that follows from them.  Linux's list discipline
differs in detail; the geometry under test does not.

Same honest policy as the Beam driver: a reborn pointer frees its
old block first (inferred free), unknown frees are counted and
skipped, zero requests are skipped.

Occupancy is granted pages live (what the buddy has handed out,
rounding included).  LPFR is sampled: the largest free block, in
pages, at each sample point.

Usage:
    python3 buddy_replay.py <stream.csv> <series.csv>
                            [sample_every] [grain]

The arena is always 512 MiB; the grain defaults to 4096, so the
buddy's page is the grain and its page count is 512 MiB / grain.
"""

import heapq
import sys

GRAIN = int(sys.argv[4]) if len(sys.argv) > 4 else 4096
PAGES = int(sys.argv[5]) if len(sys.argv) > 5 else (512 * 1024 * 1024) // GRAIN
MAX_ORDER = PAGES.bit_length() - 1


def order_for(sectors):
    return (sectors - 1).bit_length()


class Buddy:
    def __init__(self):
        self.free_set = [set() for _ in range(MAX_ORDER + 1)]
        self.free_heap = [[] for _ in range(MAX_ORDER + 1)]
        self.free_set[MAX_ORDER].add(0)
        heapq.heappush(self.free_heap[MAX_ORDER], 0)
        self.granted = 0

    def _take(self, order):
        heap, members = self.free_heap[order], self.free_set[order]
        while heap:
            start = heapq.heappop(heap)
            if start in members:
                members.remove(start)
                return start
        return None

    def _give(self, order, start):
        self.free_set[order].add(start)
        heapq.heappush(self.free_heap[order], start)

    def allocate(self, sectors):
        want = order_for(sectors)
        for order in range(want, MAX_ORDER + 1):
            if not self.free_set[order]:
                continue
            start = self._take(order)
            while order > want:
                order -= 1
                self._give(order, start + (1 << order))
            self.granted += 1 << want
            return (start, want)
        return None

    def free(self, start, order):
        self.granted -= 1 << order
        while order < MAX_ORDER:
            buddy = start ^ (1 << order)
            if buddy not in self.free_set[order]:
                break
            self.free_set[order].remove(buddy)
            start = min(start, buddy)
            order += 1
        self._give(order, start)

    def lpfr(self):
        for order in range(MAX_ORDER, -1, -1):
            if self.free_set[order]:
                return 1 << order
        return 0


def sectors_for(byte_request):
    return -(-byte_request // GRAIN)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2

    stream_path, series_path = sys.argv[1], sys.argv[2]
    sample_every = int(sys.argv[3]) if len(sys.argv) > 3 else 1000

    buddy = Buddy()
    live = {}

    events = 0
    refusals = 0
    frag_refusals = 0
    largest_refused = 0
    unknown_frees = 0
    inferred_frees = 0
    zero_requests = 0
    peak_granted = 0
    peak_objects = 0
    min_lpfr = PAGES

    with open(stream_path) as stream, open(series_path, 'w') as series:
        series.write('event,granted_pages,live_objects,lpfr_pages\n')
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
                    buddy.free(*old)
                got = buddy.allocate(sectors_for(req))
                if got is None:
                    refusals += 1
                    free_total = PAGES - buddy.granted
                    if free_total >= sectors_for(req):
                        frag_refusals += 1
                    if req > largest_refused:
                        largest_refused = req
                else:
                    live[ptr] = got
            else:
                old = live.pop(parts[1], None)
                if old is None:
                    unknown_frees += 1
                else:
                    buddy.free(*old)

            if buddy.granted > peak_granted:
                peak_granted = buddy.granted
            if len(live) > peak_objects:
                peak_objects = len(live)

            if events % sample_every == 0:
                lp = buddy.lpfr()
                if lp < min_lpfr:
                    min_lpfr = lp
                series.write(f'{events},{buddy.granted},'
                             f'{len(live)},{lp}\n')

    print(f'events            {events}')
    print(f'refusals          {refusals}')
    print(f'of which fragm.   {frag_refusals}')
    print(f'largest refused   {largest_refused} bytes')
    print(f'unknown frees     {unknown_frees}')
    print(f'inferred frees    {inferred_frees}')
    print(f'zero requests     {zero_requests}')
    print(f'peak granted      {peak_granted} pages '
          f'({peak_granted * GRAIN / 1048576:.2f} MiB)')
    print(f'peak live objects {peak_objects}')
    print(f'granted at end    {buddy.granted} pages '
          f'({buddy.granted * GRAIN / 1048576:.2f} MiB)')
    print(f'live at end       {len(live)} objects')
    print(f'min LPFR sampled  {min_lpfr} pages')
    print(f'LPFR at end       {buddy.lpfr()} pages')
    return 0


if __name__ == '__main__':
    sys.exit(main())
