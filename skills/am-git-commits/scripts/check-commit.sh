#!/usr/bin/env bash
#------------------------------------------------------------------------------
# Check a commit before handing it to the user: every hook it will meet.
#
#   skills/am-git-commits/scripts/check-commit.sh <message-file> <pathspec>...
#
# <message-file> is the commit message as git will build it from the -m
# arguments: the header, then each -m paragraph, separated by blank lines.
# <pathspec>... are exactly the pathspecs of the commit's git add -A.
#
# It runs, without staging or committing anything:
#   0. a check that git add would accept every pathspec: git refuses the whole
#      command when one matches nothing in the index or the working tree, e.g. a
#      deleted folder whose deletion is already staged,
#   1. the pre-commit hooks on those files (twice: the first run may fix files),
#   2. commitlint on the message, with the working tree's commitlint.config.js,
#   3. a check that a changed hook configuration (.pre-commit-config.yaml,
#      commitlint.config.js) is in the commit. pre-commit stashes unstaged
#      changes while hooks run, so an unstaged config fix is invisible to the
#      very commit that needs it.
#
# Exit 0 when everything passes. Never hand over a commit that fails here.
#------------------------------------------------------------------------------
set -uo pipefail

cd "$(git rev-parse --show-toplevel)"
message="$1"
shift
status=0

if [ ! -s "$message" ]; then
  echo "usage: $0 <message-file> <file>..." >&2
  exit 2
fi
header="$(head -1 "$message")"
length=${#header}
echo "header ($length characters): $header"

# 0. every pathspec must match something in the index or the working tree, or git add fails
for spec in "$@"; do
  if [ -z "$(git ls-files --cached --others --exclude-standard -- "$spec" | head -1)" ]; then
    echo "FAIL: git add would refuse pathspec '$spec': it matches nothing in the index or working tree." >&2
    echo "      (Already staged, e.g. a staged deletion? Then leave it out of the git add.)" >&2
    status=1
  fi
done

# the commit's files: everything git status reports under the pathspecs, staged or not
files=()
while IFS= read -r line; do
  files+=("${line:3}")
done < <(git status --porcelain --untracked-files=all -- "$@")
set -- "${files[@]}"

# 3. hook configuration that the commit depends on but doesn't include
for config in .pre-commit-config.yaml commitlint.config.js; do
  if ! git diff --quiet HEAD -- "$config" 2>/dev/null; then
    included=no
    for f in "$@"; do [ "$f" = "$config" ] && included=yes; done
    if [ "$included" = no ]; then
      echo "FAIL: $config has uncommitted changes, but isn't in this commit's files." >&2
      echo "      pre-commit stashes it while the hooks run, so this commit is checked with the old one." >&2
      status=1
    fi
  fi
done

# 1. the pre-commit stage hooks, on the commit's files that exist (a deleted file has nothing to check)
existing=()
for f in "$@"; do [ -f "$f" ] && existing+=("$f"); done
if [ "${#existing[@]}" -gt 0 ]; then
  venv/bin/pre-commit run --files "${existing[@]}" > /dev/null 2>&1
  if ! venv/bin/pre-commit run --files "${existing[@]}"; then
    echo "FAIL: pre-commit hooks fail on the commit's files (see above)." >&2
    status=1
  fi
fi

# 2. commitlint, as the commit-msg hook runs it, but with the working tree's config
commitlint="$(ls -t "$HOME"/.cache/pre-commit/repo*/node_env-*/bin/commitlint 2>/dev/null | head -1)"
if [ -z "$commitlint" ]; then
  venv/bin/pre-commit install-hooks > /dev/null 2>&1
  commitlint="$(ls -t "$HOME"/.cache/pre-commit/repo*/node_env-*/bin/commitlint 2>/dev/null | head -1)"
fi
if [ -z "$commitlint" ]; then
  echo "FAIL: commitlint's hook environment isn't installed (venv/bin/pre-commit install-hooks)." >&2
  status=1
else
  node_env="$(dirname "$(dirname "$commitlint")")"
  if PATH="$node_env/bin:$PATH" NODE_PATH="$node_env/lib/node_modules" "$commitlint" --edit "$message"; then
    echo "commitlint: passed"
  else
    echo "FAIL: commitlint rejects the message." >&2
    status=1
  fi
fi

exit $status
