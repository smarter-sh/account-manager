---
name: am-ci-failures
description: Use when the user gives a GitHub Actions run or job url for smarter-sh/account-manager (github.com/smarter-sh/account-manager/actions/runs/<id>, optionally /job/<id>) or says a workflow, test run, CI check or pull request check failed, e.g. "the Tests check failed on the alpha PR", "Push to main failed", "semantic-release says the token is invalid". Covers downloading the failed jobs' logs with the bundled script, reading the failures, what each workflow does (Tests, Build, Deploy, Push to main, pre-commit Version Bumps), the repository secret that shadows a rotated organization secret, reproducing a test failure locally, and reporting.
---

# Investigating a Failed GitHub Actions Run

The user can't always read a run's logs: GitHub's download often fails in the
browser, and a log can be very long. Give them the cause, not the log.

## 1. Download and extract the failures

```console
skills/am-ci-failures/scripts/fetch-run-logs.sh <run url | job url | run id> [output dir]
```

Use your scratchpad as the output dir. The repository defaults to
smarter-sh/account-manager, and a url names its own. The script prints the
run's workflow, event, branch, commit and message (so you know which code ran),
every job and its conclusion, and for each failed job (or only the job of a job
url) its Python unittest `FAIL`/`ERROR` blocks, the `Ran N tests` /
`FAILED (...)` summary and the `##[error]` lines. It writes `<job id>.log`
(the whole log, colors stripped) and `<job id>.failures.txt`.

It works around what goes wrong by hand: it retries GitHub's 502 and 503
answers (often why the user's own download failed), passes
`--allow-escape-sequences` so `gh` prints a log with color codes, and uses
`gh`'s login, or `GH_TOKEN`/`GITHUB_TOKEN` from the environment or `.env`.

When the failures file is empty, read the end of the log and the failed
step's `##[error]` lines.

## 2. Know what failed

| Workflow (file)                                        | Runs on                               | What it does                                                                                                 |
| ------------------------------------------------------ | ------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Tests (`test.yml`)                                     | PRs to `main`, push to `main`, manual | One job, `python`: runs the unit tests under coverage and uploads `coverage.xml` to Codecov (`codecov.yml`). |
| Build (`build.yml`)                                    | Manual, on alpha/beta/next/main       | Builds the image and pushes it to ECR (`.github/actions/build`).                                             |
| Deploy (`deploy.yml`)                                  | Manual, on alpha/beta/next/main       | Deploys with Helm to EKS (`.github/actions/deploy`), then sends an email.                                    |
| Push to main (`pushMain.yml`)                          | Push to `main`                        | semantic-release cuts the release (`release.config.js`), then merges `main` into the other branches.         |
| pre-commit Version Bumps (`precommitVersionBumps.yml`) | Weekly cron, manual                   | `pre-commit autoupdate`, committed and pushed to `alpha`.                                                    |
| Auto Assign (`auto-assign.yml`)                        | New issues and pull requests          | Assigns them.                                                                                                |

The Tests workflow is new, and may not be on every branch yet. Its `python`
job builds the `am` image with `ENVIRONMENT=local`, writes a `.env` from
`.env.example` with placeholder credentials (so an unmocked outside call fails
there, rather than reaching a real service), starts `am-mariadb` and `am-redis`,
then runs `migrate` and `coverage run manage.py test am` in `am-app`. A log
with no `Ran N tests` line failed before the tests ran: read the build, the
MySQL wait and the migration. The Codecov upload has `fail_ci_if_error: false`,
so a Codecov problem shows as a missing report or badge, not a failed check.
The job's last step prints the MySQL and Redis logs on failure.

### A token that "doesn't work" after it was rotated

Push to main and pre-commit Version Bumps push with the `PAT` secret, and
Tests uploads with the organization's `CODECOV_TOKEN`. GitHub
resolves a secret name **repository first, then organization**: a stale
repository-level `PAT` shadows the organization's, so rotating the
organization secret changes nothing while the repository copy exists. The
symptom is an authentication failure (`Bad credentials`, 401, semantic-release's
`EINVALIDGHTOKEN` or `EGITNOPERMISSION`, `remote: Invalid username or password`)
right after a rotation. Compare the two lists (names and dates only):

```console
gh secret list -R smarter-sh/account-manager
gh secret list --org smarter-sh
```

If the same name is in both, the fix is the user's: delete the repository
copy (`gh secret delete PAT -R smarter-sh/account-manager`), or update it.
Hand them the command; never run a secret write yourself, and never print a
secret's value.

## 3. Is it new?

Compare the run's commit with the working tree (`git log --oneline -5`,
`git show --stat <sha>`).

- A failure in code that a later commit, or the working tree, already changed
  may be fixed: run the test on the current code first.
- A test that fails on a commit that didn't touch it is often a stale
  expectation; `git log -S'<text>'` finds the commit that changed it.
- A test that passes locally and failed once in CI may be flaky. Say so, with
  the evidence, rather than "fixing" a test that isn't broken.

## 4. Reproduce, fix, verify

Run the failed test by its dotted name against the host's tree (see
`am-python-testing`):

```console
scripts/docker-test.sh am.apps.account.tests.test_api
```

Then its whole package, and the pre-commit hooks on the files you changed
(`am-code-quality`). A coverage failure: `COVERAGE=1 scripts/docker-test.sh`.

## 5. Report

Lead with the cause in one sentence: which workflow and job, which test or
step, why, and whether it is new or pre-existing. Then the fix and how you
verified it. Don't paste the log; the failures file's path is enough. Never
push, re-run a workflow or change a secret: give the user the commit command
(`am-git-commits`) or the `gh` command, and say that the next push re-runs the
checks.
