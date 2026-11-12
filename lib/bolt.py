"""A tiny client for the lab's CapeOS Bolt switches, for the checker and the status script.

It runs CLI commands with `docker exec <switch> capeos-cli`, not through Ansible, so a broken playbook
can't hide a broken check. And it reads `show running-config` the way you would: section by section.
"""
import pathlib
import re
import subprocess

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
SWITCHES = ["spine1", "leaf1", "leaf2"]
# The lab login, set in lab/fabric.clab.yml. Chapter 7 moves the copy the playbooks use into a vault.
USER, PASSWORD = "admin", "capeos-lab"
ERROR = re.compile(r"^% (Invalid|Incomplete|Ambiguous|Unknown)", re.M)


class Bolt:
    def __init__(self, host, timeout=20):
        self.host = host
        self.timeout = timeout

    def cli(self, *commands):
        """Run exec-mode commands in one CLI session; returns everything it printed."""
        p = subprocess.run(["docker", "exec", "-i", self.host, "capeos-cli"], input="\n".join(commands) + "\n",
                           capture_output=True, text=True, timeout=self.timeout)
        if p.returncode != 0 and not p.stdout:
            raise RuntimeError(p.stderr.strip() or f"{self.host} isn't running")
        return p.stdout

    def show(self, command):
        """One show command's output, without the prompts the CLI echoes around it."""
        out = self.cli("terminal length 0", command)
        lines = [ln for ln in out.splitlines() if not re.match(rf"^{re.escape(self.host)}[#>]\s*$", ln)]
        text = "\n".join(lines)
        # Strip the prompt the CLI prints in front of the command's first line of output.
        return re.sub(rf"^{re.escape(self.host)}[#>]", "", text, flags=re.M).strip()

    def configure(self, *lines):
        """Config-mode lines, as you'd type them after `configure terminal`."""
        out = self.cli("configure terminal", *lines, "end")
        if ERROR.search(out):
            raise RuntimeError(f"{self.host} rejected: {' / '.join(lines)}")
        return out

    def running(self):
        return Running(self.show("show running-config"))

    def startup(self):
        p = subprocess.run(["docker", "exec", self.host, "cat", "/flash/startup-config"],
                           capture_output=True, text=True, timeout=self.timeout)
        return Running(p.stdout)

    def version(self):
        """(software version, serial number) from `show version`."""
        out = self.show("show version")
        v = re.search(r"Version (\S+?),", out)
        s = re.search(r"Processor board ID (\S+)", out)
        return (v.group(1) if v else None), (s.group(1) if s else None)


class Running:
    """A running (or startup) config, with the questions the checker asks of it."""

    def __init__(self, text):
        self.text = text or ""

    def line(self, pattern):
        """The rest of the first top-level line that starts with `pattern`, or None."""
        m = re.search(rf"^{re.escape(pattern)} ?(.*)$", self.text, re.M)
        return m.group(1).strip() if m else None

    def lines(self, pattern):
        return [m.strip() for m in re.findall(rf"^{re.escape(pattern)} ?(.*)$", self.text, re.M)]

    def banner(self, kind):
        """A banner's text: `banner motd ^C` ... `^C`."""
        m = re.search(rf"^banner {kind} \^C\n(.*?)\n?\^C", self.text, re.M | re.S)
        return m.group(1) if m else None

    def interface(self, name):
        """The lines under `interface <name>`, without their indent."""
        m = re.search(rf"^interface {re.escape(name)}\n((?: .*\n?)*)", self.text, re.M)
        return [ln.strip() for ln in m.group(1).splitlines()] if m else []

    def port(self, name):
        """description, enabled, mtu for one port."""
        body = self.interface(name)
        desc = next((ln[len("description "):] for ln in body if ln.startswith("description ")), None)
        mtu = next((int(ln.split()[1]) for ln in body if ln.startswith("mtu ")), 1500)
        return {"description": desc, "enabled": "shutdown" not in body, "mtu": mtu}


class _Loader(yaml.SafeLoader):
    """safe_load, plus Ansible's !vault tag: from chapter 7 on, a value can be encrypted inline. The checks never
    need its contents, so it loads as the text "<vaulted>"."""


_Loader.add_constructor("!vault", lambda loader, node: "<vaulted>")


def load(path):
    """Load a YAML file relative to the repo root (None if it doesn't exist)."""
    p = ROOT / path
    return yaml.load(p.read_text(), Loader=_Loader) if p.exists() else None
