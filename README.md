# Smarter Account Manager

![Build Status](https://github.com/smarter-sh/account-manager/actions/workflows/build.yml/badge.svg?branch=main)
![Release Status](https://github.com/smarter-sh/account-manager/actions/workflows/deploy.yml/badge.svg?branch=main)
![Unit Tests](https://github.com/smarter-sh/account-manager/actions/workflows/test.yml/badge.svg?branch=main)
[![codecov](https://codecov.io/gh/smarter-sh/account-manager/branch/main/graph/badge.svg)](https://codecov.io/gh/smarter-sh/account-manager)
![GHA pushMain Status](https://img.shields.io/github/actions/workflow/status/smarter-sh/account-manager/pushMain.yml?branch=main)
![Auto Assign](https://github.com/smarter-sh/account-manager/actions/workflows/auto-assign.yml/badge.svg)<br>
[![Release Notes](https://img.shields.io/github/release/smarter-sh/account-manager)](https://github.com/smarter-sh/account-manager/releases)
[![hack.d Lawrence McDaniel](https://img.shields.io/badge/hack.d-Lawrence%20McDaniel-orange.svg)](https://lawrencemcdaniel.com)

Account user and payment management microservice for Smarter.

## Usage

See https://docs.am.smarter.sh for User and Administration Guides.

Check the real-time subscription status of a user on a hosted platform.

```console
curl -X 'GET' \
  'https://api.am.smarter.sh/accounts/subscription-status/' \
  -H 'accept: application/json' \
  -H 'X-Client-Domain: platform.smarter.sh' \
  -H 'X-Client-Username: admin'
```

## Developer Quickstart

This is the local Docker startup. Smarter Account Manager runs on Linux, Windows and macOS.

1. Verify project requirements: [Python 3.12](https://www.python.org/), [Docker](https://www.docker.com/products/docker-desktop/), and [Docker Compose](https://docs.docker.com/compose/install/).

2. Add your credentials to [.env](./docs/example-dot-env) in the root of this repo. You also need to add credentials to [terraform.tfvars](./terraform/aws/terraform/terraform.tfvars.example) for secrets that will utlimately be persisted as Kubernetes Secrets.

3. Initialize, build and run the application locally.

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
make init           # pulls Docker containers, creates and initializes a local MySql database, preloads example AI resources
make run            # runs all docker containers and starts a local web server http://localhost:8000/
```

4. Login at http://localhost:8000/login/ with user `admin` and password `am`.

## Support

Please report bugs to the [GitHub Issues Page](https://github.com/smarter-sh/account-manager/issues) for this project.
