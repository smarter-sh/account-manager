---
name: am-migrations
description: Use when an Account Manager Django model changes (a field, a choices list, an index, a new model) in the account app (am/am/apps/account) or the drf app (am/am/lib/drf), and a migration is needed, or when makemigrations --check reports missing migrations. Covers why each app keeps a single regenerated 0001_initial (Account Manager has no production data yet), regenerating it in a container, resetting the local database, and verifying.
---

# Account Manager Migrations

Account Manager has never been used in production, so no database holds data
that its migrations must carry forward. As in smarter-sh/smarter before a
release, each app with migrations, `account` (`am/am/apps/account/migrations/`)
and `drf` (`am/am/lib/drf/migrations/`), keeps **a single `0001_initial.py`**,
regenerated whenever its models change, rather than a growing chain of
migrations.

This changes once Account Manager has a production database: from then on, its
migrations are append-only (a new migration per change, never an edited one).
Update this skill and `CLAUDE.md` when that happens.

## Regenerate 0001_initial

Delete the app's migrations, regenerate them from the models with the host's
tree mounted in a throwaway container (as `scripts/docker-test.sh` does), and
check that nothing is missing:

```console
rm am/am/apps/account/migrations/0*.py
docker run --rm --network account-manager_default --env-file .env \
  -v "$PWD/am:/home/am_user/am" -w /home/am_user/am am \
  bash -c "python manage.py makemigrations account && python manage.py makemigrations --check --dry-run"
```

The new file lands in `am/am/apps/account/migrations/0001_initial.py` on the
host. A test run creates its database from scratch, so the tests need nothing
else.

## Reset the local database

The local `am` database (in `mariadb-data/`) recorded the old migrations, and its
tables have the old schema, so it no longer matches. Rebuild it with
`make docker-init`, which drops and recreates the `am` database, then migrates
and initializes it. It deletes the local data, so ask the user before running
it.

## Verify

```console
# no model change without a migration
docker exec am-app bash -c "python manage.py makemigrations --check --dry-run"
```

Then run the tests (`am-python-testing`), and mention in the commit body
(`am-git-commits`) that the migrations were regenerated and that local
databases need `make docker-init`.
