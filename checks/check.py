"""make check T=2.1 · CH=2 · (nothing)  ·  verifies a task, a chapter or the whole lab.

Every check reads real state: the switches through their JSON-RPC API (not through Ansible, so a broken
playbook can't hide a broken check), the files you wrote, and the output of your playbooks. The only
checks that change anything re-run a playbook that should change nothing the second time.

    python checks/check.py 2.1          one task
    python checks/check.py ch2          one chapter
    python checks/check.py all          everything, with progress
    python checks/check.py --files 2.1  the files task 2.1 asks you to edit (make solve uses this)
"""
import json
import os
import re
import subprocess
import sys
import pathlib

sys.path.insert(0, pathlib.Path(__file__).resolve().parents[1].as_posix())
from lib.srl import ROOT, SRL, SWITCHES, PASSWORD, load  # noqa: E402

GUIDE = "https://networkdoodles.com/labs/ansible-101"
BIN = pathlib.Path(sys.executable).parent
TTY = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
C = {k: (v if TTY else "") for k, v in dict(g="\033[32m", r="\033[31m", y="\033[33m", c="\033[36m", d="\033[2m", b="\033[1m", x="\033[0m").items()}
NOISE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
LEAVES, SPINES = ["leaf1", "leaf2"], ["spine1"]
BANNER = "Managed by Ansible · Network Doodles lab"


def ansible(*args, env=None):
    """Run an Ansible CLI from the venv in the repo root. Returns (exit code, output)."""
    p = subprocess.run([str(BIN / args[0]), *args[1:]], cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "ANSIBLE_FORCE_COLOR": "0", "ANSIBLE_CONFIG": str(ROOT / "ansible.cfg"), **(env or {})})
    return p.returncode, NOISE.sub("", p.stdout + p.stderr)


def recap(out):
    """{host: {"ok": n, "changed": n, "failed": n}} from a PLAY RECAP."""
    rows = re.findall(r"^(\S+)\s+:\s+ok=(\d+)\s+changed=(\d+)\s+unreachable=(\d+)\s+failed=(\d+)", out, re.M)
    return {h: {"ok": int(o), "changed": int(c), "failed": int(f) + int(u)} for h, o, c, u, f in rows}


def playbook_ok(path, *extra):
    """Run a playbook; yields whether it ran cleanly on every switch."""
    if not (ROOT / path).exists():
        yield False, f"{path} exists"
        return
    code, out = ansible("ansible-playbook", path, *extra)
    r = recap(out)
    failed = [ln.strip() for ln in out.splitlines() if ln.startswith(("fatal:", "failed:", "ERROR!", "[ERROR]"))]
    yield code == 0 and r and all(v["failed"] == 0 for v in r.values()), \
        f"{path} runs cleanly" + (f" ({failed[0][:140]})" if failed else "" if code == 0 else " (make run shows why)")


def idempotent(path):
    """A second run of the playbook changes nothing."""
    code, out = ansible("ansible-playbook", path)
    r = recap(out)
    changed = sum(v["changed"] for v in r.values()) if r else None
    yield code == 0 and changed == 0, f"a second run of {path} changes nothing (changed={changed})"


def get(sw, path, datastore="running"):
    try:
        return SRL(sw).get(path, datastore)
    except Exception:
        return None


def inventory():
    code, out = ansible("ansible-inventory", "--list")
    try:
        return json.loads(out[out.index("{"):]) if code == 0 else None
    except ValueError:
        return None


# ── chapter 1 · hello, ansible ─────────────────────────────────────────────────
def t1_1():
    from importlib import metadata
    yield True, f"ansible-core {metadata.version('ansible-core')} is installed"
    code, out = ansible("ansible-galaxy", "collection", "list", "nokia.srlinux")
    m = re.search(r"nokia\.srlinux\s+(\S+)", out)
    yield m is not None, f"the nokia.srlinux collection is installed ({m.group(1) if m else 'missing: make setup'})"
    for sw in SWITCHES:
        v = get(sw, "/system/information/version", "state")
        yield v is not None, f"{sw} answers its API" + (f" (SR Linux {v.split('-')[0]})" if v else ": make up")


