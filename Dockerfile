#------------------------------------------------------------------------------
# This Dockerfile is used to build
# - a Docker image for the Account Manager application.
# - a Docker container for the Account Manager Celery worker.
# - a Docker container for the Account Manager Celery beat.
#
# This image is used for all environments (local, alpha, beta, next and production).
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
# It is commonly used for production deployments where a lightweight Python environment is preferred.
ARG PYTHON_BASE_IMAGE=public.ecr.aws/docker/library/python:3.14-slim-trixie
FROM ${PYTHON_BASE_IMAGE} AS linux_base

LABEL maintainer="Lawrence McDaniel <lpm0073@gmail.com>" \
  description="Docker image for Account Manager" \
  vcs-url="https://github.com/smarter-sh/account-manager" \
  org.opencontainers.image.title="Account Manager" \
  org.opencontainers.image.version="1.1.1" \
  org.opencontainers.image.authors="Lawrence McDaniel <lpm0073@gmail.com>" \
  org.opencontainers.image.source="https://github.com/smarter-sh/account-manager"


# Environment: local, alpha, beta, next, or production
ARG ENVIRONMENT=local
ENV ENVIRONMENT=$ENVIRONMENT
RUN echo "ENVIRONMENT: $ENVIRONMENT"

############################## install system packages #################################
# build-essential           needed to build some python packages, but not included in 3.14-slim-trixie
# libssl-dev                ... ditto ...
# libffi-dev                ... ditto ...
# python3-dev               ... ditto ...
# pkg-config                ... ditto ...
# ------
# ca-certificates           needed for SSL/TLS support in http requests but not included in 3.14-slim-trixie
# python-dev-is-python3     helper package to ensure that the 'python' command points to python3
# default-mysql-client      needed for Django mysql backend support
# libmariadb-dev            needed for default-mysql-client python package
# git                       used in manage.py commands
# ------
# curl                      for debugging http from inside the container
# procps                    provides the 'ps' command, used for liveness/readiness probes of the beat pod in kubernetes
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
  default-mysql-client \
  libmariadb-dev \
  git \
  curl \
  procps \
  redis-tools && \
  update-ca-certificates && \
  rm -rf /var/lib/apt/lists/*

############################## create app user #################################
FROM system_packages AS user_setup

# Create a non-root user to run the application
RUN adduser --disabled-password --gecos '' am_user

# create a data directory for the am_user that
# the application can use to store data.
# - add a celery directory for celerybeat to use to store its schedule.
RUN mkdir -p /home/am_user/data/celery && \
  mkdir -p /home/am_user/data/media        # fallback Django storage when not using S3 or other external storage.

# ensure that the am_user owns everything in the /am directory.
RUN chown -R am_user:am_user /home/am_user/

# so that the Docker file system matches up with the local file system.
WORKDIR /am

# Switch to non-root user
USER am_user

############################## python setup #################################
FROM user_setup AS venv
# Create and activate a virtual environment in the user's home directory
RUN python -m venv /home/am_user/venv
ENV PATH="/home/am_user/venv/bin:$PATH"

# Add all Python package dependencies
COPY ./am/requirements requirements
RUN pip install --upgrade pip && \
  pip install --no-cache-dir -r requirements/docker.txt

# Install Python dependencies for the local environment for cases where
# we're going to run python unit tests in the Docker container.
RUN if [ "$ENVIRONMENT" = "local" ] ; then pip install -r requirements/local.txt ; fi

############################## application ##################################
FROM venv AS application
# do this last so that we can take advantage of Docker's caching mechanism.
WORKDIR /home/am_user/
COPY --chown=am_user:am_user ./am ./am
RUN mkdir -p /home/am_user/data/manifests/example_manifests

################################# permissuions #######################################
FROM application AS permissions

# ensure that am_user owns everything and has the minimum
# permissions needed to run the application and to manage files
# that the application needs to write to in /home/am_user.
# this is important because by default Debian adds
# read-only and execute permissions to the group and to public.
# We don't want either of these.
#
# files:                    r-------- so that am_user can read them
# directories:              r-x------ so that am_user can cd into them
# venv/bin/*:               r-x------ so that am_user can execute them
# am/**/migrations:         rwx------ so that am_user can write django migration files.
# data:                     rwx------ so that am_user can manage the data directory.
# .cache:                   rwx------ bc some python packages want to write to .cache, like tldextract
#
# The local image stays writable by am_user, as in smarter: the unit tests run
# in it under coverage.py, which writes its data file into /home/am_user/am.

USER root
RUN chown -R am_user:am_user /home/am_user/ && \
  if [ "$ENVIRONMENT" != "local" ] ; then \
  find /home/am_user/ -type f -exec chmod 400 {} + && \
  find /home/am_user/ -type d -exec chmod 500 {} + && \
  find /home/am_user/venv/bin/ -type f -exec chmod 500 {} + && \
  find /home/am_user/am/am/ -type d -name migrations -exec chmod 700 {} + && \
  chmod -R 700 /home/am_user/data && \
  chmod -R 700 /home/am_user/.cache && \
  chmod 755 /home/am_user/am/manage.py ; fi

################################# data #################################
FROM permissions AS data
# Add our source code and make the 'am' directory the working directory
# we want this to be the last step so that we can take advantage of Docker's
# caching mechanism.
WORKDIR /home/am_user/


############################## collect_assets ##################################
# This is a Django application, so we need to collect static assets.
# We do this in a separate stage so that if the application code changes
# but the static assets do not change, we can take advantage of Docker's
# caching mechanism.
FROM data AS collect_assets
WORKDIR /home/am_user/am
RUN python manage.py collectstatic --noinput


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
