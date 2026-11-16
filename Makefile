# Network Doodles lab · Ansible 101 for networking
# Guide: https://networkdoodles.com/labs/ansible-101/
#
# Tasks are numbered chapter.task, so T=1.2 is chapter 1, task 2. CH=<n> means a whole chapter.
.DEFAULT_GOAL := help
# The dev container keeps its venv outside the repo (VENV is set there); locally it is .venv.
VENV ?= .venv
PY := $(VENV)/bin/python
BIN := $(VENV)/bin
GUIDE := https://networkdoodles.com/labs/ansible-101
TOPO := lab/fabric.clab.yml
T ?=
CH ?=
# Codespaces checks the repo out into a world-writable folder, and Ansible refuses to read an ansible.cfg
# from one (anyone could have planted it). Naming the file explicitly is the documented way around that.
export ANSIBLE_CONFIG := $(CURDIR)/ansible.cfg

# What `make run T=<id>` runs. Everything else is the task's own ansible / ansible-playbook command.
RUN_1.1 := $(MAKE) status
RUN_1.2 := $(BIN)/ansible-inventory --graph
RUN_1.3 := $(BIN)/ansible fabric -m cisco.ios.ios_command -a "commands='show version'"
RUN_2.1 := $(BIN)/ansible-playbook playbooks/hello.yml
RUN_2.2 := $(BIN)/ansible-playbook playbooks/hello.yml --check -v
RUN_3.1 := $(BIN)/ansible-playbook playbooks/base.yml
RUN_3.2 := $(BIN)/ansible-playbook playbooks/facts.yml
RUN_4.1 := $(BIN)/ansible-playbook playbooks/interfaces.yml
RUN_4.2 := $(BIN)/ansible-playbook playbooks/report.yml
RUN_5.1 := $(BIN)/ansible-playbook playbooks/base.yml
RUN_5.2 := $(BIN)/ansible-playbook playbooks/interfaces.yml --tags descriptions
RUN_5.3 := $(BIN)/ansible-playbook playbooks/safe_change.yml
RUN_6.1 := $(BIN)/ansible-playbook playbooks/site.yml
RUN_6.2 := $(BIN)/ansible-galaxy collection list
RUN_7.1 := $(BIN)/ansible-playbook playbooks/site.yml
RUN_8.1 := $(MAKE) ee && $(BIN)/ansible-navigator run playbooks/site.yml
RUN_8.2 := $(BIN)/ansible-lint
RUN_8.3 := $(MAKE) ci