def t1_2():
    inv = inventory()
    yield inv is not None, "inventory/hosts.yml parses (ansible-inventory --list)"
    if not inv:
        return
    hosts = lambda g: sorted(inv.get(g, {}).get("hosts", []))  # noqa: E731
    yield hosts("spines") == SPINES, f"group spines is [spine1] (got {hosts('spines')})"
    yield hosts("leaves") == LEAVES, f"group leaves is [leaf1, leaf2] (got {hosts('leaves')})"
    children = sorted(inv.get("fabric", {}).get("children", []))
    yield children == ["leaves", "spines"], f"group fabric holds leaves and spines (got {children})"
    code, out = ansible("ansible", "fabric", "-m", "nokia.srlinux.get",
                        "-a", '{"paths": [{"path": "/system/name/host-name", "datastore": "state"}]}')
    reached = re.findall(r"^(\S+) \| SUCCESS", out, re.M)
    yield sorted(reached) == sorted(SWITCHES), f"Ansible reaches all three switches ({len(reached)}/3)"


def t1_3():
    ans = load("answers/1.3.yml") or {}
    for sw in SWITCHES:
        want = get(sw, "/system/information/version", "state")
        got = str((ans.get(sw) or {}).get("version", ""))
        yield bool(want) and got == want, f"answers/1.3.yml has {sw}'s software version" + ("" if got == want else f" (got {got or 'nothing'})")
    want = get("leaf1", "/platform/chassis/serial-number", "state")
    got = str(ans.get("leaf1", {}).get("serial", "")) if isinstance(ans.get("leaf1"), dict) else ""
    yield bool(want) and got == want, f"and leaf1's chassis serial number" + ("" if got == want else f" (got {got or 'nothing'})")


# ── chapter 2 · your first playbook ────────────────────────────────────────────
def t2_1():
    yield from playbook_ok("playbooks/hello.yml")
    for sw in SWITCHES:
        b = get(sw, "/system/banner/login-banner")
        yield b == BANNER, f"{sw} shows the login banner" + ("" if b == BANNER else f" (got {b!r})")
    for sw in SWITCHES:
        contact = get(sw, "/system/information/contact")
        yield bool(contact) and "@" in str(contact), f"the challenge: {sw} has a contact email (got {contact!r})"
    yield from idempotent("playbooks/hello.yml")


def t2_2():
    for sw in SWITCHES:
        domain = get(sw, "/system/name/domain-name")
        yield domain == "lab.networkdoodles.com", f"{sw} domain is lab.networkdoodles.com (got {domain!r})"
        tz = get(sw, "/system/clock/timezone")
        yield tz == "America/New_York", f"the challenge: {sw}'s timezone is America/New_York (got {tz!r})"
    code, out = ansible("ansible-playbook", "playbooks/hello.yml", "--check", "--diff")
    r = recap(out)
    yield code == 0 and r and sum(v["changed"] for v in r.values()) == 0, "--check --diff runs and finds nothing left to change"


# ── chapter 3 · variables and facts ────────────────────────────────────────────
def t3_1():
    inv_text = (ROOT / "inventory/hosts.yml").read_text() if (ROOT / "inventory/hosts.yml").exists() else ""
    yield "ansible_" not in inv_text, "inventory/hosts.yml only lists hosts: connection settings moved to group_vars"
    gv = load("inventory/group_vars/fabric.yml") or {}
    yield gv.get("ansible_connection") == "ansible.netcommon.httpapi", "inventory/group_vars/fabric.yml holds the connection settings"
    want_ntp = sorted(str(n.get("address")) for n in (gv.get("ntp_servers") or []) if isinstance(n, dict))
    yield len(want_ntp) == 2, f"inventory/group_vars/fabric.yml lists two ntp_servers (got {want_ntp})"
    yield from playbook_ok("playbooks/base.yml")
    for sw in SWITCHES:
        servers = (get(sw, "/system/ntp") or {}).get("server") or []
        got = sorted(s.get("address") for s in servers)
        yield got == want_ntp and want_ntp, f"{sw} uses the NTP servers from group_vars (got {got})"
    for sw in SWITCHES:
        hv = load(f"inventory/host_vars/{sw}.yml") or {}
        want = hv.get("location")
        got = get(sw, "/system/information/location")
        yield bool(want) and got == want, f"{sw}'s location comes from inventory/host_vars/{sw}.yml ({got!r})"
    yield from idempotent("playbooks/base.yml")


