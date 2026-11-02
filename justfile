PROJECT_ROOT := justfile_dir()
VENV := PROJECT_ROOT / ".venv"
PYBIN := if os() == "windows" { "Scripts" } else { "bin" }
EXE := if os() == "windows" { ".exe" } else { "" }
VENV_PYTHON := VENV / PYBIN / "python" + EXE

[doc("run the docdicer's golden tests")]
test: _venv
  PYTHONPATH="{{PROJECT_ROOT}}" "{{VENV_PYTHON}}" "{{PROJECT_ROOT}}/docdicer/test/test_dicer.py"

FLAKE8_IGNORE := "E122,E201,E202,E203,E225,E226,E228,E261,E265,E302,E303,E501,E704,E731,W291,W293,W391,W503"
[doc("[dev] black-format, isort, flake8 the generator (adjagent), the tests and devtools, or the given path(s) in place of all of them")]
format: _venv
  @"{{VENV_PYTHON}}" -m black --line-length=120 docdicer
  @"{{VENV_PYTHON}}" -m isort --profile black --line-length 120 docdicer
  @"{{VENV_PYTHON}}" -m flake8 --ignore="{{FLAKE8_IGNORE}}" docdicer

# Venv layout differs by OS: POSIX puts executables in .venv/bin, Windows in
# .venv/Scripts with .exe suffixes. Resolved here via just's os() builtin.

# Lazy: if the venv's python already exists this is a no-op; a half-built
# venv is repaired by deleting .venv and re-running.
# The tool versions are pinned on the install line, so a venv rebuild cannot
# silently change what `just format-python` and `just test` do; bumping one is
# an edit to that line, visible in the diff. `pip` stays unpinned: it installs,
# it does not produce output a change depends on.
[private]
_venv:
  #!/usr/bin/env bash
  set -euo pipefail
  if [[ ! -x "{{VENV_PYTHON}}" ]]; then
    python3 -m venv "{{VENV}}"
    "{{VENV_PYTHON}}" -m pip install pip --upgrade
    "{{VENV_PYTHON}}" -m pip install pytest==9.2.0 isort==9.0.2 black==26.10.1 flake8==7.5.0
  fi
