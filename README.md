# Lab · Ansible 101 for networking

**[▶ Open the lab](https://labs.networkdoodles.com/open/ansible-101)**: one click, nothing to install

The hands-on companion to the Network Doodles series
**[Ansible 101 for networking](https://networkdoodles.com/series/ansible-101/)**. One chapter per post.

You'll start with an inventory and an ad-hoc command, and finish with roles, a vaulted password, an
execution environment and a CI pipeline, all against a real leaf-spine fabric of Nokia SR Linux switches.
Every task has a checker that reads the switches and tells you when you're right.

**Step-by-step guide:** https://networkdoodles.com/labs/ansible-101/
**New to VS Code, the terminal or Ansible?** https://networkdoodles.com/labs/basics/ walks through all of it, with screenshots.

## Start

**Open the lab** (the link above, or the button on the [guide's page](https://networkdoodles.com/labs/ansible-101/)) and
sign in with GitHub. It creates your own codespace, on your GitHub account's free allowance (the lab's 4-core
machine uses well under 20 of its 120 monthly core-hours), and opens the lab app: the guide on the left, VS Code
on the right. The first start takes about 6 minutes while it builds the container and starts the switches; the
top bar says **network up** when it's ready. Then follow [task 1.1](https://networkdoodles.com/labs/ansible-101/task-1-1/):
**Check task**, under the guide, checks your work.

The lab stops itself after 20 minutes nobody's using it, and **Open the lab** picks up where you left off.
Restarting gives you fresh switches; your files stay, and re-running your playbooks puts the config back.
(That's the point.) **Finish lab** in the top bar deletes the codespace when you're done.

## Advanced: run it on your laptop

Same dev container, on your own Docker. You need Docker (Desktop, OrbStack or Colima) with 8 GB of memory,
Git, and VS Code with the Dev Containers extension. The switches need containerlab, which runs on Linux, so
use the dev container rather than your laptop's own shell.

```bash
git clone https://gitlab.com/networkdoodles-labs/ansible-101.git
cd ansible-101
code .             # then "Reopen in Container"; the lab app is at http://localhost:8000
```

## The fabric

```text
             ┌──────────┐
             │  spine1  │
             └─┬──────┬─┘
          e1-1 │      │ e1-2
         e1-49 │      │ e1-49
       ┌───────┴┐    ┌┴───────┐
       │ leaf1  │    │ leaf2  │
       └───┬────┘    └────┬───┘
       e1-1│              │e1-1
         host1          host2
```

```bash
make up                  # (re)start the switches with factory config (the dev container does this on start)
make ssh NODE=leaf1      # SR Linux CLI: show version, show system lldp neighbor, quit
make status              # versions and what's running
```

Login for the switches is `admin` / `NokiaSrl1!` (containerlab's default for SR Linux; chapter 7 stops the
playbooks from keeping it in plain text).

## How the tasks work

Tasks are numbered **chapter.task**. Each one is: read the guide, fill in the `TODO`s, run, check.

```bash
make run T=2.1     # run the task's playbook or command
make check T=2.1   # verify it against the switches
make check CH=2    # every task in chapter 2
make check         # progress across the whole lab
```

| Task | Post | You edit | The idea |
|------|------|----------|----------|
| **1** | **Hello, Ansible** | | |
| 1.1 | Meet the lab | – | Ansible, a collection, three switches with an API |
| 1.2 | Write the inventory | `inventory/hosts.yml` | Hosts, groups, groups of groups, connection settings |
| 1.3 | Ask the switches | `answers/1.3.yml` | Ad-hoc commands: one module, many hosts, no playbook |
| **2** | **Your first playbook** | | |
| 2.1 | Your first playbook | `playbooks/hello.yml` | Plays, tasks, modules; a second run changes nothing |
| 2.2 | Check mode and diff | `playbooks/hello.yml` | See the change before you make it |
| **3** | **Variables and facts** | | |
| 3.1 | group_vars and host_vars | `inventory/`, `playbooks/base.yml` | Data in one place, keyed by group and host; host beats group |
| 3.2 | Facts and register | `playbooks/facts.yml` | Ask, keep the answer, use it |
| **4** | **Loops, conditionals, templates** | | |
| 4.1 | Interfaces from data | `inventory/host_vars/`, `playbooks/interfaces.yml` | One task, a loop, a `when` |
| 4.2 | A report from a template | `playbooks/templates/fabric-report.md.j2` | Jinja2 turns data into any text |
| **5** | **Handlers, tags, errors** | | |
| 5.1 | Save only on change | `playbooks/base.yml` | Handlers run once, only when notified |
| 5.2 | Tags | `playbooks/interfaces.yml` | Run part of a playbook |
| 5.3 | When it goes wrong | `playbooks/safe_change.yml` | `block`, `rescue`, `always` |
| **6** | **Roles and collections** | | |
| 6.1 | Playbooks into roles | `roles/`, `playbooks/site.yml` | Tasks, defaults, handlers in a reusable unit |
| 6.2 | Defaults and overrides | `inventory/group_vars/leaves.yml` | Role defaults lose to everything |
| **7** | **Secrets** | | |
| 7.1 | Vault the password | `inventory/group_vars/`, `ansible.cfg` | Encrypted in Git, the key never is |
| **8** | **Run it like production** | | |
| 8.1 | Execution environments | `execution-environment.yml`, `ansible-navigator.yml` | Ansible in a container you can ship |
| 8.2 | ansible-lint | `playbooks/legacy.yml` | The production profile, no silenced rules |
| 8.3 | A CI job | `.gitlab-ci.yml` | Lint and syntax-check every push |

## Start at any chapter, or get unstuck

```bash
make skip CH=4     # copy in the finished files of chapters 1 to 3, then start chapter 4
make solve T=4.1   # copy in one task's finished files; read what changed with git diff --staged
make up            # fresh switches; then re-run your playbooks to put the config back
```

The answers live on the [`solution`](https://gitlab.com/networkdoodles-labs/ansible-101/-/tree/solution)
branch, with a tag at the end of every chapter (`solution-ch1` to `solution-ch8`). Chapter 7's vault password
is `netdoodles-vault`: `echo netdoodles-vault > .vault-pass` if you skip past it.

## Layout

```text
inventory/      hosts.yml (which switches), group_vars/ and host_vars/ (everything about them)
playbooks/      one playbook per idea, plus site.yml (chapter 6) and templates/
roles/          chapter 6: base and interfaces
answers/        task 1.3's answers
checks/         `make check`: reads the switches and your files, never changes them
lab/            the containerlab topology, make status and the wait-for-the-switches script
lib/            a small SR Linux JSON-RPC client the checker uses
.devcontainer/  the dev container: Docker-in-Docker, code-server, containerlab, Ansible in a venv
```

## Versions

Nokia SR Linux 26.7.2, containerlab 0.82, ansible-core 2.20.1, nokia.srlinux 1.1.1, ansible.netcommon 8.7.1,
ansible-lint 26.10.1, ansible-navigator 26.10.0.

---

Made by [David Henderson](https://networkdoodles.com/aboutme/) for [Network Doodles](https://networkdoodles.com).
The lab lives on [GitLab](https://gitlab.com/networkdoodles-labs/ansible-101); the GitHub copy is a read-only
mirror for Codespaces. Questions? Open an issue on GitLab.
