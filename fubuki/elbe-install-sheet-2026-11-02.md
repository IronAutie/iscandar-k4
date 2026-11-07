# Telezart: ELBE install sheet for telesart

Mechanic's sheet, prepared 2026-11-02. Andrew runs each step at the CIC;
stop anywhere; report what the screen says and we adjust.
Upstream reference: ELBE 15.9 Quickstart (elbe-rfs.org). ELBE is a pinned
tool, installed from the Linutronix repository. Nothing of ELBE goes into
the Telezart repo; our XML and scripts are ours.

## Step 0: confirm the bench can virtualize (one command)

```
ls -la /dev/kvm
```

Expect a device line (crw-rw---- root kvm ...). If it is missing, stop:
virtualization is likely off in the BIOS setup, and we enable it there
before anything else. Also confirm elbow room:

```
df -h ~
```

Expect tens of GB free on the 500 GB SSD. Fine as installed.

## Step 1: host prerequisites

```
sudo apt update
sudo apt install -y extrepo qemu-kvm libvirt-daemon-system libvirt-clients qemu-utils p7zip-full
```

Note on the host: upstream tests ELBE on Debian 12 (bookworm) or later.
Telesart runs Mint 22.3 (Ubuntu 24.04 family). The ELBE packages are
Python and the initvm is a Debian VM under KVM, so the straightforward
route is worth trying first. If package resolution fights us, the
fallback is a Debian host VM on telesart with KVM passed through; we
do not fight the package manager past one honest attempt.

## Step 2: enable the ELBE repository and install

```
sudo extrepo enable elbe
sudo apt update
sudo apt install -y elbe
elbe --version
```

Write the printed version into this sheet when it lands. That pinned
version goes in the Telezart manifest later; reproducibility is part
of the evidence.

Manual fallback if extrepo fails (from the ELBE 15.9 Quickstart):

```
sudo apt install -y elbe-archive-keyring || wget -O /usr/share/keyrings/elbe-archive-keyring.gpg http://debian.linutronix.de/elbe/elbe-repo.pub.gpg
echo "deb [signed-by=/usr/share/keyrings/elbe-archive-keyring.gpg] http://debian.linutronix.de/elbe bookworm main" | sudo tee /etc/apt/sources.list.d/elbe.list
sudo apt update
sudo apt install -y elbe
```

## Step 3: groups, then log out and back in

```
sudo adduser andrew libvirt
sudo adduser andrew libvirt-qemu
```

Group membership needs a fresh login to take effect.

## Step 4: create the initvm (one-time; downloads a Debian installer, quiet but slow)

```
mkdir -p ~/telezart
cd ~/telezart
elbe initvm create --directory ~/telezart/initvm --devel examples/x86_64-pc-rescue-busybox-dyn-cpio.xml
```

If the packaged example path differs on 15.9, stop and read the
examples directory together; do not improvise paths. A successful
create ends with the initvm reachable on localhost port 7587.

## Step 5: smoke test with the packaged rescue example

```
elbe initvm submit examples/x86_64-pc-rescue-busybox-dyn-cpio.xml
```

A finished build directory with an image is the pass mark. Only after
this do we author the Telezart XML (128 MiB target, systemd, tracing
packages) as the next sheet.

## Version pin record

- ELBE version: 15.9 (installed 2026-11-02 via extrepo on Mint, no package fight)
- Host: telesart, Linux Mint 22.3; /dev/kvm present; 410 GB free on /dev/sda2
- Date installed: 2026-11-02

## Resume point: 2026-11-02 evening session (stopped cleanly, nothing running)

Session ran about an hour and stopped at Andrew's call because Jennifer
needed him. Nothing is half-written or running on telesart; resume
from steps R2 and R3 below.

What was established, in order:

