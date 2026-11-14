PROJECT_ROOT := justfile_dir()
VENV := PROJECT_ROOT / ".venv"
PYBIN := if os() == "windows" { "Scripts" } else { "bin" }
EXE := if os() == "windows" { ".exe" } else { "" }
VENV_PYTHON := "\"" + VENV / PYBIN / "python" + EXE + "\""

DD_PYTHON := "PYTHONPATH=\"" + PROJECT_ROOT + "\" " + VENV_PYTHON

help:
  @just --list

[doc("run docdicer's tests: the golden cases, the round trip and the per-module unit tests")]
test: _venv
  {{DD_PYTHON}} -m pytest --basetemp="{{PROJECT_ROOT}}/docdicer/test/temp" docdicer

[doc("build the docdicer wheel into dist/")]
build: _venv
  {{VENV_PYTHON}} -m pip wheel --no-deps -w "{{PROJECT_ROOT}}/dist" "{{PROJECT_ROOT}}"

FLAKE8_IGNORE := "E122,E201,E202,E203,E225,E226,E228,E261,E265,E302,E303,E501,E704,E731,W291,W293,W391,W503"
[doc("[dev] black-format, isort, flake8 the docdicer package and its tests")]
format: _venv
  @{{VENV_PYTHON}} -m black --line-length=120 docdicer
  @{{VENV_PYTHON}} -m isort --profile black --line-length 120 docdicer
  @{{VENV_PYTHON}} -m flake8 --ignore="{{FLAKE8_IGNORE}}" docdicer

_tag-clean:
  @git diff --quiet HEAD || { echo "tag: tracked files have uncommitted changes — commit them, then tag" >&2; exit 1; }

[doc("NEEDS a signing key git tag -s can use: create and verify a signed annotated tag v<version>, <version> being docdicer --version; runs no gates, pushes nothing")]
tag: _tag-clean _venv
  #!/usr/bin/env bash
  set -euo pipefail
  ver=v$(just dev-dd --version)
  [[ "${ver}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { printf 'tag: version %s is not v<major>.<minor>.<patch>\n' "${ver}" >&2; exit 1; }
  GPG_TTY=$(tty) git tag -s "${ver}" -m "release ${ver}"
  git tag -v "${ver}"

# note: uses python3 not VENV_PYTHON to ensure zero dependencies
[doc("run kanban board for this project using this code base's version (blocks with running http server)")]
kanban:
  @just dev-dd kanban

[doc("run doc links check using this conde base's version")]
check-links:
  @just dev-dd check-links *.md

[doc("run ACTIVE_PLAN format compliance check using this conde base's version")]
check-plan:
  @just dev-dd check-plan

[doc("run ACTIVE_DESIGN final-form check using this code base's version")]
check-design:
  @just dev-dd check-design

[doc("run ROADMAP format compliance check using this code base's version")]
check-roadmap:
  @just dev-dd check-roadmap

[doc("run this code base's docdicer with the given arguments, e.g.: just dev-dd dice-doc big.md out/")]
dev-dd *args:
  @PYTHONPATH={{PROJECT_ROOT}} python3 -m docdicer {{args}}

# Venv layout differs by OS: POSIX puts executables in .venv/bin, Windows in
# .venv/Scripts with .exe suffixes. Resolved here via just's os() builtin.

# Lazy: if the venv's python already exists this is a no-op; a half-built
# venv is repaired by deleting .venv and re-running.
# The tool versions on the install line are floors that run on the minimum
# Python: a venv rebuild takes the newest release that installs there, so
# `just format` can reformat after a rebuild.
[private]
_venv:
  #!/usr/bin/env bash
  set -euo pipefail
  if [[ ! -x {{VENV_PYTHON}} ]]; then
    # if /usr/bin/python3 is installed it is the crappy 3.9.6 from xcode command line tools
    # that is actually our minspec, so use it to ensure we're not using any features
    # beyond its ken
    [[ "$(uname)" == Darwin ]] && export PATH=/usr/bin/:${PATH} || true
    python3 -m venv --upgrade-deps "{{VENV}}"
    {{VENV_PYTHON}} -m pip install "pytest>=8.4" "isort>=6.1" "black>=25.11" "flake8>=7.3"
  fi

agents:
  @command -v devpro > /dev/null || { echo 'devpro not installed. run `brew install benn-herrera/tap/devpro`' }
  devpro install . --harnes=claude
  devpro install . --harness=opencode

import? '.opencode/plugins/devpro/skills/docdicer/tools/runner-snippets/docdicer.just'