def t3_2():
    yield from playbook_ok("playbooks/facts.yml")
    for sw in SWITCHES:
        facts = load(f"build/facts/{sw}.yml") or {}
        want_v = get(sw, "/system/information/version", "state")
        want_s = get(sw, "/platform/chassis/serial-number", "state")
        yield facts.get("version") == want_v and facts.get("serial") == want_s, \
            f"build/facts/{sw}.yml has its real version and serial"


# ── chapter 4 · loops, conditionals, templates ─────────────────────────────────
def t4_1():
    yield from playbook_ok("playbooks/interfaces.yml")
    for sw in SWITCHES:
        want = (load(f"inventory/host_vars/{sw}.yml") or {}).get("interfaces") or []
        yield len(want) >= 1, f"inventory/host_vars/{sw}.yml lists its interfaces ({len(want)})"
        for i in want:
            d = get(sw, f"/interface[name={i['name']}]/description")
            a = get(sw, f"/interface[name={i['name']}]/admin-state")
            yield d == i.get("description") and a == "enable", f"{sw} {i['name']}: '{i.get('description')}', enabled (got {d!r}, {a})"
            if i.get("uplink"):
                mtu = get(sw, f"/interface[name={i['name']}]/mtu")
                yield mtu == 9100, f"{sw} {i['name']} is an uplink, so MTU 9100 (got {mtu})"
    yield from idempotent("playbooks/interfaces.yml")


def t4_2():
    yield from playbook_ok("playbooks/report.yml")
    report = (ROOT / "build/fabric-report.md").read_text() if (ROOT / "build/fabric-report.md").exists() else ""
    yield bool(report), "build/fabric-report.md exists"
    for sw in SWITCHES:
        v = get(sw, "/system/information/version", "state") or "?"
        yield bool(re.search(rf"\|\s*{sw}\s*\|.*{re.escape(v.split('-')[0])}", report)), f"the report has a row for {sw} with its version"
    yield "uplink" in report.lower(), "uplinks are marked (the `when` / `if` part)"


# ── chapter 5 · handlers, tags, errors ─────────────────────────────────────────
def t5_1():
    # Your switches already have NTP from chapter 3, so a run would change nothing and the handler would
    # never fire. Take NTP away first: the next run has something to change.
    for sw in SWITCHES:
        SRL(sw).delete("/system/ntp")
    code, out = ansible("ansible-playbook", "playbooks/base.yml")
    yield code == 0, "playbooks/base.yml runs cleanly (the checker removed NTP first, so there's a change)"
    yield "RUNNING HANDLER" in out, "something changed, so the save handler ran"
    yield out.count("RUNNING HANDLER") == 1, "and it ran once, at the end, not once per task"
    ntp = [n["address"] for n in (load("inventory/group_vars/fabric.yml") or {}).get("ntp_servers") or []]
    for sw in SWITCHES:
        p = subprocess.run(["docker", "exec", sw, "cat", "/etc/opt/srlinux/config.json"], capture_output=True, text=True)
        yield bool(ntp) and all(a in p.stdout for a in ntp), f"{sw}'s startup config has the NTP servers: the handler saved it"
    code, out = ansible("ansible-playbook", "playbooks/base.yml")
    yield code == 0 and "RUNNING HANDLER" not in out, "a second run changes nothing, so the handler stays quiet"
    # The challenge: the location task notifies the handler too. Move leaf1, and only the location changes.
    SRL("leaf1").set([{"action": "update", "path": "/system/information", "value": {"location": "moved by the checker"}}])
    code, out = ansible("ansible-playbook", "playbooks/base.yml")
    yield code == 0 and "RUNNING HANDLER" in out, "the challenge: a location change alone also runs the save handler"


