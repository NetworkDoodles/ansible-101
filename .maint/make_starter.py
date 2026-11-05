#!/usr/bin/env python3
"""Maintainers only: turn the solution files into the starter files learners get on main.

Solution code sits between marker lines:

    # >>> solution | <optional starter line>
    ...finished code...
    # <<< solution

On main, each block becomes the starter line if one is given, otherwise
`raise NotImplementedError("TODO x.ya is still open")` for Python, or nothing for YAML.

    python .maint/make_starter.py <solution checkout> <starter checkout>
"""
import re
import sys
import pathlib

FILES = [
    "playbooks/foundation.yml", "playbooks/device.yml", "playbooks/config_contexts.yml",
    "intent/devices.yml", "playbooks/render.yml", "tools/drift.py", "tools/compile.py",
    "tools/diff_rules.py", "tools/schema_check.py", ".gitlab-ci.yml",
]
OPEN = re.compile(r"^(\s*)# >>> solution(?: \| (.*))?$")
CLOSE = re.compile(r"^\s*# <<< solution$")


def strip(text, yaml_file):
    out, todo, skipping = [], "TODO", False
    for line in text.splitlines():
        if m := re.match(r"\s*# (TODO \d+\.\d+[a-z]?)", line):
            todo = m.group(1)
        if skipping:
            skipping = not CLOSE.match(line)
            continue
        if m := OPEN.match(line):
            indent, starter = m.groups()
            if starter:
                out.append(indent + starter)
            elif not yaml_file:
                out.append(f'{indent}raise NotImplementedError("{todo} is still open")')
            skipping = True
            continue
        out.append(line)
    return "\n".join(out) + "\n"


src, dst = (pathlib.Path(p) for p in sys.argv[1:3])
for f in FILES:
    (dst / f).write_text(strip((src / f).read_text(), f.endswith((".yml", ".yaml"))))
    print("starter:", f)