- DisplayLink: the large display was out and the desktop was very slow.
  No displaylink systemd unit exists on telesart ("Unit displaylink not
  found"). Unplugging the DisplayLink adapter restored normal speed, so
  the DisplayLink stack, not ELBE and not the bench, was the drag.
  DisplayLink repair is a separate job for another sitting.
- Step 4 correction: the elbe package ships no example XML files at all
  (`dpkg -L elbe | grep xml` returned nothing, and
  /usr/share/elbe/examples does not exist). The genuine ELBE rescue
  example, x86_64-pc-rescue-busybox-dyn-cpio.xml (Debian trixie), was
  fetched from ELBE's own repository and saved into ~/telezart on
  telesart. A copy also sits beside this sheet.
- Initvm create reached the Debian installer kernel download, then
  failed: "Failure to download kernel/initrd debian Package / Check
  Mirror configuration". The output showed "Signature with unknown key"
  for the Debian signatures.
- Mirror check acquitted the network: `curl -I
  http://deb.debian.org/debian/dists/trixie/Release` answered
  HTTP/1.1 200 OK from telesart.
- Diagnosis, read from ELBE's own source
  (/usr/lib/python3/dist-packages/elbepack/init/__init__.py,
  copy_kinitrd failure path): ELBE verifies the Debian Release using
  keys from /etc/apt/trusted.gpg.d. Listing that folder showed only
  Mint and Ubuntu keys (linuxmint.key.asc, linuxmint-keyring.gpg,
  ubuntu-keyring-2012-cdimage.gpg, ubuntu-keyring-2016-dbgsym.gpg,
  ubuntu-keyring-2018-archive.gpg). No Debian key is there, which is
  why every Debian signature read as unknown.

Resume steps, in order, when Andrew chooses:

- R1. If the cp in R2 errors that its source file does not exist, the
  debian-archive-keyring package never landed; install it first with
  `sudo apt install -y debian-archive-keyring`, then repeat R2.
- R2. Copy the Debian key where ELBE looks:
  `sudo cp /usr/share/keyrings/debian-archive-keyring.gpg /etc/apt/trusted.gpg.d/`
- R3. Clear the stale partial initvm (ELBE refuses to build over it,
  FileExistsError on .elbe-in) and rerun:
  `rm -rf ~/telezart/initvm`, then from ~/telezart:
  `elbe initvm create --directory ~/telezart/initvm x86_64-pc-rescue-busybox-dyn-cpio.xml`

Amendment, 2026-11-03 morning: R2 was run and worked only partway. The
bookworm archive key in the Mint-packaged debian-archive-keyring now
reads VALID (Untrusted), but the create still fails because the
trixie Release file carries three signatures and ELBE fails if any
one key is missing. The two unknown fingerprints are the new 2025
Debian 13 keys, which predate nothing: they were generated
2025-03-30 and are absent from the old keyring package Mint ships.
Verified on Muse's side from the official Debian key directory:
B8E5F13176D2A7A75220028078DBA3BC47EF2265 is the signing subkey of
archive-key-13.asc (SHA256 of that file:
6f1d277429dd7ffedcc6f8688a7ad9a458859b1139ffa026d1eeaadcbffb0da7,
matching Debian's own announcement), and
41587F7DB8C774BCCF131416762F67A0B2C39DE4 is release-13.asc itself,
the Debian Stable Release Key (13/trixie). Fix: fetch both files
from https://ftp-master.debian.org/keys/ into
/etc/apt/trusted.gpg.d/ as .asc files, then repeat R3.

Last note, confirmed 2026-11-02 evening after stopping: Andrew reported
that plugging in an LVDT port kicked open the DP driver, and then
confirmed the big screen stayed lit and fast for the last 5 commands.
The bench ended the night whole on that display path. If that display
ever sulks after a login again, the first remedy is a replug to give
the driver its hotplug knock, before any deeper surgery. The separate
DisplayLink drag finding above still stands as its own job.

Resolution, 2026-11-03: the key fix above worked. `elbe initvm create`
completed; the initvm listens on localhost port 7587 (verified with
`ss -ltn`). The upstream rescue example's submit then failed in its own
finetuning at `ln -sf /sbin/init /init` (chroot returned 127: no working
`ln` inside the bare busybox target at that step). A patched copy of the
example, x86_64-pc-rescue-busybox-dyn-cpio-patched.xml (in this folder),
replaces the <ln> action with a busybox raw_cmd and moves the rcS mode
setting to a busybox chmod raw_cmd. With that patch the submit ran
clean: "Package List validation: No Errors found", files saved to
/home/andrew/elbe-build-20261103-114739 on telesart, rescue.cpio image
present. Smoke test PASSED. Next: author the Telezart target XML
(128 MiB, systemd, tracing packages). Andrew named his own build
"Fubuki" (2026-11-03).

## Corrective steps, consolidated (what actually worked, in order)

For a fresh Mint host, after Steps 0-3, do these instead of plain
Step 4; every step below was needed and verified on telesart:

- C1. Give ELBE the Debian keys it looks for. ELBE verifies the Debian
  Release signature using ONLY files in /etc/apt/trusted.gpg.d, and it
  fails if ANY signature on the Release file lacks a key there. The
  Mint-packaged debian-archive-keyring alone is not enough for trixie:
  it has the bookworm key but not Debian 13's two 2025 keys. Run:
  `sudo cp /usr/share/keyrings/debian-archive-keyring.gpg /etc/apt/trusted.gpg.d/`
  `sudo curl -fsSL https://ftp-master.debian.org/keys/archive-key-13.asc -o /etc/apt/trusted.gpg.d/debian-archive-key-13.asc`
  `sudo curl -fsSL https://ftp-master.debian.org/keys/release-13.asc -o /etc/apt/trusted.gpg.d/debian-release-key-13.asc`
- C2. Clear any stale partial initvm and create from inside ~/telezart
  (ELBE refuses to build over a leftover initvm):
  `rm -rf ~/telezart/initvm`
  `cd ~/telezart && elbe initvm create --directory ~/telezart/initvm x86_64-pc-rescue-busybox-dyn-cpio.xml`
- C3. Verify the initvm is up before submitting; the create command
  exiting is normal, the daemon must be listening:
  `ss -ltn | grep 7587` (a LISTEN line is the pass mark).
- C4. Submit by ABSOLUTE path. With a bare filename, elbe fails with
  "RepodirError ... failed to load external entity" whenever the
  terminal is standing in any other directory:
  `elbe initvm submit /home/andrew/telezart/x86_64-pc-rescue-busybox-dyn-cpio-patched.xml`
- C5. Use the PATCHED example for the smoke test, not the upstream one.
  The upstream example's finetuning calls chroot `ln` and `chmod`,
  which return 127 in the bare busybox target under ELBE 15.9. The
  patched copy (kept beside this sheet) makes two changes only:
  the <ln path="/sbin/init">/init</ln> action becomes
  <raw_cmd>/usr/bin/busybox ln -sf /sbin/init /init</raw_cmd>, and the
  rcS <file> drops its mode="755" attribute and gains a following
  <raw_cmd>/usr/bin/busybox chmod 755 /etc/init.d/rcS</raw_cmd>.
- C6. Pass mark: "Package List validation: No Errors found" and a
  saved elbe-build-<timestamp> folder containing rescue.cpio.

Telezart target decisions, 2026-11-03: QEMU hands the kernel in via
its -kernel flag (Andrew's decision); the ELBE-built rootfs carries no
kernel, so the kernel version stays a separate pinned piece of
evidence. No kernel or Debian source is marked up or patched for
profiling (confirmed in discussion 2026-11-03): the experiment runs
the stock buddy allocator, and the capture uses the kernel's own
built-in kmem tracepoints (mm_page_alloc / mm_page_free) through
tracefs, plus /proc counters. A patched kernel would invalidate the
numbers as evidence about the stock system.