def t5_2():
    code, out = ansible("ansible-playbook", "playbooks/interfaces.yml", "--list-tasks", "--tags", "descriptions")
    tasks = [ln.strip() for ln in out.splitlines() if "TAGS:" in ln and "play #" not in ln]
    yield code == 0 and len(tasks) >= 1, f"--tags descriptions selects {len(tasks)} task(s)"
    code2, out2 = ansible("ansible-playbook", "playbooks/interfaces.yml", "--list-tasks")
    all_tasks = [ln for ln in out2.splitlines() if "TAGS:" in ln and "play #" not in ln]
    yield len(all_tasks) > len(tasks), "and leaves the others out"
    yield from playbook_ok("playbooks/interfaces.yml", "--tags", "descriptions")
    code, out = ansible("ansible-playbook", "playbooks/interfaces.yml", "--list-tasks", "--tags", "mtu")
    mtu = [ln for ln in out.splitlines() if "TAGS:" in ln and "play #" not in ln]
    yield code == 0 and len(mtu) >= 1 and all("descriptions" not in ln for ln in mtu), \
        f"the challenge: --tags mtu selects the MTU task, and only that ({len(mtu)})"


def t5_3():
    code, out = ansible("ansible-playbook", "playbooks/safe_change.yml")
    r = recap(out)
    yield code == 0, "playbooks/safe_change.yml finishes, even though its change fails"
    yield "rescue" in out.lower() or (r and all(v.get("failed", 0) == 0 for v in r.values())), "the rescue section ran"
    for sw in LEAVES:
        mtu = get(sw, "/interface[name=ethernet-1/49]/mtu")
        yield mtu == 9100, f"{sw} ethernet-1/49 is back to its known-good MTU 9100 (got {mtu})"
    play = (load("playbooks/safe_change.yml") or [{}])[0]
    blocks = [t for t in play.get("tasks") or [] if isinstance(t, dict) and "block" in t]
    yield blocks and blocks[0].get("always"), "the challenge: the block has an always section"
    names = [t.get("name") for t in (blocks[0].get("always") or [])] if blocks else []
    yield names and all(f"TASK [{n}]" in out for n in names), "...and it ran, after the rescue"


# ── chapter 6 · roles and collections ──────────────────────────────────────────
def t6_1():
    for role in ("base", "interfaces"):
        yield (ROOT / f"roles/{role}/tasks/main.yml").exists(), f"roles/{role}/tasks/main.yml exists"
    yield (ROOT / "roles/base/defaults/main.yml").exists(), "roles/base has defaults (the banner text lives there)"
    yield (ROOT / "roles/base/handlers/main.yml").exists(), "roles/base has the save handler"
    yield from playbook_ok("playbooks/site.yml")
    yield from idempotent("playbooks/site.yml")


def t6_2():
    want = (load("inventory/group_vars/leaves.yml") or {}).get("base_motd_text")
    yield bool(want), "inventory/group_vars/leaves.yml overrides base_motd_text"
    own = (load("inventory/host_vars/leaf2.yml") or {}).get("base_motd_text")
    yield bool(own) and own != want, "the challenge: inventory/host_vars/leaf2.yml gives leaf2 a message of its own"
    yield from playbook_ok("playbooks/site.yml")
    got = get("leaf1", "/system/banner/motd-banner")
    yield got == want, f"leaf1 shows the leaves' message of the day (got {got!r})"
    got = get("leaf2", "/system/banner/motd-banner")
    yield bool(own) and got == own, f"leaf2 shows its own: host_vars beats group_vars (got {got!r})"
    default = (load("roles/base/defaults/main.yml") or {}).get("base_motd_text")
    got = get("spine1", "/system/banner/motd-banner")
    yield bool(default) and got == default, f"spine1 keeps the role's default (got {got!r})"


