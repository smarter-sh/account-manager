# Smarter Account Manager

![Build Status](https://github.com/smarter-sh/account-manager/actions/workflows/build.yml/badge.svg?branch=main)
![Test Status](https://github.com/smarter-sh/account-manager/actions/workflows/test.yml/badge.svg?branch=main)
![Release Status](https://github.com/smarter-sh/account-manager/actions/workflows/deploy.yml/badge.svg?branch=main)
[![Python coverage](https://img.shields.io/codecov/c/github/smarter-sh/account-manager/main?flag=python&label=Python%20coverage&logo=codecov)](https://codecov.io/gh/smarter-sh/account-manager?flags%5B0%5D=python)
[![Latest Release](https://img.shields.io/github/v/release/smarter-sh/account-manager?label=release)](https://github.com/smarter-sh/account-manager/releases)
![Auto Assign](https://github.com/smarter-sh/account-manager/actions/workflows/auto-assign.yml/badge.svg)<br>
[![hack.d Lawrence McDaniel](https://img.shields.io/badge/hack.d-Lawrence%20McDaniel-orange.svg)](https://lawrencemcdaniel.com)

Account user and payment management microservice for Smarter.

## Usage

See https://docs.am.smarter.sh for User and Administration Guides.

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

## Developer Quickstart

This is the local Docker startup. Smarter Account Manager runs on Linux, Windows and macOS.

1. Verify project requirements: [Python 3.14](https://www.python.org/), [Docker](https://www.docker.com/products/docker-desktop/), and [Docker Compose](https://docs.docker.com/compose/install/).

2. Add your credentials to [.env](./.env.example) in the root of this repo.

3. Terraform requires some manual setup.

- Create an AWS S3 bucket in your AWS account for managing Terraform state: `s3://<AWS ACCOUNT NUMBER>-terraform-tfstate-<PROJECT-CODE>/`. Example: s3://012345678901-terraform-tfstate-am/
- Create a DynamoDB table for managing Terraform locks during plan execution: `<PROJECT-CODE>-terraform-lock`. Example: am-terraform-lock.
- Add credentials to [terraform.tfvars](./terraform/aws/terraform/terraform.tfvars.example) for production secrets that will be persisted as Kubernetes Secrets.
- Terraform additionally requires admin access to your AWS account in order to manager resources. See [global.hcl](./terraform/aws/global.hcl). You can provide these by exporting environment variables to the console in either of the following schemes:

```console

export AWS_PROFILE=lawrence                 # Recommended way

export AWS_REGION=us-east-2                 # -----------------------
export AWS_ACCOUNT_ID=012345678901          # Alternative
export AWS_ACCESS_KEY_ID=SET-ME-PLEASE      # way
export AWS_SECRET_ACCESS_KEY=SET-ME-PLEASE  # -----------------------
```

4. Initialize, build and run the application locally.

```console
git clone https://github.com/smarter-sh/account-manager
make                # scaffold .env and terraform.tfvars files
                    #
                    # ****************************
                    # STOP HERE!
                    # ****************************
                    # Add your credentials to .env located in the project root folder, and
                    # to terraform/aws/terraform/terraform.tfvars
                    #
make init           # pulls Docker containers, creates and initializes a local MySQL database and the admin user
make run            # runs all docker containers and starts a local web server http://localhost:8000/
```

5. Login at http://localhost:8000/login/ with user `admin` and password `am`.

## Development

```console
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
