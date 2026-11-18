#------------------------------------------------------------------------------
# This Dockerfile is used to build
# - a Docker image for the Account Manager application.
# - a Docker container for the Account Manager Celery worker.
# - a Docker container for the Account Manager Celery beat.
#
# This image is used for all environments (local, alpha, beta, next and production).
# It is modeled on smarter-sh/smarter's Dockerfile: same base image, the same MariaDB
# client stack, and the same permissions model.
#------------------------------------------------------------------------------

################################## base #######################################
# Use the official Python image as a parent image
# see https://hub.docker.com/_/python
#
# 3.14-slim-trixie is an official Docker image tag for Python 3.14 based on
# Debian "Trixie" (the codename for Debian 13), as in smarter-sh/smarter.
#
# PYTHON_BASE_IMAGE lets a build pull the same image from somewhere else.
# Anonymous ECR Public pulls have a monthly data quota per source IP, which
# other users of GitHub's shared runner IPs exhaust ("toomanyrequests: Data
# limit exceeded"), so the Tests workflow sets this to Docker Hub's python
# image, where it is logged in.
# The "slim" variant is a minimal image that excludes unnecessary files and packages,
# making it smaller and faster to download and build.
ARG PYTHON_BASE_IMAGE=public.ecr.aws/docker/library/python:3.14-slim-trixie
FROM ${PYTHON_BASE_IMAGE} AS linux_base

LABEL maintainer="Lawrence McDaniel <lpm0073@gmail.com>" \
  description="Docker image for Account Manager" \
  license="GNU AGPL v3" \
  vcs-url="https://github.com/smarter-sh/account-manager" \
  org.opencontainers.image.title="Account Manager" \
  org.opencontainers.image.version="1.1.1" \
  org.opencontainers.image.authors="Lawrence McDaniel <lpm0073@gmail.com>" \
  org.opencontainers.image.url="https://smarter.sh/" \
  org.opencontainers.image.source="https://github.com/smarter-sh/account-manager" \
  org.opencontainers.image.documentation="https://docs.smarter.sh/"


# Environment: local, alpha, beta, next, or production
ARG TARGETPLATFORM
ARG TARGETARCH
ARG ENVIRONMENT=local
ENV ENVIRONMENT=$ENVIRONMENT

############################## install system packages #################################
# build-essential           needed to build some python packages, but not included in 3.14-slim-trixie
# libssl-dev                ... ditto ...
# libffi-dev                ... ditto ...
# python3-dev               ... ditto ...
# pkg-config                ... ditto ...
# ------
# ca-certificates           needed for SSL/TLS support in http requests but not included in 3.14-slim-trixie
# python-dev-is-python3     helper package to ensure that the 'python' command points to python3
# git                       used in manage.py commands
# ------
# curl                      fetches MariaDB's apt repository setup script below, and for debugging
# procps                    provides the 'ps' command, used for liveness/readiness probes of the beat pod in kubernetes
# redis-tools               redis-cli, for debugging Celery's broker from inside the container
FROM linux_base AS system_packages

