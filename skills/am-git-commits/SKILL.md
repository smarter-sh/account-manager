---
name: am-git-commits
description: Use whenever the user asks you to "write a git commit" (or a commit message, or the git add) in the Account Manager repository. Covers the never-execute rule, authorship, the multiple -m command format, conventional-commit types and scopes (account, api, lib, common, ci, deps, helm, docker, ...), the 72-character header limit, why a ! or BREAKING CHANGE footer is never written, and how thorough the body must be.
---

# Account Manager Git Commits

## The rule: write, never execute

"Write a git commit", in any wording or tone, means **output the command as
text**. It never means run it, however frustrated or emphatic the request.

- Never execute `git commit`, `git add`, `git reset`, `git restore --staged`,
  `git push`, `git tag`, `git stash`, or any other git command that writes. The
  user stages, commits and pushes.
- Read-only commands (`git status`, `git diff`, `git log`) are fine.
- Don't volunteer commit messages. Write one only when asked.

## Authorship

As in smarter-sh/smarter: you are the author, Lawrence McDaniel is the
co-author.

- `--author="Claude <noreply@anthropic.com>"`
- The last `-m` is `Co-authored-by: Lawrence McDaniel <lpm0073@gmail.com>`.

## Command format

Exactly one `git commit` command in one code block:

```console
git commit --author="Claude <noreply@anthropic.com>" \
  -m "<type>(<scope>): <subject>" \
  -m "<body paragraph>" \
  -m "<body paragraph or bullet list>" \
  -m "Co-authored-by: Lawrence McDaniel <lpm0073@gmail.com>"
```

- One `-m` per paragraph; git joins them with blank lines.
- No heredoc, no `-F`, and no `git add` in the same block. When the user asks
  for the `git add` too, write it as a separate block, with explicit paths, and
  leave out files that belong to other work (other agents may be changing this
  tree at the same time).
- No backticks, `$` or `!` inside the double-quoted messages. In zsh a `!` in
  double quotes is history expansion, and the whole command aborts with
  `event not found`. Reword instead.
- Never write a CI skip instruction anywhere in the message, not even to
  describe one (`[skip ci]`, `[ci skip]`, `[no ci]`, `[skip actions]`,
  `skip-checks: true`). GitHub then starts no workflows for the push, and a
  pull request's required Tests never report.

## Subject line

`<type>(<scope>): <subject>`, checked by commitlint (`commitlint.config.js`:
`@commitlint/config-conventional` and `@commitlint/config-angular`) and read by
semantic-release (`release.config.js`) to version the release.

- **type:** `feat`, `fix`, `test`, `docs`, `refactor`, `perf`, `style`,
  `build`, `ci` or `chore`.
  - `feat` is for a truly new feature (a new app, model, api endpoint or
    integration). It cuts a minor release, so it is rare. When in doubt, `fix`.
  - `fix` is a bug fix, including the shortcomings of something that exists.
    It cuts a patch release.
  - `refactor`, `docs`, `test` and `style` cut no release.
  - `chore` for housekeeping; `chore(release): ...` belongs to
    semantic-release, never write it yourself.
- **scope:** the area the change centers on, in lower case: `account`, `api`,
  `lib`, `drf`, `common`, `settings`, `workers`, `tests`, `ci`, `deps`, `helm`,
  `terraform`, `docker`, `docs`, `skills`. Omit it for repository-wide changes.
- **subject:** imperative mood, lower case, no trailing period.
- **length:** the whole header, type and scope included, is **72 characters or
  fewer** (a hard commitlint limit). Measure it, don't count by eye, and aim
  for 70:

  ```console
  printf %s "fix(account): return 404 for an unknown subscription host" | wc -c
  ```

- **Never a `!` or a `BREAKING CHANGE:` footer**, and never the words BREAKING
  CHANGE anywhere in the message. semantic-release turns either one into a new
  major version, whatever the change (`git tag --sort=-v:refname | head -1`
  shows the latest release). Cutting a major release is the
  maintainers' decision, not a side effect of a commit. A change that breaks an
  api client or a deployment keeps its usual type, and its body says what
  breaks and what to do.

## Body

Write for a reader with no context, such as a reviewer six months from now. A
terse four-bullet body is too brief.

- Start with the problem or motivation: what was wrong or missing, and how it
  showed up.
- Then go area by area, a short heading paragraph per area (e.g.
  `Subscription status api (am/am/apps/account/views/...):`), then one bullet
  per change, saying what changed and why.
- Name files, classes, settings and commands precisely.
- Cover the tests: what is new, what it proves, and the coverage.
- Mention any migration and upgrade step.
- End with the status: known skips, pre-existing failures, follow-ups.

## Before writing

1. Run `git status` and `git diff --stat` (and `git diff` on anything unclear),
   so the message describes the working tree, not your memory of it.
2. Ask, or check, which files belong to the commit if that is ambiguous.
3. Measure the header with `wc -c`.
4. Start the response with a one-line `Written for:` audience note.

## Check every commit before handing it over

A commit you write must pass every hook it will meet when the user runs it, or
you haven't finished it. The user runs the commit; the hooks reject it; the user
pays for your unchecked work. So, for each commit, before showing it:

1. Write its message to a file in your scratchpad, exactly as git will build it
   from the `-m` arguments: the header, then each paragraph, separated by blank
   lines, ending with the `Co-authored-by` line.
2. Run, with exactly the pathspecs of the commit's `git add -A`:

   ```console
   skills/am-git-commits/scripts/check-commit.sh <message-file> <pathspec>...
   ```

   It checks that `git add` would accept every pathspec (git refuses the whole
   command when one matches nothing, e.g. a deletion the user already staged),
   runs the pre-commit hooks on the files they cover (twice, since the first
   run may fix them), commitlint on the message with the working tree's
   `commitlint.config.js`, and checks that a changed hook configuration is in
   the commit.

3. Fix whatever fails, in the files or the message, and run it again. Hand over
   only commits that pass.

Three traps this catches:

- **pre-commit stashes unstaged changes while the hooks run.** A fix to
  `.pre-commit-config.yaml` or `commitlint.config.js` is invisible to a commit
  that doesn't include it, so the commit is checked with the old configuration.
  Put such a fix in the first commit of the series.
- **commitlint runs in the commit-msg stage**, which `pre-commit run --files`
  never runs. Checking the files alone says nothing about the message.
- **A retried commit's paths may already be staged.** After a failed attempt, a
  deleted file's deletion is in the index and the path exists nowhere, so
  repeating its `git add` fails. Re-check against the current index before
  handing a commit over again.

When a series has several commits, also say in which order to run them, and why.

For a complete, real example of the format, see
`../smarter/skills/smarter-git-commits/references/canonical-git-commit.md`.