# ── chapter 7 · secrets ────────────────────────────────────────────────────────
def t7_1():
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    # The README documents the lab login on purpose; the checker and lab scripts need it to reach the switches.
    leaks = [f for f in tracked if not f.startswith(("lib/", "checks/", "lab/", ".maint/", "docs/", "README"))
             and (ROOT / f).is_file() and PASSWORD in (ROOT / f).read_text(errors="ignore")]
    yield not leaks, "the switch password isn't in any file you commit" + (f" (found in {', '.join(leaks)})" if leaks else "")
    vault = ROOT / "inventory/group_vars/all/vault.yml"
    yield vault.exists() and vault.read_text().startswith("$ANSIBLE_VAULT"), "inventory/group_vars/all/vault.yml is encrypted"
    yield "vault_ansible_password" in ((ROOT / "inventory/group_vars/fabric.yml").read_text() if (ROOT / "inventory/group_vars/fabric.yml").exists() else ""), \
        "inventory/group_vars/fabric.yml gets ansible_password from the vault"
    ignored = subprocess.run(["git", "check-ignore", "-q", ".vault-pass"], cwd=ROOT).returncode == 0
    yield ignored, ".vault-pass is git-ignored"
    fabric = (ROOT / "inventory/group_vars/fabric.yml").read_text() if (ROOT / "inventory/group_vars/fabric.yml").exists() else ""
    yield re.search(r"^snmp_community:\s*!vault", fabric, re.M), \
        "the challenge: snmp_community is in group_vars/fabric.yml, encrypted inline (ansible-vault encrypt_string)"
    code, out = ansible("ansible", "spine1", "-m", "ansible.builtin.debug", "-a", "var=snmp_community")
    yield code == 0 and "VARIABLE IS NOT DEFINED" not in out and "snmp_community" in out, "...and Ansible decrypts it"
    yield from playbook_ok("playbooks/site.yml")


# ── chapter 8 · run it like production ─────────────────────────────────────────
def t8_1():
    p = subprocess.run(["docker", "image", "inspect", "ans101-ee:1"], capture_output=True)
    yield p.returncode == 0, "execution environment ans101-ee:1 is built (make ee)"
    code, out = ansible("ansible-navigator", "run", "playbooks/site.yml", "--mode", "stdout")
    r = recap(out)
    yield code == 0 and r and all(v["failed"] == 0 for v in r.values()), "ansible-navigator runs playbooks/site.yml in the EE"


def t8_2():
    code, out = ansible("ansible-lint", "--offline", "-q")
    n = len(re.findall(r"^\S+:\d+", out, re.M))
    yield code == 0, f"ansible-lint passes ({n} problem(s))"


def t8_3():
    ci = load(".gitlab-ci.yml") or {}
    jobs = {k: v for k, v in ci.items() if isinstance(v, dict) and "script" in v}
    scripts = " ".join(" ".join(v.get("script", [])) for v in jobs.values())
    yield "ansible-lint" in scripts, ".gitlab-ci.yml runs ansible-lint"
    yield "--syntax-check" in scripts, "and a syntax check of playbooks/site.yml"
    yield "yamllint" in scripts, "and yamllint"


