"""make status · what's installed, what's running, and where to start.

The dev container runs this when the folder opens. It only reads: package versions, docker ps, one
`show version` per switch. Safe to run any time.
"""
import os
import re
import shutil
import subprocess
import sys
import time
import pathlib
from importlib import metadata

sys.path.insert(0, pathlib.Path(__file__).resolve().parents[1].as_posix())
from lib.bolt import Bolt, SWITCHES  # noqa: E402

GUIDE = "https://networkdoodles.com/labs/ansible-101"
TTY = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
G, R, Y, C, D, B, X = (("\033[32m", "\033[31m", "\033[33m", "\033[36m", "\033[2m", "\033[1m", "\033[0m")
                       if TTY else ("",) * 7)


def sh(*cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return (p.stdout + p.stderr).strip() if p.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def row(ok, name, value, fix=""):
    mark = f"{G}✓{X}" if ok else (f"{Y}·{X}" if ok is None else f"{R}✗{X}")
    print(f"  {mark} {name:<20} {value if ok else (D + fix + X if fix else value)}")


def version(name):
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


print(f"\n{B}{C}  Network Doodles lab · Ansible 101 for networking{X}\n")
print(f"{D}  tools{X}")
row(True, "python", sys.version.split()[0])
for pkg in ("ansible-core", "ansible-lint", "ansible-navigator"):
    v = version(pkg)
    row(bool(v), pkg, v, "not installed: make setup")
out = sh(str(pathlib.Path(sys.executable).parent / "ansible-galaxy"), "collection", "list", "cisco.ios")
m = re.search(r"cisco\.ios\s+(\S+)", out or "")
row(bool(m), "cisco.ios", m.group(1) if m else "", "not installed: make setup")
v = sh("docker", "version", "--format", "{{.Server.Version}}")
row(bool(v), "docker", v, "not answering")
m = re.search(r'"version":\s*"([^"]+)"', sh("containerlab", "version", "--json") or "") if shutil.which("containerlab") else None
row(bool(m), "containerlab", m.group(1) if m else "", "not found: it comes with the dev container")


def answering():
    up = {}
    for sw in SWITCHES:
        try:
            v = Bolt(sw, timeout=6).version()[0]
            if v:
                up[sw] = v
        except Exception:
            pass
    return up


print(f"\n{D}  running{X}")
up = answering()
if len(up) < len(SWITCHES) and "--wait" in sys.argv:
    # The folder-open task can run before the dev container has started the switches.
    print(f"  {Y}·{X} the switches are starting: a few seconds", flush=True)
    deadline = time.time() + 10 * 60
    while len(up) < len(SWITCHES) and time.time() < deadline:
        time.sleep(10)
        up = answering()
for sw in SWITCHES:
    row(bool(up.get(sw)), sw, f"CapeOS Bolt {up.get(sw)}", "not answering: make up")

print(f"\n{D}  next{X}")
print(f"  guide     {GUIDE}/")
print(f"  basics    {GUIDE.rsplit('/', 1)[0]}/basics/   (new to VS Code, the terminal or Ansible? start here)")
print(f"  commands  make help\n")
