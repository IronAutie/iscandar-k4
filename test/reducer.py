"""Reduce a raw ftrace capture to an ordered alloc/free stream.

Reads the kernel trace text (kmalloc, kmem_cache_alloc, kfree and
kmem_cache_free events) and writes a plain stream file:

    A,<ptr>,<bytes_req>     an allocation was born
    F,<ptr>                  a pointer was freed

Everything else in the capture is dropped.  The reducer also keeps
the matching books: a free that names a live pointer is matched;
a free that names no live pointer (allocated before the trace was
armed, or freed through a path the tracepoints do not cover) is
counted as unmatched and still written to the stream, so the
driver decides what to do with it.  An allocation that reuses a
still-live pointer is counted as an overwrite anomaly.

Usage:
    python3 reducer.py <trace.txt> <stream.csv>
"""

import re
import sys

ALLOC_EVENTS = ('kmalloc:', 'kmem_cache_alloc:')
FREE_EVENTS = ('kfree:', 'kmem_cache_free:')

PTR = re.compile(r'ptr=([0-9a-fx]+)')
REQ = re.compile(r'bytes_req=(\d+)')


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    trace_path, stream_path = sys.argv[1], sys.argv[2]

    live = {}
    lines = allocs = frees = matched = unmatched = overwrites = 0
    total_req = 0

    with open(trace_path) as trace, open(stream_path, 'w') as stream:
        for line in trace:
            lines += 1
            if 'ptr=' not in line:
                continue
            m = PTR.search(line)
            if m is None:
                continue
            ptr = m.group(1)
            if any(e in line for e in ALLOC_EVENTS):
                r = REQ.search(line)
                if r is None:
                    continue
                req = int(r.group(1))
                allocs += 1
                total_req += req
                if ptr in live:
                    overwrites += 1
                live[ptr] = req
                stream.write(f'A,{ptr},{req}\n')
            elif any(e in line for e in FREE_EVENTS):
                frees += 1
                if ptr in live:
                    matched += 1
                    del live[ptr]
                else:
                    unmatched += 1
                stream.write(f'F,{ptr}\n')

    print(f'lines read        {lines}')
    print(f'allocations       {allocs}')
    print(f'frees             {frees}')
    print(f'frees matched     {matched}')
    print(f'frees unmatched   {unmatched}')
    print(f'live at end       {len(live)}')
    print(f'overwrite anomaly {overwrites}')
    print(f'sum bytes_req     {total_req}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
