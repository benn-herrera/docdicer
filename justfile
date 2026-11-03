PROJECT_ROOT := justfile_dir()
VENV := PROJECT_ROOT / ".venv"
PYBIN := if os() == "windows" { "Scripts" } else { "bin" }
EXE := if os() == "windows" { ".exe" } else { "" }
VENV_PYTHON := "\"" + VENV / PYBIN / "python" + EXE + "\""

DD_PYTHON := "PYTHONPATH=\"" + PROJECT_ROOT + "\" " + VENV_PYTHON

[doc("run the docdicer's golden tests")]
test: _venv
  {{DD_PYTHON}} -m pytest docdicer

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
  ver=v$({{DD_PYTHON}} -m docdicer --version)
  [[ "${ver}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { printf 'tag: version %s is not v<major>.<minor>.<patch>\n' "${ver}" >&2; exit 1; }
  GPG_TTY=$(tty) git tag -s "${ver}" -m "release ${ver}"
  git tag -v "${ver}"

# Venv layout differs by OS: POSIX puts executables in .venv/bin, Windows in
# .venv/Scripts with .exe suffixes. Resolved here via just's os() builtin.

# Lazy: if the venv's python already exists this is a no-op; a half-built
# venv is repaired by deleting .venv and re-running.
# The tool versions are pinned on the install line, so a venv rebuild cannot
# silently change what `just format` and `just test` do; bumping one is
# an edit to that line, visible in the diff. `pip` stays unpinned: it installs,
# it does not produce output a change depends on.
[private]
_venv:
  #!/usr/bin/env bash
  set -euo pipefail
  if [[ ! -x {{VENV_PYTHON}} ]]; then
    python3 -m venv "{{VENV}}"
    {{VENV_PYTHON}} -m pip install pip --upgrade
    {{VENV_PYTHON}} -m pip install pytest==9.2.0 isort==9.0.2 black==26.10.1 flake8==7.5.0
  fi
