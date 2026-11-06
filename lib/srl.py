"""A tiny SR Linux JSON-RPC client for the checker and the status script.

The checker reads the switches the same way Ansible's nokia.srlinux collection does (JSON-RPC over
HTTPS), but without Ansible, so a broken playbook can't hide a broken check.
"""
import pathlib
import warnings

import requests
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
SWITCHES = ["spine1", "leaf1", "leaf2"]
# containerlab's SR Linux defaults; chapter 7 moves the password the playbooks use into a vault.
USER, PASSWORD = "admin", "NokiaSrl1!"
warnings.filterwarnings("ignore", message="Unverified HTTPS request")


class SRL:
    def __init__(self, host, timeout=10):
        self.url = f"https://{host}/jsonrpc"
        self.timeout = timeout

    def _call(self, method, params):
        body = {"jsonrpc": "2.0", "id": 0, "method": method, "params": params}
        r = requests.post(self.url, json=body, auth=(USER, PASSWORD), verify=False, timeout=self.timeout)
        r.raise_for_status()
        out = r.json()
        if "error" in out:
            raise RuntimeError(out["error"].get("message", out["error"]))
        return out["result"]

    def get(self, path, datastore="running"):
        """The value at a YANG path, or None if nothing is configured there."""
        try:
            value = self._call("get", {"commands": [{"path": path, "datastore": datastore}]})[0]
            return None if value == {} else value  # an unset leaf comes back as {}
        except RuntimeError as e:
            if "not found" in str(e).lower() or "no data" in str(e).lower():
                return None
            raise

    def set(self, commands):
        """One transaction: a list of {"action": "update"|"replace"|"delete", "path": ..., "value": ...}."""
        return self._call("set", {"commands": commands})

    def delete(self, path):
        """Remove the config at a path (the checker uses this to make a handler fire)."""
        return self._call("set", {"commands": [{"action": "delete", "path": path}]})

    def cli(self, *commands):
        return self._call("cli", {"commands": list(commands), "output-format": "text"})


def load(path):
    """Load a YAML file relative to the repo root (None if it doesn't exist)."""
    p = ROOT / path
    return yaml.safe_load(p.read_text()) if p.exists() else None