# Install system packages
# The Python slim trixie image is based on Debian and is a limited installation. Most of these packages
# would ordinarily be included in a full Debian installation, but are missing from the slim image and
# we therefore need to "add these back in" as part of our Dockerfile.
RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get upgrade -y && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  build-essential \
  libssl-dev \
  libffi-dev \
  python3-dev \
  pkg-config \
  ca-certificates \
  python-dev-is-python3 \
  git \
  curl \
  procps \
  redis-tools && \
  update-ca-certificates && \
  rm -rf /var/lib/apt/lists/*

############################## MariaDB #################################
FROM system_packages AS mariadb_connector

# Install MariaDB, as smarter-sh/smarter does: Account Manager's database is the shared MariaDB
# server that smarter's Helm chart runs.
# installs libmariadb-dev libmariadb-dev-compat mariadb-client, Connector/C and mariadb_config:
# the C library that the mariadb Python package builds against, and the mariadb client that the
# Helm chart's init job uses to create Account Manager's database and user.
# See
# - https://mariadb.com/docs/connectors/mariadb-connector-c/install-mariadb-connector-c
# - https://mariadb.com/downloads/

ARG MARIADB_VERSION=12.3
ENV MARIADB_CONFIG=/usr/bin/mariadb_config
ENV MARIADB_CONFIG_ALTERNATIVE=/usr/local/bin/mariadb_config
RUN curl -LsS -o mariadb_repo_setup https://downloads.mariadb.com/MariaDB/mariadb_repo_setup && \
    chmod +x mariadb_repo_setup && \
    ./mariadb_repo_setup --mariadb-server-version="${MARIADB_VERSION}" --skip-maxscale && \
    apt-get update && \
    apt-get install -y --no-install-recommends libmariadb-dev libmariadb-dev-compat mariadb-client && \
    test -x "$MARIADB_CONFIG" || (echo "mariadb_config not found at $MARIADB_CONFIG" && exit 1) && \
    ln -sf "$MARIADB_CONFIG" "$MARIADB_CONFIG_ALTERNATIVE" && \
    rm -f mariadb_repo_setup && \
    rm -rf /var/lib/apt/lists/*

############################## create app user #################################
FROM mariadb_connector AS user_setup

# Create a non-root user to run the application
RUN adduser --disabled-password --gecos '' am_user

# create a data directory for the am_user that
# the application can use to store data.
# - a celery directory for celerybeat to use to store its schedule.
# - a media directory, the fallback Django storage when not using S3 or other external storage.
RUN mkdir -p /home/am_user/data/celery && \
  mkdir -p /home/am_user/data/media

RUN chown -R am_user:am_user /home/am_user/

WORKDIR /home/am_user/

# Switch to non-root user
USER am_user

############################## python setup #################################
FROM user_setup AS venv
# Create and activate a virtual environment in the user's home directory
RUN python -m venv /home/am_user/venv
ENV PATH="/home/am_user/venv/bin:$PATH"

# Add all Python package dependencies: one requirements file, never two. local.txt is a superset
# of docker.txt (local.in includes docker.in) with the development and test tools, for the local
# image, which runs the unit tests. Every other environment gets docker.txt.
COPY ./am/requirements requirements
RUN pip install --upgrade pip && \
  if [ "$ENVIRONMENT" = "local" ] ; then \
    pip install --no-cache-dir -r requirements/local.txt ; \
  else \
    pip install --no-cache-dir -r requirements/docker.txt ; \
  fi

############################## application ##################################
FROM venv AS application
# do this last so that we can take advantage of Docker's caching mechanism.
WORKDIR /home/am_user/
COPY --chown=am_user:am_user ./am ./am
RUN mkdir -p /home/am_user/am/staticfiles

################################# permissions #######################################
FROM application AS permissions

# As in smarter-sh/smarter, the code and the virtual environment belong to root, and am_user only
# reads and runs them through its group. A file's owner can always chmod it back to writable, so
# owning its own code would let the running process rewrite it, whatever the modes. am_user owns
# only what it must write: data/, .cache/ and staticfiles/.
#
# files:                    r--r----- root:am_user
# directories:              r-xr-x--- root:am_user
# venv/bin/*, manage.py:    r-xr-x--- root:am_user
# data, .cache, staticfiles rwx------ am_user, and nobody else
#
# The bytecode is compiled here, since nothing can write __pycache__ at runtime.
#
# The local image stays writable by am_user, as in smarter: the unit tests run in it under
# coverage.py, which writes its data file into /home/am_user/am.

USER root
RUN mkdir -p /home/am_user/.cache && \
  if [ "$ENVIRONMENT" != "local" ] ; then \
  python -m compileall -q /home/am_user/am/am && \
  chown -R root:am_user /home/am_user/ && \
  find /home/am_user/ -type f -exec chmod 440 {} + && \
  find /home/am_user/ -type d -exec chmod 550 {} + && \
  find /home/am_user/venv/bin/ -type f -exec chmod 550 {} + && \
  chmod 550 /home/am_user/am/manage.py && \
  chown -R am_user:am_user /home/am_user/data /home/am_user/.cache /home/am_user/am/staticfiles && \
  chmod -R u=rwX,go= /home/am_user/data /home/am_user/.cache /home/am_user/am/staticfiles ; \
  else \
  chown -R am_user:am_user /home/am_user/ ; fi

################################# data #################################
FROM permissions AS data
WORKDIR /home/am_user/


############################## collect_assets ##################################
# This is a Django application, so we need to collect static assets. collectstatic runs as
# am_user, with a throwaway secret key, as in smarter.
FROM data AS collect_assets
USER am_user
WORKDIR /home/am_user/am
RUN SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')" \
      python manage.py collectstatic --noinput && \
    if [ -z "$(ls -A /home/am_user/am/staticfiles 2>/dev/null)" ]; then \
      echo "Error: /home/am_user/am/staticfiles is missing or empty" >&2; exit 1; \
    fi
# then the collected files are read-only, like the code.
USER root
RUN if [ "$ENVIRONMENT" != "local" ] ; then \
  chown -R root:am_user /home/am_user/am/staticfiles && \
  find /home/am_user/am/staticfiles -type f -exec chmod 440 {} + && \
  find /home/am_user/am/staticfiles -type d -exec chmod 550 {} + ; fi


################################# final #######################################
# This is the final stage that will be used to run the application.
# Gunicorn is used as the application server.
# "am.wsgi:application" is the WSGI application callable and corresponds
# to the "application" variable in am/wsgi.py.
# The application will listen on all interfaces (0.0.0.0).
FROM collect_assets AS serve_application

WORKDIR /home/am_user/am
USER am_user
CMD ["gunicorn", "am.wsgi:application", "-b", "0.0.0.0:8000"]
EXPOSE 8000
