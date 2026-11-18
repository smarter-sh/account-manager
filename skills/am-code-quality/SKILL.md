---
name: am-code-quality
description: Use before finishing any Account Manager change, to lint and format Python, Markdown, YAML and JSON with the repository's pre-commit hooks (pydocstringformatter, pyupgrade, codespell, Prettier, black, flake8, complexity-new-violations, isort, autoflake, bandit, pyright-new-errors, pre-commit-hooks, commitlint), or when a hook fails, e.g. "flake8 F401", "complexity C901 new violation", "pyright new error", "codespell flagged a word". Explains what each hook checks, where it is configured, and how to run them on the changed files under zsh.
---

# Account Manager Code Quality

`.pre-commit-config.yaml` at the repository root is the authoritative standard.
If a hook passes, the code meets the standard; if it fails, fix the code. Never
bypass a hook (`--no-verify`, `SKIP=`, a blanket `# noqa`) to make a change
pass. ruff isn't configured, and pylint (which `make python-lint` runs after
the hooks) isn't a hook: don't report their output as lint debt.

## The hooks

| Hook                        | Configuration                                                         | What it does                                                                                                                                     |
| --------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `pydocstringformatter`      |                                                                       | Normalizes docstring layout.                                                                                                                     |
| `pyupgrade`                 |                                                                       | Modern Python syntax.                                                                                                                            |
| `codespell`                 | `--ignore-words=codespell.txt`                                        | Spelling, in code, docs and skills. Add real project words to `codespell.txt`.                                                                   |
| `prettier`                  | `.prettierrc.json`                                                    | Formats Markdown, YAML, JSON and JS; skips `am/am/templates/`, `am/am/static/`, `helm/`.                                                         |
| `black`                     | `pyproject.toml`: line length 120, `py312`                            | The Python formatter. Let it reformat.                                                                                                           |
| `flake8`                    | `.flake8`                                                             | pyflakes (F) and pycodestyle (E, W), minus the checks black disagrees with.                                                                      |
| `complexity-new-violations` | `.flake8`'s `max-complexity = 10`                                     | Fails on functions a change makes too complex (C901), compared with HEAD.                                                                        |
| `isort`                     | `pyproject.toml`: `profile = "black"`, 2 lines after imports          | Import order.                                                                                                                                    |
| `autoflake`                 | `--in-place --remove-all-unused-imports --ignore-init-module-imports` | Removes unused imports; skips migrations and keeps `__init__.py` re-exports.                                                                     |
| `bandit`                    | `-ll`                                                                 | Medium and high severity security findings fail.                                                                                                 |
| `pyright-new-errors`        | `pyproject.toml`'s `[tool.pyright]`                                   | Fails on pyright errors a change adds under `am/`, compared with HEAD. Needs Node.js and `venv`.                                                 |
| `pre-commit-hooks`          |                                                                       | Trailing whitespace, end-of-file newline, JSON/TOML/XML/YAML syntax, merge conflicts, symlinks, private keys, AWS credentials, debug statements. |
| `commitlint`                | `commitlint.config.js` (conventional + angular)                       | Checks commit messages, at the `commit-msg` stage. See `am-git-commits`.                                                                         |

pre-commit.ci runs the hooks on pull requests too, except `commitlint` and
`pyright-new-errors`.

### flake8

`.flake8` selects E, W and F, at line length 120, and turns off the
pycodestyle checks that black's output breaks (E203, E501, E701, E704, W503).
Migrations and `__version__.py` are excluded; the settings modules may use star
imports (F403, F405), and `docs/source/conf.py` may import after setting up
Django (E402). **The repository has no flake8 findings: keep it that way.**

```console
git ls-files '*.py' | xargs venv/bin/flake8
```

Fix the cause. A `# noqa` names its code and says why, on code that is right
as it is.

### Complexity and pyright: new findings only

Both have a backlog, so their hooks compare the changed files with the same
files at a base commit and fail only on what the change adds. A backlog
function or error you leave alone passes; one you make worse fails.

```console
python3 -I scripts/complexity_new_violations.py --python venv/bin/python               # changed since HEAD
python3 -I scripts/complexity_new_violations.py --python venv/bin/python --base alpha  # since another commit
python3 -I scripts/pyright_new_errors.py                                               # changed since HEAD
python3 -I scripts/pyright_new_errors.py --base alpha
venv/bin/flake8 --select=C901 am                                                       # the complexity backlog
```

Fix a complexity failure by splitting the function into named steps, not by
raising the limit. Fix a pyright error by narrowing (`is None`, `isinstance`),
correcting the annotation, or declaring the attribute; use `cast()` or
`# pyright: ignore[<rule>]` only with a comment that says why.

`mypy.ini` (django-stubs and pydantic plugins, `check_untyped_defs`) exists
for editors and manual runs; no hook runs mypy.

## How to run

From the repository root, after `make python-init` has created `venv`:

```console
git diff --name-only | xargs venv/bin/pre-commit run --files
git ls-files --others --exclude-standard | xargs venv/bin/pre-commit run --files   # new files
```

- **Use `xargs`.** Under zsh, `pre-commit run --files $FILES` passes the whole
  list as one argument, and pre-commit checks nothing.
- Hooks that modify files (black, isort, autoflake, Prettier, the whitespace
  fixers) fail the first run and pass the second. Run them twice, and read the
  diff of what they changed.
- `pre-commit run --files` runs only the pre-commit stage. `commitlint` runs at
  the commit-msg stage, on the message, when the user commits. Before handing
  over a commit, check both with `skills/am-git-commits/scripts/check-commit.sh`
  (see `am-git-commits`).
- While hooks run at commit time, pre-commit stashes everything unstaged. A
  hook configuration change (`.pre-commit-config.yaml`, `commitlint.config.js`)
  only takes effect in a commit that includes it, or after it is committed.
- `make pre-commit-run` runs every hook on every tracked file: slower, and it
  touches files you didn't change. It skips untracked files.
- `make pre-commit-init` runs `pre-commit autoupdate`, which edits
  `.pre-commit-config.yaml`. That is a commit of its own (`build:` or
  `chore:`), not part of an unrelated change.
- Don't reformat code you didn't otherwise change. It buries the real diff.
