---
name: am-pull-requests
description: Use when asked to create, open, write or update a GitHub pull request in the Account Manager repository (smarter-sh/account-manager), e.g. "create a PR for these commits", "open the alpha to main pull request", or "write the PR description". Covers the branches (usually alpha into main), the title, filling in every section of .github/PULL_REQUEST_TEMPLATE.md from the commits' own messages, creating it with gh pr create --body-file, and what never to do (push, merge, or leave the template's placeholders in).
---

# Account Manager Pull Requests

Every pull request uses the template in `.github/PULL_REQUEST_TEMPLATE.md`.
GitHub pre-fills it in the browser, but `gh pr create --body-file` doesn't.
Fill in every section, from the commits themselves.

## Rules

- **Create one only when asked.** A pull request is public and notifies
  people. Writing the description as text, when that is all that was asked, is
  fine.
- **Never push, merge, or change a branch.** The user pushes. `gh pr create`
  only opens a pull request for commits already on GitHub. If the head branch
  is behind the local one, or not pushed, say so and stop.
- **Never leave a placeholder.** Each section gets real content, or `None.`.
- **The repository is public.** No credentials, account ids, private
  hostnames, customer data or personal details.
- **No bare `@name`** unless it is a real GitHub login you mean to notify.
- **No CI skip instruction**, not even to describe one (see `am-git-commits`).

## Branches and title

- The usual pull request is **`alpha` into `main`**: everything on `alpha`
  since the last release. Merging it starts the Push to main workflow, whose
  semantic-release cuts the release. Title: `Alpha - <summary>`, naming the
  one or two most important changes, under about 100 characters.
- A feature branch goes into `alpha`, titled with its main commit's subject.
- Check first that one isn't open already:
  `gh pr list --repo smarter-sh/account-manager --head <branch> --state open`.
  If one is, update it (`gh pr edit <number> --body-file ...`) rather than open
  another.

## Gather the material

```bash
git fetch origin main alpha
git status -sb                                                 # ahead of origin? then stop
git log --oneline origin/main..origin/alpha                    # the commits
git log --format='### %h %s%n%n%b' origin/main..origin/alpha   # their full messages
git diff --stat origin/main...origin/alpha | tail -1           # files, additions, deletions
```

Leave out `chore(release): ...` and merge commits, but read a merged pull
request for the issue it fixed. Many commits on `alpha` are Dependabot's
`chore(deps): ...` bumps: group them in one subsection. Read every other
commit's body; build the description from them, never from memory. For each
issue a commit names, check its state:
`gh issue view <n> --repo smarter-sh/account-manager --json state,title`.

## Fill in the template

Keep the template's headings and order (`# Pull Request Template` included),
and drop its `<!-- ... -->` hints and `_placeholder_` lines.

- **Type of Change.** Check (`- [x]`) each box a commit's type earns:
  `feat` New feature, `fix` Bug fix, `docs` Documentation, `refactor`
  Refactor, and `ci`, `build`, `chore`, `test` Chore.
- **Resolves.** One `- Fixes #<n>` per issue (GitHub closes them when the
  pull request merges into `main`); note one that is already closed. With no
  issue, list each problem the pull request resolves, one bullet each, with
  its commit's short hash. `- None.` only when it resolves no problem.
- **Changes.** One or two sentences on the whole, then a `###` subsection per
  commit, most important first, titled with its subject and short hash: the
  problem in a sentence or two, then bullets naming files and classes.
  Condense the body, don't paste it.
- **Testing.** What was run and where (`scripts/docker-test.sh`, the `am-app`
  container, the coverage figure), per commit, with the numbers the commits
  report; then what still needs testing. Never claim a test no commit reports.
- **Screenshots.** Only for a visible change to a page. Otherwise
  `None: no visible change.`
- **Dependencies.** Changed requirements (`am/requirements/`) or npm
  packages, new settings, secrets or environment variables a deployment
  needs, and pull requests that must merge first. Otherwise `None.`
- **Breaking Changes.** Anything that changes for an api client (such as
  Smarter's calls to the subscription-status api), a deployment, the Helm
  chart, a workflow, or the database (migrations). Otherwise `None.`

End the description with the attribution line from the conversation's system
context, if there is one.

## Create it

Write the description to a file in your scratchpad, not inline: backticks, `$`
and `#` break shell quoting.

```bash
gh pr create --repo smarter-sh/account-manager --base main --head alpha \
  --title "Alpha - <summary>" --body-file <scratchpad>/pr-body.md
```

If `gh` answers 401, it has no login: ask the user to provide a token in
`GH_TOKEN` rather than pasting one into the conversation. Give the user the
pull request's url, and say what you left out or couldn't verify.
