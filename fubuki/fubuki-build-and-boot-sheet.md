# Fubuki: build and boot sheet (draft, 2026-11-03)

Draft v1, prepared by Muse at Andrew's direction, for his review.
Fubuki is Andrew's Telezart build: a stock Debian trixie system whose
page allocations we trace and replay through Iscandar.

## Why the kernel rides in the image after all (verified 2026-11-03)

Andrew decided QEMU hands the kernel in at boot. Preparing that
surfaced a fact that refines how, not whether: Debian's stock kernel
is modular. Checked directly in the config of the current trixie
kernel (linux-image 6.12.113+deb13-amd64, read from the .deb on
Muse's side): CONFIG_ATA_PIIX=m, CONFIG_BLK_DEV_SD=m,
CONFIG_VIRTIO_BLK=m, CONFIG_EXT4_FS=m. A modular kernel cannot mount
any disk root filesystem until its initramfs loads those modules, and
the initramfs is generated from the kernel package itself. So the
image includes linux-image-amd64, and the build exports the vmlinuz,
initrd, and config under fixed names. QEMU still hands all three in
from outside the image at boot; the kernel version is pinned by the
artifact names and the exported config, a separate piece of evidence.

Also verified in that same config: CONFIG_TRACING=y,
CONFIG_EVENT_TRACING=y, CONFIG_FTRACE=y, CONFIG_TRACEPOINTS=y.
The tracing stack the capture depends on is switched on in the stock
kernel build. At first boot we still confirm the kmem events exist in
tracefs (step B3), so the run record shows it, not assumes it.

## Stage A: build (on telesart, at the bench)

- A1. Copy `fubuki.xml` into `~/telezart` on telesart.
- A2. Submit by absolute path (bare filenames fail from other dirs):
  `elbe initvm submit /home/andrew/telezart/fubuki.xml`
- A3. Pass mark: "Package List validation: No Errors found" and a new
  `elbe-build-<timestamp>` folder holding `fubuki.img` plus the
  exported artifacts `telezart-vmlinuz`, `telezart-initrd`,
  `telezart-kconfig` (artifact placement in the output to be
  confirmed on the first run; if they land elsewhere in the folder,
  adjust the paths below once, here in this sheet).

## Stage B: boot and capture (on telesart)

Work in the build output folder, so `fubuki.img` and the artifacts
are under your feet.

- B1. Kernel config check (evidence, 10 seconds):
  `grep -E '^CONFIG_(TRACING|EVENT_TRACING|TRACEPOINTS|FTRACE)=' telezart-kconfig`
  Expect four `=y` lines.
- B2. Boot at exactly 128 MiB, serial console:
  `qemu-system-x86_64 -m 128 -enable-kvm -cpu host -kernel telezart-vmlinuz -initrd telezart-initrd -append "root=LABEL=rfs console=ttyS0 nomodeset" -drive format=raw,file=fubuki.img,if=virtio -vga none -nographic`
  No video, by Andrew's decision 2026-11-03: `-vga none` removes
  the virtual display adapter entirely, so no frame buffer is ever
  allocated; `nomodeset` keeps the kernel from modesetting even if
  a device appears; `-nographic` puts the serial console on the
  terminal. The console is the serial port, ttyS0, not video:
  kernel messages and the login getty (systemd starts a serial
  getty because console=ttyS0 is on the command line) all come
  over it. In the QEMU monitor mux, Ctrl-a c toggles to the
  monitor and Ctrl-a x ends the session.
  Log in as root, password as set in the XML (draft: fubuki).
  Honest unknown: whether stock trixie systemd reaches a prompt
  inside 128 MiB is a measurement, not a promise. If it starves, that
  is itself a finding to record before changing anything.
- B3. Confirm the instruments exist in this kernel:
  `ls /sys/kernel/tracing/events/kmem/`
  Expect the malloc-level events in the list: `kmalloc`,
  `kmalloc_node`, `kmem_cache_alloc`, `kmem_cache_alloc_node`,
  `kfree`, `kmem_cache_free`. (Andrew's ruling, 2026-11-03: trace
  the higher level malloc call, not the page allocator.)
- B4. Start capture: `telezart-capture` (it backgrounds nothing; it
  runs in the console). It snapshots /proc/buddyinfo, vmstat, and
  meminfo to /root/counters-before.txt, enables the six kmalloc-level
  kmem events, and streams the trace to /root/telezart-trace.txt.
  BOOT-CAPTURE VARIANT (the goal, stated by Andrew 2026-11-03:
  gather the allocations from bootup): arming the events after
  login misses the boot itself, so for the real list the kernel
  must arm them from t=0. Append line instead:
  "root=LABEL=rfs console=ttyS0 nomodeset trace_buf_size=16M trace_event=kmem:kmalloc,kmem:kmalloc_node,kmem:kmem_cache_alloc,kmem:kmem_cache_alloc_node,kmem:kfree,kmem:kmem_cache_free"
  The ring buffer then records allocations from the first
  kmalloc of boot; telezart-stop dumps that buffer to
  /root/telezart-trace-boot.txt alongside everything else.
  Honest limit: at 128 MiB the boot kmalloc stream may wrap even
  a 16M buffer before anyone logs in; what survives is the tail
  of boot into userspace, and a wrapped buffer is a measured
  fact to report, not a defect to hide.
  The kmalloc-family events carry the actual byte requests:
  bytes_req (what the caller asked for), bytes_alloc (what the slab
  layer actually granted), and the pointer the free will name.
- B5. In a second console (or after a defined workload window), stop
  with `telezart-stop`, which disables the events, snapshots the
  counters after, and syncs.
- B6. Shut the guest down cleanly (`poweroff`). The trace and counter
  files stay in the image's /root for extraction on the host.

## Stage C: extraction and replay (later sitting)

- C1. Mount the image's root partition read-only on telesart
  (losetup with partition scan) and copy out `telezart-trace.txt`,
  `counters-before.txt`, `counters-after.txt`. Hash them (SHA-256)
  into the Telezart manifest with the kernel version, ELBE version,
  and engine commit, per the evidence publication plan.
- C2. Reduce the trace to the ordered alloc/free sequence and replay
  it through the Iscandar simulator. The load is the actual byte
  requests from the kmalloc level (Andrew's ruling, 2026-11-03):
  each event's bytes_req is the request, each free names its pointer,
  and bytes_alloc rides along so Iscandar's granted-vs-requested can
  be compared against the slab layer's own rounding. The reduced
  dataset keeps the call site and gfp flags per event for audit.
  Sector size is NOT assumed in advance (Andrew's method,
  2026-11-03): the kmalloc trace gives the real Debian byte load
  first, and the sector size is calibrated to that load afterward.
  The calibration tool is `calibrate_sector.py` beside this sheet:
  it replays the reduced trace once per candidate sector size and
  tabulates peak live sectors against the 32,768 pool, arena bytes
  at peak, and internal waste at peak. Andrew's calibration rule
  (2026-11-03): the sector size sits at the bottom 20% of observed
  requests or below, the Pareto rule: the pick is the largest
  candidate sector not exceeding the P20 of observed request sizes,
  so at most the smallest fifth of requests under-fill a sector.
  The tool marks that pick in its table. Compare:
  fit and refusals, occupancy, fragmentation over time,
  granted vs requested, cost tails (maximum, not the mean).

## Open items for Andrew's review

- Root password in the draft XML is `fubuki`. Bench-local VM, serial
  console only, no network configured; change it if he prefers.
- No network packages in v1: capture and extraction are deliberately
  offline (serial + image mount), which keeps the trace clean.
- Image size 2000 MiB is the bookworm example's size, not a
  requirement; shrinking it is a v2 decision if disk matters.

## Anticipated objection: "you adjusted the sector to fit your allocator"

Raised by Andrew himself, 2026-11-03, before any data exists, and
answered by method rather than by argument:

- The calibration rule is fixed in advance and timestamped in this
  sheet and the calibration tool before Fubuki's first trace: sector
  at or below the P20 of observed requests (Pareto), subject to the
  capacity and largest-request floors, with beyond-Huge requests
  excluded as out of contract. A rule written before the data cannot
  have been fitted to the data.
- The full calibration table is published, every candidate sector,
  not just the pick. If the pick were a knife-edge that flatters
  Iscandar while its neighbors fail, any reader can see it in the
  table. A robust result shows a plateau, and the paper reports the
  plateau or its absence.
- Sector size is a declared parameter of the design, not a hidden
  knob: Iscandar's geometry is unit-invariant, and choosing the unit
  by a stated rule for a stated workload is the same kind of act as
  an OS choosing its page size, which is likewise tuned to observed
  loads and always has been.

Frame-level comparison, stated by Andrew 2026-11-03: the idea is to
compare the frames there (the guest's real memory map under the
load, from the kpageflags scans and buddyinfo) against strain on
our own allocator replaying the same load. Same workload, two maps:
the buddy system's spatial stress pattern in the real machine, and
Iscandar's cube under the identical list, judged in analogous terms
(free-run survival at the top sizes, occupancy per plane, where the
strain concentrates).

Headline fragmentation metric, named by Andrew 2026-11-03:
Largest Possible Fit Remaining (LPFR). Overall occupancy can be
identical between the buddy system and Iscandar while LPFR differs
by orders of magnitude, and LPFR is what a late large request
actually meets. Definition at matched moments in the load:
- Buddy (real machine): from the buddyinfo snapshot, the largest
  order with a nonzero free count, in pages/bytes. Its structural
  tax: a big block exists only when aligned buddy pairs are ALL
  free and coalesced; one stray allocation in the wrong half kills
  the whole block.
- Iscandar (replay): operationally probed, not estimated: the
  largest request in sectors that the geometry would accept at
  that moment, found by descending fit probes against the free-run
  structure. Free runs serve at any start they cover; no alignment
  pairing is required.
Report LPFR against occupancy for both systems across the run;
occupancy alone is not a fragmentation verdict.

Thesis for memory conservation, stated by Andrew 2026-11-03:
conservation is not merely holding occupancy down. It is keeping
the memory usable at occupancy: at the same occupancy on the same
load, the allocator that preserves the Largest Possible Fit
Remaining conserves the machine's ability to keep working, and so
lets the same work live in a smaller arena without meeting the
fragmentation wall. LPFR against occupancy is the thesis's chart.
This refines the Gaussian Two headline (same workload, about
two-thirds the memory, an occupancy statement) into a servability
statement.

## Test One (Andrew's summary, 2026-11-03)

Extract the control list. By definition we assume it works for
Debian: the stock system served every request on the list, so the
list is satisfiable; the kernel's run is the control. For each
request on the list we need its size in sectors (the request's
bytes_req converted at the sector under test), which is the replay
input Iscandar is judged against, with LPFR and occupancy read off
both sides at matched moments.

Parked in the pocket (Andrew, 2026-11-03, talk only, do not build):
the Lenovo laptop as a remote debug screen: Fubuki's serial console
offered from telesart over the LAN (telnet socket), PuTTY on the
Lenovo as the console, and the QEMU gdb stub reachable across the
network likewise. Zero cost beyond a socket flag, if ever needed.
The pocket idea's purpose, Andrew 2026-11-03: automated simulated
breakpointing. The gdb stub driven by script, unattended:
breakpoints at chosen kernel functions or conditions, and at each
stop a scripted harvest (frame state, counters, memory scan) with
no human at the console. Where the before/after snapshots give two
frames of the strain film, breakpoint-triggered scans could take
frames at the exact moments that matter (threshold crossings, the
largest requests, specific call sites), identically on every run.

Deliverable restated by Andrew, 2026-11-03, scoping everything
above: "Its possible we won't need any of that. All I want are
just another pair of graphs to add to the paper, called Real
Debian Numbers, and here we will compare how exact fit really
works." The pocket rig (simulated JTAG, debug screen, breakpoint
automation, Wireshark) stays parked unless a graph needs it. The
product is a pair of graphs for the "Real Debian Numbers" section:
occupancy and Largest Possible Fit Remaining, buddy against
Iscandar on the real load: how exact fit really works, in numbers
Debian itself wrote.

## Addendum 2026-11-03 evening: first build succeeded, first boots panic in initramfs unpack

Recorded after the sitting, from Andrew's own reports in chat:

- Build: `elbe-build-20261103-185517` (19:04 local). validation.txt:
  "No Errors found". Artifacts present: telezart-vmlinuz 12,142,528
  bytes, telezart-initrd 36,356,881 bytes, telezart-kconfig 283,337
  bytes, fubuki.img as fubuki.img.tar.xz (290,618,160 bytes packed).
- Config check B1 passed exactly: CONFIG_TRACEPOINTS=y,
  CONFIG_EVENT_TRACING=y, CONFIG_TRACING=y, CONFIG_FTRACE=y.
- First boot (trace_buf_size=16M, six kmem events armed at t=0)
  panicked at about 1.0 s: "System is deadlocked on memory", stack
  through unpack_to_rootfs / do_populate_rootfs / kernel_write.
  That is the initramfs unpack, before root mount, before systemd.
- Second boot at trace_buf_size=2M, with -no-reboot added, panicked
  the same way. So buffer size alone is not convicted; it may be an
  accomplice, not the murderer.
- No stray QEMU was killed: the long command line Andrew inspected
  (1 GiB, 8 vCPUs, hostfwd tcp::7587) is the ELBE initvm under
  libvirt, alive and correctly left alone. The panicked Fubuki left
  no survivor process.

Arithmetic that frames the next test (estimates, not measurements):
the compressed initrd is 34.7 MiB. Unpacked at a typical 2.5 to 3x
ratio it wants roughly 87 to 104 MiB of the 128 MiB machine, before
the resident kernel and page structures take their share. A plain
boot may therefore panic in the same place with no tracing at all.

Next step, already given in chat, is the control: boot plain (no
trace_buf_size, no trace_event) at 128 MiB.
- If plain boots: tracing weight is the problem. Capture from
  inside a living system instead (telezart-capture after login),
  and take the boot list from a separate, explicitly labelled run.
- If plain panics in unpack_to_rootfs: the initrd is too fat for
  128 MiB as built. Two honest branches, neither hides the fact:
  (1) a capture-only boot at larger RAM (for example 512 MiB) to
  extract the boot allocation list; the list stays a valid control
  because Test One defines it as satisfiable by Debian's own run,
  and the replay, not the capture machine, is where Iscandar's
  arena is judged; record the capture RAM in the manifest.
  (2) slim the initrd in the XML (initramfs-tools MODULES=dep,
  fewer packages) and rebuild, keeping the stock kernel and the
  same six events, and retry at exactly 128 MiB.
  Which branch, if either, is Andrew's call.

FIRST BOOT RECORD (2026-11-03 evening): build clean from the
current fubuki.xml (build dir elbe-build-20261103-185517).
Kernel config verified: TRACING, EVENT_TRACING, FTRACE,
TRACEPOINTS all =y. The initrd is an UNCOMPRESSED cpio of
36 MB. At -m 128 the kernel panics during populate_rootfs
(memory deadlock) with the trace_event append AND with a plain
append alike; tracing stands acquitted. At -m 512 Fubuki
reached its login prompt. Conclusion of record: the ELBE-shipped
configuration (stock trixie systemd + 36 MB uncompressed
initramfs) has a floor above 128 MiB. Open for Andrew: bisect
the floor (256 next), slim the initramfs (MODULES=dep,
compressed), and rule on what this does to the 128 MiB framing.

CAPTURE PROVEN (2026-11-03 evening): in the running guest the
capture/stop scripts produced a trace containing kmalloc
events with byte counts (Andrew's report). Repairs folded back
into fubuki.xml: event enables are existence-guarded (the
*_node tracepoints are absent on this non-NUMA kernel), and the
capture script's trace_pipe cat is backgrounded so the console
prompt survives.

RULING (Andrew, 2026-11-03): publish the 128 MiB failure of
the untouched configuration as a measured fact, AND slim
Fubuki until she boots at 128 MiB. No bisection.

FIRST TRACE SAMPLE STATS (Andrew ran the awk summary in the guest,
2026-11-03 evening; short post-login capture at -m 512, NOT the
boot list): allocs 1584; sum_req 799658 bytes; sum_alloc 858272
bytes (SLUB rounding tax 58614 bytes, about 7.3% over ask);
max_req 16592 bytes. Histogram: <=64: 580; 65-256: 731;
257-1024: 119; 1025-8192: 153; >8192: 1. Readings: 82.8% of
requests are <=256 bytes; 90.3% are <=1024; P20 falls inside the
<=64 bucket (exact percentile waits for the raw trace); demand
shape is bimodal, small control objects plus a 1-8 KiB buffer
hump. Peak LIVE demand is not derivable from alloc totals alone;
that needs the pointer-matched reducer output.

FAIRNESS RULING (Andrew, 2026-11-03): "at a sector size of
4 bytes, our cube is 128KiB. not a fair test." Methodological
consequence: a replay must endow the allocator under test with
the same total memory as the machine being compared. Sector
size sets granularity; cube count (the k ladder) sets the
endowment. A single k=3 cube at a 4-byte sector is a 128 KiB
arena and cannot fairly stand against a whole Debian machine;
small sectors demand tiled cubes (k=4 beams / k=5 plates) to
reach machine scale, and a single-cube test implicitly forces
the sector by machine size (32768 x 4 KiB = the 128 MiB
machine exactly).

INITRAMFS ACCOUNTING, clarified by Andrew's pushback
(2026-11-03): Andrew: "I really dont believe initramfs should
count as a significant fraction of the cube, do you?" Adopted
clarification: the bulk initramfs is a pre-allocator boot
reservation, loaded by QEMU/boot protocol and held through
memblock before the kmalloc regime. It is common to both
allocators and is NOT chargeable to the cube in Test One.
Only the actual kmalloc/page requests emitted during unpack
belong in the control list. The initramfs remains relevant
only to the separate observation that the ELBE-shipped
configuration could not boot at 128 MiB, which is a packaging
floor, not an allocator verdict.

ZERO-TO-LOGIN COUNT (Andrew's stated want, 2026-11-03): the
boot run's first deliverable is a count of allocations from
t=0 to the login prompt, split by kmalloc and kmem_cache_alloc,
with frees counted alongside. That count, with the size
histogram and pointer-matched frees, is what the sector
estimate is computed from; the count alone is the gross ceiling.
Method: boot with the trace_event append so the kernel arms the
kmem events from t=0. At login, before stopping, read
/sys/kernel/tracing/per_cpu/cpu0/stats: if dropped events is 0,
the dumped ring buffer count is exact; if dropped is nonzero,
the count is a lower bound and the run is repeated with the
early-streaming capture in the slim build. The 512 MiB machine
is the diagnostic seat for this count; the slim 128 MiB build
inherits the method.

ZERO-TO-LOGIN COUNT, FIRST MEASUREMENT (Andrew, in the guest,
2026-11-03 evening; boot-capture run at -m 512, trace armed
from t=0, dump at /root/telezart-trace-boot.txt):
kmalloc events: 20096. kmem_cache_alloc events: 131390.
Total allocation events zero to login: 151486.
Not yet on record: the dropped-events reading for this run
(exactness of the count rides on it), the free counts, and the
size histogram over the boot dump.

BOOT DUMP STATISTICS (Andrew, in the guest, 2026-11-03):
allocs 151486; sum_req 155841190 bytes; sum_alloc 157955888
(SLUB tax 2114698 bytes, about 1.36% over ask at boot scale);
max_req 177418 bytes. Histogram: <=64: 50084; 65-256: 61585;
257-1024: 5568; 1025-8192: 34189; >8192: 60.
Frees: kfree 39920; kmem_cache_free 130932; total frees
170852, which exceeds counted allocs by 19366. By family:
kmem_cache nets +458 live at login; kmalloc nets -19824,
the signature of the early-boot slab population (allocated
before the tracepoints armed) being freed during boot.
Reducer must treat those as frees of pre-window objects.
Feasibility arithmetic from max_req alone: a single request
of 177418 bytes needs 44355 sectors at 4 B (out of contract),
22178 at 8 B, 1387 at 128 B; the largest-request floor for
k=3 is a sector of at least 6 bytes, so 8 B is the smallest
candidate that can express the boot's biggest request at all.
P20 of boot requests falls inside the <=64 bucket. Peak LIVE
sectors still require the pointer-matched reducer.

SLIMMING TARGET (Andrew, 2026-11-03): trim Fubuki until the
zero-to-login request total is less than 128 MiB overall.
Baseline from the untouched build: sum_req 155,841,190 bytes
(148.6 MiB), which is 21,623,462 bytes over the 134,217,728
line, a reduction of about 13.9% in requested bytes
(sum_alloc baseline 157,955,888, about 15.0% over). Recorded
as the slimming acceptance target; the pointer-matched replay
still judges peak live sectors separately.

CORRECTION (2026-11-03 evening, on receipt and inspection of
the file itself): the boot trace is NOT zero-to-login. Its own
header reads entries-in-buffer/entries-written:
322338/1734733, and its first event is timestamped 4.145614 s
(systemd-udevd already running), its last 49.936 s (login).
The ring buffer wrapped: about 1.41M events from the boot's
first ~4.1 s were overwritten. All four event counts in the
file match the in-guest greps exactly, and the statistics
computed from it (151486 allocs, sum_req 155841190, histogram,
free counts) are exact for the RETAINED WINDOW, t=4.15 s to
login, and only for that window. The "dropped events: 0" check
was the wrong field: in overwrite mode, wraps are counted as
overrun, not dropped events. The earlier "exact zero-to-login"
statements in this sheet are superseded by this paragraph.
Remedy: at the 512 MiB diagnostic seat, the retained density
(322338 events in a 16 MiB buffer, about 52 bytes per event)
implies the full 1734733 written events need roughly 90 MB;
trace_buf_size=128M is the rerun setting, verified by BOTH
the file header (written == in-buffer) and the overrun field.
File of record: traces/telezart-trace-boot.txt, SHA-256
2b767249c3f44783d40bb1f47677dbf5279dd5bc646fe45683c228370026e7f8;
the .gz as received hashes to
245e060eb1de7a5e4d13a0b5c60c502167a90e4d3cd66ccd90aa2296adc2328b.

WINDOW LEDGER, pointer-matched by Muse from the received
trace (2026-11-03, bytes_req basis): total allocations
148.62 MiB (151486 events, 155841190 bytes); total frees
matched to in-window allocations 145.36 MiB (136779 events,
152418403 bytes); difference 3.26 MiB (3422787 bytes). The
set actually live at login measures 2.76 MiB in 14169 objects;
the roughly 0.50 MiB gap is allocation instances whose
pointers were reused without a traced free in between.
Another 34073 frees retired pre-window objects whose bytes
this file cannot know. Andrew's plan: a live-fire exercise in
the next couple of days (the full zero-to-login rerun at
trace_buf_size=128M) to replace these window figures with
whole-boot ones.

FUBUKI OCCUPANCY AFTER THE CHURN (from counters-after.txt
meminfo, read by Andrew 2026-11-03; the 512 MiB boot):
MemTotal 475236 kB (464.1 MiB); MemFree 314760 kB;
MemAvailable 397544 kB; Cached 83940 kB; Slab 20860 kB
(SReclaimable 6812, SUnreclaim 14048). Computed: strict
occupancy MemTotal-MemFree = 160476 kB = 156.7 MiB (33.8%);
practical occupancy MemTotal-MemAvailable = 77692 kB =
75.9 MiB (16.3%). Against the kmalloc trace difference of
3.26 MiB, true occupancy is roughly 23x larger on the
practical measure: page cache (82.0 MiB, reclaimable) and
slab retention (20.4 MiB, of which 13.7 MiB unreclaimable)
carry most of the difference, exactly the layers the kmem
trace does not see.

TEST ONE CONFIGURATION, settled by Andrew (2026-11-03): test
Iscandar AS IS (k=3, unmodified) at a 4 KiB sector, one cube =
128 MiB arena, "and win." Grounds: Fubuki's static dynamic
memory after all frees is 75.9 MiB (MemTotal minus
MemAvailable), well inside one cube; the window replay's peak
live set was 14,539 objects against the cube's 32,768 slots,
and at a 4 KiB sector each live object rents at least one
sector, so peak live sectors sit near half the cube with
largest-fit room to spare; the boot's largest request
(177,418 bytes) is 44 sectors at 4 KiB, ordinary Large-mode
work. The live-fire rerun's job is to confirm the lost first
seconds hide no live-object peak above 32,768.

LIVE-FIRE PROTOCOL (ordered by Andrew 2026-11-03: the complete
list of allocates and frees, tonight or tomorrow, with scripted
on/off if needed): (1) Boot the armed line at the 512 MiB seat
with trace_buf_size=128M (measured need is roughly 90 MB for
the boot's roughly 1.73M events). (2) OFF is automated in the
revised fubuki.xml by telezart-autostop.service, which runs
telezart-stop as multi-user.target is reached; on the current
already-built image, telezart-stop by hand at the login prompt
is the same act. (3) Verify completeness TWO ways before
believing any total: the dump's own header must show
entries-written == entries-in-buffer, and per_cpu stats must
show overrun 0 (dropped events is NOT the wrap counter).
(4) poweroff, extract by losetup read-only mount as before,
hash (SHA-256) into the manifest, gzip across to Muse.

EXPORT WITHOUT MOUNTING (Andrew's order, 2026-11-03: mounting
and unmounting the disk image "is for the birds"; the stats
are to be counted and stored back in the telesart folder):
the revised fubuki.xml adds telezart-stats (an awk ledger over
the boot trace: counts by event, totals, matched frees,
difference, peak live, live at end, histogram, P20/P50/P80;
its output was verified line-for-line against Muse's
independent Python count of the 2026-11-03 window trace) and
telezart-finish (autostop now runs stop, then stats, then
exports trace, stats, counters, and kpageflags scans through
a QEMU 9p share into ~/telezart/share on the host). Host prep
is one mkdir; the live-fire boot line gains:
-virtfs local,path=/home/andrew/telezart/share,mount_tag=tzshare,security_model=mapped-xattr
No losetup, no image mounting, anywhere in the loop.

REVISED BUILD RECORD (2026-11-03): ELBE build folder
/home/andrew/telezart/elbe-build-20261103-204902 completed and
generated fubuki.img.tar.xz plus telezart-vmlinuz,
telezart-initrd, and telezart-kconfig. This is the build
carrying telezart-autostop, telezart-stats, and telezart-finish.

LIVE-FIRE RESULT (2026-11-03): overrun 0, commit overrun 0:
the zero-to-login capture is complete. Allocations 812,106;
gross requests 383.69 MiB; matched frees 754,350 (364.31 MiB);
unmatched frees 83,968 (born before the trace armed);
difference 19.38 MiB; peak live 13.38 MiB in 56,023 objects;
live at login 12.68 MiB in 56,020 objects; P20/P50/P80 request
sizes 72/80/184 bytes; max request 996,600 bytes. Consequence:
56,023 live objects exceed one k=3 cube's 32,768 sectors at
any sector size (minimum one sector per allocation), so the
k=3-at-4-KiB Test One configuration fails the object-level
list. The open ruling: k=4 for the object list, or k=3 at the
page level. Muse's earlier ~0.9 GB gross approximation was
high by roughly 2.4x and is superseded by this measurement.

LOCALITY, MEASURED (2026-11-03, from the complete trace):
lifetimes of 756,086 matched pairs: median 7 microseconds;
79.5% freed within 100 us, 83.4% within 1 ms, 97.7% within
100 ms, 98.6% within 1 s; 96.8% of freed bytes freed within
100 ms. Survivors at login readiness: 56,020 objects /
12.68 MiB (about 6.9% of allocations): the standing set.
Andrew's framing: if locality holds, memory use should
vanish shortly after held. It does, for the traffic; what
remains is the furniture.
