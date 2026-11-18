---
name: am-python-testing
description: Use when writing, fixing or running Account Manager's Django unit tests, or raising coverage, e.g. "add tests for the subscription-status view", "this test fails", "coverage dropped below 97%". Covers where tests run (scripts/docker-test.sh, the am-app container, make test), AM_TEST_DATABASE_NAME for concurrent runs, coverage (make coverage, COVERAGE=1, am/.coveragerc, the 97% target), test layout, the shared helpers (AMTestBase, TestAccountMixin, the account factories), cleanup without transaction rollback, and mocking Stripe, SMTP, boto3 and outbound HTTP.
---

# Account Manager Python Testing

## Where tests run

Tests run in Docker, against the `am-mariadb` and `am-redis` containers. The host
has no runnable test environment. Two ways, both from the repository root:

```console
# The host's working tree, in a throwaway container of the am image. No sync needed.
scripts/docker-test.sh                                    # every test
scripts/docker-test.sh am.apps.account.tests.test_user    # a module, class or method

# The code inside am-app (sync your edits first: see am-docker-environment)
docker exec am-app bash -c "python manage.py test am.apps.account"
make test                                                 # = make docker-test: the whole suite
```

**Prefer `scripts/docker-test.sh`.** It mounts the host's `am/` over
`/home/am_user/am`, so your edits are tested at once, without a rebuild or a
`docker cp`. It needs the `am` image (`make build`) and `am-mariadb` and
`am-redis` running (`docker compose up -d`), on the `account-manager_default`
network. It reads `.env`, as the containers do.

- **Concurrent runs need their own test database.** Each run creates and drops
  its test database (`test_am` by default, set in `settings/base.py` from
  `AM_TEST_DATABASE_NAME`), so two runs with the same name destroy each other's
  tables. Other agents may be running tests too: give yours a name of its own.

  ```console
  AM_TEST_DATABASE_NAME=test_am_2 scripts/docker-test.sh am.lib
  ```

- `make test` and `make coverage` stop `am-beat` while they run, and start it
  again afterwards. `scripts/docker-test.sh` doesn't touch the containers.
- Run the modules you touched while iterating, then the whole suite once
  before you finish. Run long suites in the background, with the output saved
  to a file in your scratchpad, and read the `Ran N tests` and `OK` /
  `FAILED (...)` lines at the end. Grep a saved log with `grep -a`: colored
  output makes grep call it binary.

## Coverage

**Target: at least 97% of `am/am`.** A change must not lower it.

```console
make coverage                                  # in am-app: report in the terminal, and coverage.xml
COVERAGE=1 scripts/docker-test.sh              # the host's tree, with a report
COVERAGE=1 AM_TEST_DATABASE_NAME=test_am_3 scripts/docker-test.sh am.apps.account
```

`am/.coveragerc` holds the options: the source is `am/`, and it omits
`**/tests/*`, `**/migrations/*`, `am/settings/*`, `am/asgi.py` and `am/wsgi.py`,
and lines marked `pragma: no cover` or under `if TYPE_CHECKING:`. Don't add a
`pragma: no cover` to reach the number; test the code. `COVERAGE=1` writes its
data to `am/.coverage.<test database name>`.

To raise coverage, rank the modules of `coverage report -m` by missed lines,
and test them through their public interface: the view, the serializer, the
task function, the management command.

## Layout and conventions

- **One test module per source module**, in the package's `tests/` folder:
  `am/am/lib/drf/tests/test_middleware.py` tests `am/am/lib/drf/middleware.py`.
- **Test data is YAML** (or JSON) in that folder's `tests/data/`, e.g.
  `am/am/lib/drf/tests/data/auth-token.yaml`, read with
  `get_readonly_yaml_file()`, not inline dicts.
- One class per module, with shared fixtures built once in `setUpClass`.
  Mutating tests use throwaway objects plus `addCleanup`.