TASKS = {
    "1.1": ("meet the lab", []),
    "1.2": ("write the inventory", ["inventory/hosts.yml"]),
    "1.3": ("ask the switches", ["answers/1.3.yml"]),
    "2.1": ("your first playbook", ["playbooks/hello.yml"]),
    "2.2": ("check mode and diff", ["playbooks/hello.yml"]),
    "3.1": ("group_vars and host_vars", ["inventory/hosts.yml", "inventory/group_vars/fabric.yml", "inventory/host_vars/spine1.yml",
                                          "inventory/host_vars/leaf1.yml", "inventory/host_vars/leaf2.yml", "playbooks/base.yml"]),
    "3.2": ("facts and register", ["playbooks/facts.yml"]),
    "4.1": ("interfaces from data", ["inventory/host_vars/spine1.yml", "inventory/host_vars/leaf1.yml", "inventory/host_vars/leaf2.yml",
                                      "playbooks/interfaces.yml"]),
    "4.2": ("a report from a template", ["playbooks/report.yml", "playbooks/templates/fabric-report.md.j2"]),
    "5.1": ("save only on change", ["playbooks/base.yml"]),
    "5.2": ("tags", ["playbooks/interfaces.yml"]),
    "5.3": ("when it goes wrong", ["playbooks/safe_change.yml"]),
    "6.1": ("playbooks into roles", ["roles/base/tasks/main.yml", "roles/base/defaults/main.yml",
                                      "roles/base/handlers/main.yml", "roles/interfaces/tasks/main.yml", "playbooks/site.yml"]),
    "6.2": ("defaults and overrides", ["inventory/group_vars/leaves.yml", "inventory/host_vars/leaf2.yml"]),
    "7.1": ("vault the password", ["inventory/group_vars/fabric.yml", "inventory/group_vars/all/vault.yml", "ansible.cfg", ".gitignore"]),
    "8.1": ("execution environments", ["execution-environment.yml", "ansible-navigator.yml"]),
    "8.2": ("ansible-lint", ["playbooks/legacy.yml"]),
    "8.3": ("a CI job", [".gitlab-ci.yml"]),
}
CHAPTERS = {1: "hello, ansible", 2: "your first playbook", 3: "variables and facts", 4: "loops, conditionals, templates",
            5: "handlers, tags, errors", 6: "roles and collections", 7: "secrets", 8: "run it like production"}


def report(t):
    print(f"{C['c']}╭─{C['x']} {C['b']}task {t}{C['x']} {C['d']}·{C['x']} {TASKS[t][0]}")
    results = []
    try:
        for ok, msg in globals()[f"t{t.replace('.', '_')}"]():
            ok = bool(ok)
            results.append(ok)
            print(f"{C['c']}│{C['x']}  {C['g'] + '✓' if ok else C['r'] + '✗'}{C['x']} {msg}")
    except Exception as e:  # a half-finished task shouldn't crash the checker
        results.append(False)
        print(f"{C['c']}│{C['x']}  {C['r']}✗{C['x']} {type(e).__name__}: {str(e).splitlines()[0][:140] if str(e) else ''}")
    passed = sum(results)
    done = passed == len(results)
    tail = f"{C['g']}verified{C['x']}" if done else f"{C['y']}stuck?{C['x']} make solve T={t}  {C['d']}·  {GUIDE}/task-{t.replace('.', '-')}/{C['x']}"
    print(f"{C['c']}╰─{C['x']} {passed}/{len(results)} checks passed  {tail}\n")
    return done


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    if arg == "--files":
        print(" ".join(TASKS.get(sys.argv[2], ("", []))[1]))
        sys.exit(0)
    if arg == "--files-before":
        ch = int(sys.argv[2])
        files = {f for t, (_, fs) in TASKS.items() if int(t.split(".")[0]) < ch for f in fs}
        print(" ".join(sorted(files)))
        sys.exit(0)
    if arg.startswith("ch"):
        n = int(arg[2:])
        tasks = [t for t in TASKS if t.startswith(f"{n}.")]
        print(f"{C['b']}chapter {n} · {CHAPTERS[n]}{C['x']}\n")
        sys.exit(0 if all([report(t) for t in tasks]) else 1)
    if arg == "all":
        done = [t for t in TASKS if report(t)]
        print(f"{C['b']}{len(done)}/{len(TASKS)} tasks verified{C['x']}")
        sys.exit(0 if len(done) == len(TASKS) else 1)
    if arg not in TASKS:
        sys.exit(f"no task {arg}: tasks are {', '.join(TASKS)}")
    sys.exit(0 if report(arg) else 1)
