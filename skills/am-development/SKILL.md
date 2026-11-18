---
name: am-development
description: Start here for any change to the Account Manager repository (the Django account, subscription and payment microservice of the Smarter platform), e.g. a model, view, api route, serializer, Celery task, setting, test, requirement, Helm or Terraform change, or a commit. Gives the non-negotiable rules, the pattern-first workflow, and an index of the narrower am-* skills to load for each kind of work.
---

# Account Manager Development

Account Manager is the account, subscription and payment microservice of the
Smarter platform (smarter-sh/smarter). It is a Django 5 project with Django REST
Framework, django-oscar and dj-stripe, deployed with Helm to the same EKS
cluster as Smarter. A multitenant Smarter platform calls
`GET /accounts/subscription-status/` on the api host, with its platform key
(`Authorization: Platform <key>`, the `PlatformClient` model), to ask whether a
user has an active subscription.

It follows the conventions of smarter-sh/smarter, whose checkout usually sits
next to this one in `../smarter`. When this repository and its skills have no
answer, do what Smarter does (its skills are in `../smarter/skills/`), scaled
down to a much smaller project.

## Repository map

| Path                          | What lives there                                                          |
| ----------------------------- | ------------------------------------------------------------------------- |
| `am/am/apps/account`          | Accounts, users, API keys, payment methods, subscriptions, their api      |
| `am/am/apps/api`              | The api host's urls (`v1/`), OpenAPI views, waffle initialization         |
| `am/am/common`                | The settings model (`conf.py`, `am_settings`), email and logger helpers   |
| `am/am/lib`                   | Framework code: `django/` (middleware, validators, waffle), `drf/`, cache |
| `am/am/lib/unittest`          | `AMTestBase`, the base class of the tests                                 |
| `am/am/settings`              | `base.py`, `local.py`, and one module per cloud environment               |
| `am/am/workers`               | The Celery app (`celery.py`) and Beat (`celerybeat.py`)                   |
| `am/requirements`             | `in/*.in` name the packages; the compiled `*.txt` pin them                |
| `helm/charts/account-manager` | The Helm chart                                                            |
| `terraform/`                  | The AWS resources (ECR, Route53, Kubernetes secrets, ingress)             |
| `docs/source`                 | Sphinx documentation                                                      |
| `.pre-commit-config.yaml`     | The authoritative lint and format standard                                |
| `.github/workflows/`          | Tests (PRs to main), Build, Deploy, Push to main (semantic-release)       |
| `Makefile`                    | Developer commands; a bare `make` prints the menu                         |

Host path `am/am/<path>` is `/home/am_user/am/am/<path>` inside the `am-app`
container, whose working directory, `/home/am_user/am`, holds `manage.py`.

## Non-negotiable rules

1. **Never execute git write commands.** "Write a git commit" means output the
   command text. Never run `git commit`, `git add`, `git reset`, `git push`, or
   anything else that changes the index or history. See `am-git-commits`.
2. **No real infrastructure from tests.** The code reaches AWS (S3, SES and
   other boto3 clients), Stripe and SMTP, and the container's `.env`
   holds real credentials. Patch every such call in tests. Don't run commands
   that write to real infrastructure (`aws`, `terraform apply`, `kubectl
apply`, `helm upgrade`); hand the user the command instead.
3. **Run the tests yourself**, in the containers, after any change, and never
   ask the user to re-run them. Report failures honestly, including
   pre-existing ones. See `am-python-testing` and `am-docker-environment`.
4. **The pre-commit hooks are the lint standard.** flake8 has no findings
   anywhere; pyright and complexity fail only on what a change adds. See
   `am-code-quality`.
5. **Coverage stays at 97% or more** of `am/am` (options in `am/.coveragerc`).
   A change must not lower it.
6. **This repository is public.** No API keys, tokens, account ids, private
   hostnames or customer data in code, tests, docs, commits or skills.
7. **`make run` never returns.** It is `docker compose up`, attached to the
   logs. Start it only with `run_in_background: true`.
8. **No secrets, credentials or PII in log entries.** Log ids and masked
   values, never the value, and never a whole request, settings object or
   exception that may carry one.
9. **Each app keeps a single `0001_initial` migration.** A model change
   regenerates it; Account Manager has no production data yet. See `am-migrations`.
10. **`make docker-init` drops the local `am` database.** Don't run it unless
    the user asks. Bring a database up to date with `python manage.py migrate`.
11. **The host shell is zsh, which doesn't word-split.** A file list in
    `$FILES` reaches a command as one argument. Pipe to `xargs`, or use an
    array. See `am-docker-environment`, "Shell notes".

## Pattern-first workflow

1. Identify the kind of change: a model field, an api view, a serializer, a
   middleware, a Celery task, a management command, a setting, a test module.
2. Find two or three existing implementations of the same kind in this
   repository, and the equivalent in `../smarter` when there is one (much of
   `am/am/lib` was copied from `smarter/smarter/lib`).
3. Read them in full, and copy their structure, naming, docstrings, logging
   (a `WaffleSwitchedLoggerWrapper` where the module has one) and error
   handling. Don't introduce a new pattern when one exists.
4. Call an existing helper rather than writing a second copy of it.
5. Make the change, then add or update its tests and docstrings
   (reStructuredText: `:param:`, `:returns:`, `:raises:`; Sphinx publishes them).
6. Run the tests and the hooks, and fix what they find.

When existing code disagrees with these skills, the newest code that is
consistent with the rest of the repository wins. Say so in your summary.

Other agents may be editing this working tree at the same time. Touch only the
files your task needs, and don't revert changes you didn't make.

## Which skill to load

| Task                                                              | Skill                   |
| ----------------------------------------------------------------- | ----------------------- |
| Writing, fixing or running unit tests; coverage                   | `am-python-testing`     |
| Running anything in the containers; syncing edits; the database   | `am-docker-environment` |
| A model change and its migration                                  | `am-migrations`         |
| Lint, format, pre-commit, flake8, pyright, complexity             | `am-code-quality`       |
| Writing a commit message                                          | `am-git-commits`        |
| Creating or describing a pull request                             | `am-pull-requests`      |
| A failed GitHub Actions run, or a run url                         | `am-ci-failures`        |
| Anything these don't cover (docs, logging, typing, url names ...) | `../smarter/skills/`    |

## Definition of done

- The change follows an existing pattern.
- Tests cover it, you ran them in a container, and coverage is still 97% or
  more.
- The pre-commit hooks pass on the changed files.
- No new or changed log call writes a secret, credential or PII.
- Your summary says what changed, what you verified, and what you skipped.
