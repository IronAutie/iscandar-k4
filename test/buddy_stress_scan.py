"""Find the buddy replay's stress extrema and dump a stopped state.

Configuration defaults match the 256 MiB test: 65,536 pages of
4 KiB.  The scan follows the same honest policy as buddy_replay.py:
a reborn pointer frees its old block first, and unknown frees are
counted and skipped.

Without --stop, the scan reports the first and last events reaching
peak granted occupancy, minimum LPFR, and maximum free-space
fragmentation, where fragmentation is 1 - LPFR / total_free.

With --stop EVENT, the replay stops immediately after that stream
event and prints the complete free-block distribution by order.
"""

import argparse
import heapq


def order_for(units):
    return (units - 1).bit_length()


class Buddy:
    def __init__(self, pages):
        self.max_order = pages.bit_length() - 1
        self.free_set = [set() for _ in range(self.max_order + 1)]
        self.free_heap = [[] for _ in range(self.max_order + 1)]
        self.free_set[self.max_order].add(0)
        heapq.heappush(self.free_heap[self.max_order], 0)
        self.granted = 0

    def _take(self, order):
        heap = self.free_heap[order]
        members = self.free_set[order]
        while heap:
            start = heapq.heappop(heap)
            if start in members:
                members.remove(start)
                return start
        return None

    def _give(self, order, start):
        self.free_set[order].add(start)
        heapq.heappush(self.free_heap[order], start)

    def allocate(self, units):
        want = order_for(units)
        for order in range(want, self.max_order + 1):
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
        while order < self.max_order:
            buddy = start ^ (1 << order)
            if buddy not in self.free_set[order]:
                break
            self.free_set[order].remove(buddy)
            start = min(start, buddy)
            order += 1
        self._give(order, start)

    def lpfr(self):
        for order in range(self.max_order, -1, -1):
            if self.free_set[order]:
                return 1 << order
        return 0


def describe(event, op, buddy, live_count, pages):
    total_free = pages - buddy.granted
    lpfr = buddy.lpfr()
    fragmentation = 0.0 if total_free == 0 else 1.0 - lpfr / total_free
    return {
        'event': event,
        'op': op,
        'granted': buddy.granted,
        'total_free': total_free,
        'lpfr': lpfr,
        'fragmentation': fragmentation,
        'live_objects': live_count,
    }


def print_record(label, record):
    if record is None:
        print(f'{label}: none')
        return
    print(f"{label}: event {record['event']}; op {record['op']}; "
          f"granted {record['granted']}; free {record['total_free']}; "
          f"LPFR {record['lpfr']}; fragmentation "
          f"{record['fragmentation']:.6f}; live objects "
          f"{record['live_objects']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stream')
    parser.add_argument('--pages', type=int, default=65536)
    parser.add_argument('--grain', type=int, default=4096)
    parser.add_argument('--stop', type=int)
    args = parser.parse_args()

    buddy = Buddy(args.pages)
    live = {}
    unknown_frees = 0
    inferred_frees = 0
    refusals = 0

    max_granted_first = None
    max_granted_last = None
    min_lpfr_first = None
    min_lpfr_last = None
    max_frag_first = None
    max_frag_last = None
    max_objects_first = None
    max_objects_last = None

    with open(args.stream) as stream:
        for event, line in enumerate(stream, 1):
            parts = line.rstrip('\n').split(',')
            op = line.rstrip('\n')
            if parts[0] == 'A':
                ptr = parts[1]
                request = int(parts[2])
                if request == 0:
                    if event == args.stop:
                        break
                    continue
                old = live.pop(ptr, None)
                if old is not None:
                    inferred_frees += 1
                    buddy.free(*old)
                units = -(-request // args.grain)
                got = buddy.allocate(units)
                if got is None:
                    refusals += 1
                else:
                    live[ptr] = got
            else:
                ptr = parts[1]
                old = live.pop(ptr, None)
                if old is None:
                    unknown_frees += 1
                else:
                    buddy.free(*old)

            if args.stop is not None:
                if event == args.stop:
                    break
                continue

            record = describe(event, op, buddy, len(live), args.pages)

            if (max_granted_first is None or
                    record['granted'] > max_granted_first['granted']):
                max_granted_first = record
                max_granted_last = record
            elif record['granted'] == max_granted_first['granted']:
                max_granted_last = record

            if (min_lpfr_first is None or
                    record['lpfr'] < min_lpfr_first['lpfr']):
                min_lpfr_first = record
                min_lpfr_last = record
            elif record['lpfr'] == min_lpfr_first['lpfr']:
                min_lpfr_last = record

            if (max_frag_first is None or
                    record['fragmentation'] >
                    max_frag_first['fragmentation']):
                max_frag_first = record
                max_frag_last = record
            elif (record['fragmentation'] ==
                    max_frag_first['fragmentation']):
                max_frag_last = record

            if (max_objects_first is None or
                    record['live_objects'] >
                    max_objects_first['live_objects']):
                max_objects_first = record
                max_objects_last = record
            elif (record['live_objects'] ==
                    max_objects_first['live_objects']):
                max_objects_last = record

    if args.stop is not None:
        total_free = args.pages - buddy.granted
        print(f'stopped after event {args.stop}')
        print(f'granted {buddy.granted}')
        print(f'total free {total_free}')
        print(f'LPFR {buddy.lpfr()}')
        print(f'live objects {len(live)}')
        print(f'unknown frees so far {unknown_frees}')
        print(f'inferred frees so far {inferred_frees}')
        print(f'refusals so far {refusals}')
        print('free blocks by order:')
        accounted = 0
        for order in range(buddy.max_order, -1, -1):
            starts = sorted(buddy.free_set[order])
            size = 1 << order
            accounted += len(starts) * size
            print(f'  order {order:2d} ({size:6d} pages): '
                  f'{len(starts):4d} blocks; starts {starts}')
        print(f'free pages accounted {accounted}')
        return 0

    print_record('peak granted first', max_granted_first)
    print_record('peak granted last', max_granted_last)
    print_record('minimum LPFR first', min_lpfr_first)
    print_record('minimum LPFR last', min_lpfr_last)
    print_record('maximum fragmentation first', max_frag_first)
    print_record('maximum fragmentation last', max_frag_last)
    print_record('peak live objects first', max_objects_first)
    print_record('peak live objects last', max_objects_last)
    print(f'unknown frees {unknown_frees}')
    print(f'inferred frees {inferred_frees}')
    print(f'refusals {refusals}')
    print(f'granted at end {buddy.granted}')
    print(f'live objects at end {len(live)}')
    print(f'LPFR at end {buddy.lpfr()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
