# CLAUDE.md

Guidance for Claude Code (and other coding agents) working in this repository.

Account Manager is the account, subscription and payment microservice of the
Smarter platform (smarter-sh/smarter). It is a Django 5 project with Django REST
Framework, django-oscar and dj-stripe, deployed with Helm to the same EKS
cluster as Smarter. Smarter's deployments ask it, for example, whether a user's
subscription on a hosted platform is active
(`GET /accounts/subscription-status/` on the api host).

Detailed know-how lives in the Agent Skills under `skills/` (symlinked to
`.claude/skills`). **Load `am-development` first for any change.** Its table
says which narrower `am-*` skill covers each kind of work. This file holds only
what applies to nearly every task. The repository follows the conventions of
smarter-sh/smarter (a checkout usually sits next to this one, in `../smarter`);
when this repository has no answer, copy what Smarter does.

## Hard rules

1. **Never run git write commands.** "Write a git commit" means print the
   command as text. Never run `git commit`, `git add`, `git reset`, `git push`
   or anything else that changes the index or history. Format and authorship
   are in `am-git-commits`.
2. **No real services from tests.** The code calls Stripe, SMTP (the
   email helper), boto3 (AWS credentials, S3 storage) and outbound HTTP, and
   the local `.env` holds live credentials. Patch every one of those calls in
   tests. Don't run commands that write to real
   infrastructure (`aws`, `terraform apply`, `kubectl apply`); hand the user
   the command instead.
3. **Run the tests yourself**, in the `am-app` container, after any change.
   Never ask the user to re-run them. Report failures honestly, including
   pre-existing ones.
4. **The pre-commit hooks are the lint standard** (black, flake8, isort,
   autoflake, bandit, pyright and complexity on new findings only, codespell,
   pyupgrade, pydocstringformatter, Prettier). flake8 (pyflakes and
   pycodestyle) has no findings anywhere.
5. **Coverage: at least 97%** of `am/am` (the options are in
   `am/.coveragerc`). A change must not lower it.
6. **This repository is public.** No API keys, tokens, account IDs, private
   hostnames or customer data in code, tests, docs or skills.
7. **`make run` never returns.** It is `docker compose up`, attached to the
   logs. Start it only with `run_in_background: true`.
8. **No secrets, credentials or PII in log entries.** Log ids and masked
   values, never the value.
9. **Migrations are append-only.** The app is deployed with production data:
   add a new migration (`makemigrations` in the container, then copy it out);
   never edit, delete or regenerate one that is on `main`.
10. **`make docker-init` drops the local `am` database.** Don't run it unless
    the user asks. To bring a database up to date, run `migrate`.

## Repository map

| Path                          | Contents                                                                          |
| ----------------------------- | --------------------------------------------------------------------------------- |
| `am/am/apps/account`          | Accounts, contacts, users, API keys, payment methods, subscriptions, the api      |
| `am/am/apps/api`              | The api host's urls, OpenAPI views, waffle initialization                         |
| `am/am/common`                | Settings model (`conf.py`, `am_settings`), email, console, logging helpers        |
| `am/am/lib`                   | Framework code: django (middleware, validators, waffle), drf (auth tokens), cache |
| `am/am/settings`              | Django settings: `base.py`, `local.py`, and one module per cloud environment      |
| `am/requirements`             | `in/*.in` name the packages (no version pins); the compiled `*.txt` pin them      |
| `helm/charts/account-manager` | The Helm chart                                                                    |
| `terraform/`                  | The AWS resources (ECR, Route53, Kubernetes secrets, ingress)                     |
| `skills/`                     | Agent Skills for developing this repository                                       |
| `.github/workflows/`          | Tests (PRs to main), Build, Deploy, Push to main (semantic-release)               |

## Containers

Services in `docker-compose.yml`: `am-app` (gunicorn on `localhost:8000`),
`am-worker`, `am-beat`, `am-mysql` (MySQL 8, user `am`, password `am`),
`am-redis`.

- The image holds a copy of `am/` at `/home/am_user/am` (the compose bind mount
  at `/am` is not on the app's path). To test host edits without rebuilding,
  use `scripts/docker-test.sh`, which mounts the host's `am/` into a throwaway
  container (concurrent runs: give each its own `AM_TEST_DATABASE_NAME`). To
  update the running app, `make build` and `docker compose up -d`.
- `smarter-mariadb` (from the smarter repository) also binds host port 3306.
  Stop it before `docker compose up`.

## Common commands

```bash
# Python tests, in the container. Celery Beat is stopped while they run.
make test
scripts/docker-test.sh am.apps.account              # the host's tree, in a throwaway container
COVERAGE=1 scripts/docker-test.sh                   # ... under coverage, with a report
make coverage                                       # report in the terminal, and coverage.xml

# Lint changed files (zsh doesn't word-split $FILES, so use xargs)
source venv/bin/activate && git diff --name-only | xargs pre-commit run --files

# Requirements: edit am/requirements/in/*.in, then recompile the pins
make python-requirements
```

## Conventions

- **Pattern first.** Find two or three existing implementations of the same
  kind of change, read them in full, and copy their structure, naming,
  docstrings, logging and error handling.
- **Tests:** one test module per source module, under the package's `tests/`;
  follow the base class of the module you're in (`AMTestBase`, which has no
  transaction rollback, so delete what you create; `TestAccountMixin` for an
  account and users), and prefer Django's `TestCase` in a new module that
  touches the database; test data as YAML under `tests/data/`. See `am-python-testing`.
- **Docstrings** are reStructuredText (`:param:`, `:returns:`, `:raises:`);
  Sphinx autodoc publishes them.
- **Commits** are conventional commits; semantic-release versions the project
  from them (`release.config.js`). Never write a `!` or a `BREAKING CHANGE:`
  footer: either one cuts a new major version, which is the maintainers'
  decision. Describe a breaking change and its upgrade steps in the body.

## Definition of done

- The change follows an existing pattern.
- Tests cover it, and you ran them in the container; coverage is still at
  least 97%.
- Pre-commit hooks pass on the changed files.
- Your summary says what changed, what you verified, and what you skipped.