help: ## show this help
	@grep -hE '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# The venv's .ok holds a hash of the requirements it was built from (the dev container's image writes the
# same hash), so a fresh checkout doesn't reinstall a venv that's already right.
REQS := requirements.txt requirements.yml
REQ_HASH = $(shell python3 -c "import hashlib,sys; print(hashlib.sha256(b''.join(open(f,'rb').read() for f in sys.argv[1:])).hexdigest()[:16])" $(REQS))

setup: ## create the Python venv with Ansible, and install the collections
	@if [ "$$(cat $(VENV)/.ok 2>/dev/null)" = "$(REQ_HASH)" ] && [ -x $(PY) ]; then exit 0; fi; \
	echo "installing Ansible and the lab's tools into $(VENV)"; \
	if command -v uv >/dev/null; then \
	  uv venv -q --allow-existing --python 3.13 $(VENV) && uv pip install -q --python $(PY) -r requirements.txt; \
	else \
	  python3 -m venv $(VENV) && $(PY) -m pip install -q --upgrade pip && $(PY) -m pip install -q -r requirements.txt; \
	fi && $(BIN)/ansible-galaxy collection install -r requirements.yml >/dev/null && echo "$(REQ_HASH)" > $(VENV)/.ok

# The dev container's own Docker engine starts alongside the container, so the first commands can beat it.
docker-ready:
	@for i in $$(seq 1 60); do docker info >/dev/null 2>&1 && exit 0; [ $$i = 1 ] && echo "  waiting for Docker to start ..."; sleep 2; done; \
	echo "Docker isn't answering. In the dev container it starts on its own; on a laptop, start Docker Desktop."; exit 1

BOLT := ghcr.io/dkhenderson2/capeos-bolt:0.11.2
images: docker-ready ## pull the switch images (the dev container does this once)
	docker pull -q $(BOLT)
	docker pull -q alpine:3.22

up: setup docker-ready ## start the switches: spine1, leaf1, leaf2 and two hosts (about ten seconds)
	@command -v containerlab >/dev/null || (echo "containerlab isn't installed: it comes with the dev container"; exit 2)
	@# Each switch boots from a fresh copy of its factory config in lab/configs/. `write memory` saves into
	@# the copy (build/startup/), so the files Git tracks never change.
	@mkdir -p build/startup && cp lab/configs/*.cfg build/startup/
	@# --reconfigure: a fresh start every time, so a restarted container never trips over an old lab.
	containerlab deploy -t $(TOPO) --reconfigure
	@$(PY) lab/wait.py

down: ## remove the switches
	containerlab destroy -t $(TOPO) --cleanup

reset: ## put every switch back to its factory config (your files are untouched)
	$(MAKE) up

ssh: ## open a CLI on a switch or host:  make ssh NODE=leaf1
	@test -n "$(NODE)" || (echo "usage: make ssh NODE=leaf1  (or leaf2, spine1, host1, host2)"; exit 2)
	@case "$(NODE)" in host*) docker exec -it $(NODE) sh ;; *) docker exec -it $(NODE) capeos-cli ;; esac

status: ## what's installed, what's running, and where to start  (WAIT=1 waits for the switches)
	@$(PY) lab/status.py $(if $(WAIT),--wait)

run: ## run a task:  make run T=2.1
	@test -n "$(T)" || (echo "usage: make run T=<chapter.task>, e.g. T=2.1"; exit 2)
	@test -n "$(RUN_$(T))" || (echo "task $(T) has nothing to run: see $(GUIDE)/"; exit 2)
	$(RUN_$(T))

check: ## verify a task, a chapter or everything:  make check T=2.1 · CH=2 · (nothing)
	@$(PY) checks/check.py $(if $(T),$(T),$(if $(CH),ch$(CH),all))

# The answers: a tag at the end of every chapter on the solution branch (answers-ch1 ... answers-ch8),
# because files grow chapter by chapter and task 2.1 needs chapter 2's version, not the final one.
# A task's own tag (answers-1.3) wins over its chapter's: 1.3's answers changed with CapeOS 0.11.2.
VAULT_HINT = if [ ! -f .vault-pass ] && git cat-file -e $$tag:inventory/group_vars/all/vault.yml 2>/dev/null; then \
	  echo netdoodles-vault > .vault-pass; echo "wrote .vault-pass (the lab's vault password, chapter 7)"; fi

solve: ## stuck? copy one task's finished files from the solution:  make solve T=2.1
	@test -n "$(T)" || (echo "usage: make solve T=<chapter.task>"; exit 2)
	@files=$$($(PY) checks/check.py --files $(T)); test -n "$$files" || { echo "task $(T) has no files to solve"; exit 2; }; \
	git fetch -q origin --tags 2>/dev/null || true; tag=answers-$(T); \
	git rev-parse -q --verify "refs/tags/$$tag" >/dev/null || tag=answers-ch$$(echo $(T) | cut -d. -f1); \
	git checkout $$tag -- $$files && echo "restored $$files from $$tag. Read what changed: git diff --staged"; \
	$(VAULT_HINT)

skip: ## start at any chapter: copy the finished files of every chapter before it  make skip CH=4
	@test -n "$(CH)" || (echo "usage: make skip CH=<chapter 2-8>"; exit 2)
	@files=$$($(PY) checks/check.py --files-before $(CH)); \
	git fetch -q origin --tags 2>/dev/null || true; tag=answers-ch$$(( $(CH) - 1 )); \
	git checkout $$tag -- $$files ansible.cfg && git reset -q -- $$files ansible.cfg && \
	for t in $$(git tag -l 'answers-[0-9]*.[0-9]*' | sed 's/answers-//'); do [ $$(echo $$t | cut -d. -f1) -lt $(CH) ] && \
	  git checkout answers-$$t -- answers/$$t.yml 2>/dev/null && git reset -q -- answers/$$t.yml; done; \
	echo "you're at the start of chapter $(CH). Run the earlier chapters' playbooks to set up the switches."; \
	$(VAULT_HINT)

EE := ans101-ee:1
ee: setup docker-ready ## chapter 8: build the execution environment (FORCE=1 rebuilds it)
	@if [ -z "$(FORCE)" ] && docker image inspect $(EE) >/dev/null 2>&1; then \
	  echo "execution environment $(EE) is built"; \
	else \
	  $(BIN)/ansible-builder build --tag $(EE) --file execution-environment.yml --context build/ee; \
	fi

ci: ## run the CI pipeline's steps locally (chapter 8)
	$(BIN)/yamllint .
	$(BIN)/ansible-lint
	$(BIN)/ansible-playbook playbooks/site.yml --syntax-check

.PHONY: help setup docker-ready images up down reset ssh status run check solve skip ee ci
