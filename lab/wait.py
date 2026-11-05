"""Wait for every switch's API to answer, then print how to reach them."""
import sys
import time
import pathlib

sys.path.insert(0, pathlib.Path(__file__).resolve().parents[1].as_posix())
from lib.srl import SRL, SWITCHES  # noqa: E402

deadline = time.time() + 300
pending = list(SWITCHES)
while pending:
    for sw in list(pending):
        try:
            SRL(sw, timeout=5).get("/system/information/version", "state")
            pending.remove(sw)
        except Exception:
            pass
    if pending:
        if time.time() > deadline:
            sys.exit(f"these switches didn't answer in 5 minutes: {', '.join(pending)}")
        print(f"  waiting for {', '.join(pending)} ...", flush=True)
        time.sleep(5)
print("\n  switches are up: spine1, leaf1, leaf2   (make ssh NODE=leaf1 for a CLI)\n")
