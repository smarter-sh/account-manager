---
name: am-migrations
description: Use when an Account Manager Django model changes (a field, a choices list, an index, a new model) in the account app (am/am/apps/account) or the drf app (am/am/lib/drf), and a migration is needed, or when makemigrations --check reports missing migrations. Covers why migrations are append-only, generating one in the am-app container, copying it out, data migrations for existing rows, and verifying.
---

# Account Manager Migrations

The apps with migrations, `account` (`am/am/apps/account/migrations/`) and
`drf` (`am/am/lib/drf/migrations/`), are deployed with production data. So
their migrations are **append-only**: never edit, delete, squash or regenerate
a migration that is on `main`. A production database has already applied it,
and Django won't run a changed one again. Every schema change is a new
migration that runs unattended on that database during a deployment.

## Add a migration

Generate it in the `am-app` container, after your model change has reached it
(see `am-docker-environment`), then copy it to the host:

```console
docker exec am-app bash -c "python manage.py makemigrations account --name <what_it_does>"
docker cp am-app:/home/am_user/am/am/apps/account/migrations/<NNNN>_<what_it_does>.py am/am/apps/account/migrations/
docker exec am-app bash -c "python manage.py migrate"
```

- Name it after what it does (`0003_subscription_comment.py`), not the
  default `auto_<timestamp>`.
- If `makemigrations` fails with a permission error, the migrations folder
  holds files you copied in as root:
  `docker exec -u root am-app chown -R am_user /home/am_user/am/am/apps/account/migrations`.
- A migration on `alpha` that isn't on `main` yet may still be replaced, if
  nothing but local databases have applied it. Ask first.

## Existing rows

A required field on a table with rows needs a default, or three steps: add it
as nullable, fill it with `migrations.RunPython(forward, reverse)`, then
`AlterField` it to its final form. In `RunPython`, use
`apps.get_model("account", "<Model>")`, never an import of the real model, and
give it a real reverse function, or `migrations.RunPython.noop` explicitly.
Changing a field's `choices` needs an `AlterField` migration too.

## Verify

```console
# no model change without a migration
docker exec am-app bash -c "python manage.py makemigrations --check --dry-run"
# backward to the previous migration, then forward again
docker exec am-app bash -c "python manage.py migrate account <previous> && python manage.py migrate account"
```

Never `make docker-init` to get a clean database: it drops the local `am`
database. Then run the app's tests (`am-python-testing`), and mention the
migration in the commit body (`am-git-commits`) and the pull request's
Breaking Changes section.
