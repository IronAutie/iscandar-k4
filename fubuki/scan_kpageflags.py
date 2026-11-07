#!/usr/bin/env python3
"""Telezart memory-space scan: decode a /proc/kpageflags dump.

Input: a binary dump taken in the guest with
  dd if=/proc/kpageflags of=kpageflags.bin bs=8
(one little-endian uint64 per page frame, in PFN order).

What this reports, honestly scoped:
- The BUDDY bit (bit 10) is set on the HEAD page of each free block
  on the buddy allocator's free lists. So buddy-flagged PFNs mark
  where free blocks start; the exact size histogram of those blocks
  comes from /proc/buddyinfo (snapshotted beside the dump), not from
  this file.
- Everything spatial is exact, though: which frames are slab, anon,
  page cache, and where they sit. Mapped onto Iscandar's geometry at
  sector = one page, PFN order IS the cube order: 32 frames per row,
  1024 per plane, 32 planes. The per-plane occupancy table below is
  the machine's own memory read in the allocator's native shape.

Stable kernel page-flag bits (include/uapi/linux/kernel-page-flags.h):
  5 LRU, 6 ACTIVE, 7 SLAB, 10 BUDDY, 11 MMAP, 12 ANON, 13 SWAPCACHE,
  17 HUGE, 22 THP, 24 ZERO_PAGE, 26 PGTABLE.
"""

import struct
import sys

BITS = {
    'LRU': 5, 'ACTIVE': 6, 'SLAB': 7, 'BUDDY': 10, 'MMAP': 11,
    'ANON': 12, 'SWAPCACHE': 13, 'HUGE': 17, 'THP': 22,
    'ZERO_PAGE': 24, 'PGTABLE': 26,
}


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    data = open(sys.argv[1], 'rb').read()
    n = len(data) // 8
    flags = struct.unpack(f'<{n}Q', data[:n * 8])
    print(f'frames scanned: {n} '
          f'({n * 4096 / (1024 * 1024):.0f} MiB at 4 KiB pages)')
    counts = {name: 0 for name in BITS}
    for f in flags:
        for name, bit in BITS.items():
            if f & (1 << bit):
                counts[name] += 1
    print('flag counts:', ', '.join(
        f'{k}={v}' for k, v in counts.items() if v))
    buddy_heads = [i for i, f in enumerate(flags)
                   if f & (1 << BITS['BUDDY'])]
    print(f'free-block heads (BUDDY): {len(buddy_heads)}')
    if buddy_heads:
        gaps = [b - a for a, b in zip(buddy_heads, buddy_heads[1:])]
        print(f'spacing between free-block heads: '
              f'min {min(gaps)}, max {max(gaps)}')
    print()
    print('occupancy by plane (1024 frames per plane, cube order):')
    print(f'{"plane":>5} {"non-buddy frames":>17} {"buddy heads":>12}')
    for plane in range((n + 1023) // 1024):
        chunk = flags[plane * 1024:(plane + 1) * 1024]
        heads = sum(1 for f in chunk if f & (1 << BITS['BUDDY']))
        non_buddy = sum(1 for f in chunk
                        if not (f & (1 << BITS['BUDDY'])))
        print(f'{plane:>5} {non_buddy:>17} {heads:>12}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