- Test names say what is being proven. Give each a one-line docstring when the
  name alone isn't enough.
- CLAUDE.md asks for Django's `TestCase` (transaction rollback) for a test
  that touches the database. The existing modules use `AMTestBase` and
  `TestAccountMixin` instead (see below). In a module you extend, follow the
  module; in a new one, prefer `django.test.TestCase` unless you need the
  account fixtures.

## Shared helpers

| Helper                       | Module                                  | Gives you                                                                                                                                                           |
| ---------------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AMTestBase`                 | `am/am/lib/unittest/base_classes.py`    | A plain `unittest.TestCase` with `hash_suffix`, `name`, `uid`, YAML/CSV/JSON readers, `generate_hash_suffix()`, `create_generic_request()`                          |
| `TestAccountMixin`           | `am/am/apps/account/tests/mixins.py`    | `account`, `admin_user`, `user_profile`, `non_admin_user`, `non_admin_user_profile`, created in `setUpClass`, deleted in `tearDownClass`                            |
| `AccountTestCase`            | `am/am/apps/account/tests/mixins.py`    | Django `TestCase` (transaction rollback), a per-process LocMem cache, and `EmailHelper.send_email` patched as `self.send_email`: the default for new database tests |
| `admin_user_factory()`       | `am/am/apps/account/tests/factories.py` | A superuser, an `Account` (or the one you pass) and a `UserProfile` with `is_test=True`: returns `(user, account, user_profile)`                                    |
| `mortal_user_factory()`      | same                                    | The same, for a user who is neither staff nor superuser                                                                                                             |
| `factory_account_teardown()` | same                                    | Deletes the profile, user and account you give it, ignoring the ones already gone                                                                                   |
| `payment_method_factory()`   | same                                    | A `PaymentMethod` with a fake `stripe_id`; `payment_method_factory_teardown()` deletes it                                                                           |
| `billing_address_factory()`  | same                                    | A billing address dict                                                                                                                                              |

These files change; read them before relying on a signature.

## Things that will bite you

- **No transaction rollback in `AMTestBase`.** It is a plain
  `unittest.TestCase`: whatever a test creates stays in the test database
  until it is deleted, and `transaction.on_commit` callbacks run at once.
  Delete explicitly in `tearDownClass` or with `addCleanup`.
- **`admin_user` is a superuser.** Permission queries return everything for a
  superuser. Use `non_admin_user` to prove that access is refused.
- **Celery is not eager.** `.delay()` sends the task to the `am-worker`
  container, which uses the `am` database, not the test database. Call the
  task function directly, or patch it where the code under test imports it.
- **Patch where the name is looked up**, e.g.
  `patch("am.common.helpers.email_helpers.smtplib.SMTP")`, not
  `patch("smtplib.SMTP")`.

## Mock every outside service

The containers read `.env`, which holds **real** credentials (SMTP, and
any AWS or Stripe keys a developer adds), so an unpatched call
sends real email, or reaches a real cloud or
payment account. Every test patches:

- **Stripe** (dj-stripe and the `stripe` package): fake ids such as
  `stripe_id="test-stripe-id"` on the model rows, and patched api calls. Never
  call Stripe's api, test mode included.
- **SMTP**: `am.common.helpers.email_helpers` (`EmailHelper`); patch
  `am.common.helpers.email_helpers.smtplib.SMTP`, as
  `am/am/common/helpers/tests/test_email_helper.py` does.
- **boto3**: any client or `boto3.Session` (e.g. in `am/am/common/conf.py`).
- **Outbound HTTP**: `requests`, `httpx`, `urllib`; patch the call, or the
  helper that makes it.

If a test seems to need the real service, stop and ask the user.

## Reporting

Report the pass, fail, error and skip counts honestly. Name pre-existing
failures, and separate them from anything your change caused; confirm
"pre-existing" by running the test on unchanged code, don't assume it.
