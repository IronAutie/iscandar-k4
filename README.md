# Iscandar k=4: the Beam, and the Debian replay experiment

Companion repository to [iscandar](https://github.com/IronAutie/iscandar),
which holds the k=3 allocator and the monograph. This repository holds the
k=4 composition (cubes composed into beams under a rotary rule) and the
complete replication package for the paper "Iscandar Revisited: Expansion
to k=4 Theory For Running Debian": the allocation trace of a real Debian
boot, the reducer that turns it into a replay stream, the Beam and buddy
replay drivers, and the scripts that regenerate the paper's memory maps.

## Layout

- `Beam.py`, `BeamCoordinate.py`, `CPUPointer.py`: the k=4 code. A Beam
  offers the first cube that accepts a request, walking its cubes in a
  rotary order. A fit never crosses a cube wall.
- `test/reducer.py`: converts a kernel trace into the replay stream
  (one allocation or free per line).
- `test/test_driver.py`: replays the stream through the Beam and writes a
  sampled series of live sectors, live objects, and largest possible fit
  remaining (LPFR).
- `test/buddy_replay.py`: the control. Replays the same stream through a
  lowest-address first-fit buddy allocator and writes the same series.
- `test/beam_stress_stop.py`, `test/buddy_stress_scan.py`: stop either
  replay at a chosen stream event and dump the allocator state there.
- `data/`: the captured trace (gzipped), the reduced stream, and the
  reference series the paper's figures were drawn from.
- `fubuki/`: the ELBE project file that builds the test system (Fubuki,
  Debian 13 trixie), the install and build sheets used, and two guest-side
  analysis tools.
- `figures/`: the state dumps and render scripts for the paper's memory
  maps, including the joined beam maps that share the buddy maps' canvas.

## Setup

Clone both repositories side by side under their default names. The k=4
code locates the k=3 engine at `../iscandar` relative to this repo.

```sh
git clone https://github.com/IronAutie/iscandar
git clone https://github.com/IronAutie/iscandar-k4
```

Build the k=3 engine first (its setup script builds the gear library the
engine loads), and install the one third-party Python package it needs:

```sh
cd iscandar && ./iscandar-linux-setup.sh && cd ..
python3 -m pip install bitstruct
```

## The experiment end to end

### 1. Install ELBE and QEMU (Debian or Debian-based host)

```sh
sudo apt update
sudo apt install -y extrepo qemu-kvm libvirt-daemon-system \
    libvirt-clients qemu-utils p7zip-full
sudo extrepo enable elbe
sudo apt update
sudo apt install -y elbe
elbe --version          # 15.9 was used for the paper
sudo adduser $USER libvirt-qemu
```

Create the ELBE initvm once, following `fubuki/elbe-install-sheet-2026-11-02.md`.

### 2. Build Fubuki

```sh
elbe initvm submit fubuki/fubuki.xml
```

The build produces `telezart-vmlinuz`, `telezart-initrd`,
`telezart-kconfig`, and `fubuki.img`. The XML carries a guest service
that stops the capture at multi-user readiness and exports the trace and
counters through a QEMU 9p share, so no image mounting is needed anywhere
in the loop. Details and the full record are in
`fubuki/fubuki-build-and-boot-sheet.md`.

### 3. Boot under QEMU and capture the trace

```sh
mkdir -p ~/telezart/share
qemu-system-x86_64 -m 512 -enable-kvm -cpu host \
  -kernel telezart-vmlinuz -initrd telezart-initrd \
  -append "root=LABEL=rfs console=ttyS0 nomodeset trace_buf_size=16M trace_event=kmem:kmalloc,kmem:kmalloc_node,kmem:kmem_cache_alloc,kmem:kmem_cache_alloc_node,kmem:kfree,kmem:kmem_cache_free" \
  -drive format=raw,file=fubuki.img,if=virtio \
  -virtfs local,path=$HOME/telezart/share,mount_tag=tzshare,security_model=mapped-xattr \
  -vga none -nographic
```

The kernel arms the kmem tracepoints from t=0, so the capture covers the
boot from the first allocation to the login prompt. The 512 MiB size is
the capture seat: the stock trixie initramfs cannot unpack in 128 MiB.
A complete capture reports dropped events 0. The bundled capture
(`data/telezart-trace-boot-complete-2026-11-03.txt.gz`) contains
1,650,424 events: 812,106 allocations requesting 402,331,163 bytes, peak
live 14,028,570 bytes in 56,023 objects, 56,020 objects live at the end.

SHA-256 of the trace as captured (uncompressed):
`1ba9a4a725d0fa924de9ed97576d77a5dba001f545c1b77da06fef823dfa76a6`
SHA-256 of the bundled gzip: `8b2a07f7926585c5bdaf28e3ea2da456a36c16222729478f53bcef28122d06d2`

### 4. Reduce the trace to the replay stream

```sh
zcat data/telezart-trace-boot-complete-2026-11-03.txt.gz > trace.txt
python3 test/reducer.py trace.txt stream.csv
```

The bundled `data/stream.csv` is this output (1,650,424 lines,
SHA-256 `a901af25ecd9d9692443bd4fc2c1005cf6efa84c8a0095a6baa29b7d1c4e36c4`).
Frees of pointers born before the trace armed appear in the stream as
unknown frees. Both replay drivers apply the same policy to them and to
reborn pointers: a reborn pointer frees its old block first, and an
unknown free is counted and skipped.

### 5. Replay

Beam, first configuration (4 cubes, 4 KiB grain, 512 MiB arena):

```sh
python3 test/test_driver.py data/stream.csv series-beam-new.csv 1000 4096 4
```

Buddy control, same arena:

```sh
python3 test/buddy_replay.py data/stream.csv series-buddy-new.csv 1000 4096 131072
```

Expected results, matching the paper: the Beam refuses nothing and peaks
at 56,535 live sectors in 56,023 objects; the buddy peaks at 56,599
granted pages, 64 pages (0.11 percent) above the Beam. Reference series
from the original runs are `data/series-honest.csv` (Beam) and
`data/series-buddy.csv` (buddy).

Second configuration (2 KiB grain): Beam with 8 cubes,
`test_driver.py ... 1000 2048 8` peaks at 57,336 sectors; the buddy
(`buddy_replay.py ... 1000 2048`, arena pages follow from the grain)
peaks at 57,486 pages. Reference series: `data/series-beam-2k.csv`,
`data/series-buddy-2k.csv`.

Halved arena (256 MiB) stress test: Beam with 2 cubes,
`test_driver.py ... 1000 4096 2` still refuses nothing, with LPFR falling
to a minimum of 970 sectors; the buddy (`buddy_replay.py ... 1000 4096
65536`) holds an LPFR floor of 8,192 pages. Reference series:
`data/series-beam-256.csv`, `data/series-buddy-256.csv`.

### 6. Stress stops and figures

The three instants the paper maps: the crest at event 1,106,000, the
bottom of the fall (fragmentation peak) at event 1,133,798, and the
fullness peak at event 1,650,412.

```sh
python3 test/beam_stress_stop.py data/stream.csv 1133798 4096 2
python3 test/buddy_stress_scan.py data/stream.csv --stop 1133798
```

The state dumps in `figures/` are the stopped states at those instants.
`figures/render_maps.py` draws the paper's bordered maps;
`figures/render_beam_joined.py` draws the beam maps as single joined
grids on the buddy maps' canvas (cube 0 in the top half, cube 1 in the
bottom half, the cube wall marked only at the frame edges).

## Authorship

The allocator design, the k=4 theory, and the mathematics are the
author's. AI assistance was used under the author's direction for
transcription, harness code, verification, and figure generation, as the
paper's acknowledgements state.
