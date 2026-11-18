# Account Manager

![Build Status](https://github.com/smarter-sh/account-manager/actions/workflows/build.yml/badge.svg?branch=main)
![Test Status](https://github.com/smarter-sh/account-manager/actions/workflows/test.yml/badge.svg?branch=main)
![Release Status](https://github.com/smarter-sh/account-manager/actions/workflows/deploy.yml/badge.svg?branch=main)
[![Python coverage](https://img.shields.io/codecov/c/github/smarter-sh/account-manager/main?flag=python&label=Python%20coverage&logo=codecov)](https://codecov.io/gh/smarter-sh/account-manager?flags%5B0%5D=python)
[![Latest Release](https://img.shields.io/github/v/release/smarter-sh/account-manager?label=release)](https://github.com/smarter-sh/account-manager/releases)

Account user and payment management microservice for Smarter.

## Usage

A multitenant Smarter platform asks, when a user signs in, whether the user has an
active subscription. The platform identifies itself with its platform key, and the
user by username and email address:

```console
curl https://api.am.smarter.sh/accounts/subscription-status/ \
  -H 'Authorization: Platform <the platform key>' \
  -H 'X-Client-Username: <username>' \
  -H 'X-Client-Email: <email>'
```

It answers 200 (`{"active": true, "plan_type": "multitenant", "end_date": "..."}`)
when the user belongs to an active MULTITENANT subscription, and 403 otherwise. An
operator registers each platform, and gets its key (shown once), with:

```console
docker exec am-app python manage.py create_platform_api_key --host alpha.platform.smarter.sh
```

The platform stores the key in its `SMARTER_ACCOUNT_MANAGER_API_KEY` setting. Once
every platform sends its key, turn on the `require_platform_key` waffle switch, and
requests without a key are refused.

## Development

```console
make init       # venv, Docker images, database, pre-commit hooks
make run        # the app at http://localhost:8000/ (docker compose up; doesn't return)
make test       # the unit tests, in the am-app container
make coverage   # the unit tests under coverage.py, with a line-by-line report
make help       # every command
```

Unit tests run in the `am-app` container against MySQL and Redis. The
[Tests workflow](.github/workflows/test.yml) runs them under coverage on every
pull request to `main`, and uploads the report to
[Codecov](https://codecov.io/gh/smarter-sh/account-manager), which the coverage
badge above shows. The target is at least 97% line coverage of `am/am`.

## Support

Please report bugs to the [GitHub Issues Page](https://github.com/smarter-sh/account-manager/issues) for this project.
