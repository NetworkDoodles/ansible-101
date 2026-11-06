"""Wait until every switch has booted and answers SSH, then print how to reach them."""
import socket
import subprocess
import sys
import time
import pathlib

sys.path.insert(0, pathlib.Path(__file__).resolve().parents[1].as_posix())
from lib.bolt import SWITCHES  # noqa: E402


def ready(sw):
    # CapeOS creates /run/capeos/ready once its startup config is applied; Ansible then needs SSH.
    booted = subprocess.run(["docker", "exec", sw, "test", "-f", "/run/capeos/ready"], capture_output=True).returncode == 0
    if not booted:
        return False
    try:
        socket.create_connection((sw, 22), timeout=3).close()
        return True
    except OSError:
        return False


deadline = time.time() + 120
pending = list(SWITCHES)
while pending:
    pending = [sw for sw in pending if not ready(sw)]
    if pending:
        if time.time() > deadline:
            sys.exit(f"these switches didn't come up in 2 minutes: {', '.join(pending)}   (docker logs {pending[0]} says why)")
        print(f"  waiting for {', '.join(pending)} ...", flush=True)
        time.sleep(2)
print("\n  switches are up: spine1, leaf1, leaf2   (make ssh NODE=leaf1 for a CLI)\n")
