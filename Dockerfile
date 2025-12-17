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
# 3.12-slim-trixie is an official Docker image tag for Python 3.12 based on
# Debian "Trixie" (the codename for Debian 13).
# The "slim" variant is a minimal image that excludes unnecessary files and packages,
# making it smaller and faster to download and build.
# It is commonly used for production deployments where a lightweight Python environment is preferred.
FROM python:3.12-slim-trixie AS linux_base

LABEL maintainer="Lawrence McDaniel <lpm0073@gmail.com>" \
  description="Docker image for Account Manager" \
  vcs-url="https://github.com/smarter-sh/account-manager" \
  org.opencontainers.image.title="Account Manager" \
  org.opencontainers.image.version="1.1.0" \
  org.opencontainers.image.authors="Lawrence McDaniel <lpm0073@gmail.com>" \
  org.opencontainers.image.source="https://github.com/smarter-sh/account-manager"


# Environment: local, alpha, beta, next, or production
ARG TARGETPLATFORM
ARG TARGETARCH
ARG ENVIRONMENT=local
ENV ENVIRONMENT=$ENVIRONMENT
RUN echo "ENVIRONMENT: $ENVIRONMENT"

############################## install system packages #################################
# build-essential           needed to build some python packages, but not included in 3.12-slim-trixie
# libssl-dev                ... ditto ...
# libffi-dev                ... ditto ...
# python3-dev               ... ditto ...
# pkg-config                ... ditto ...
# ------
# ca-certificates           needed for SSL/TLS support in http requests but not included in 3.12-slim-trixie
# python-dev-is-python3     helper package to ensure that the 'python' command points to python3
# default-mysql-client      needed for Django mysql backend support
# libmariadb-dev            needed for default-mysql-client python package
# git                       used in manage.py commands
# ------
# curl                      used below in this Dockerfile to download files
# unzip                     used below in this Dockerfile to install aws cli
# procps                    provides the 'ps' command, used for liveness/readiness probes of the beat pod in kubernetes
FROM linux_base AS system_packages

# Install system packages
# The Python slim trixie image is based on Debian and is a limited installation. Most of these packages
# would ordinarily be included in a full Debian installation, but are missing from the slim image and
# we therefore need to "add these back in" as part of our Dockerfile.
RUN apt-get update && apt-get upgrade -y && apt-get install -y \
  build-essential \
  libssl-dev \
  libffi-dev \
  python3-dev \
  pkg-config \
  ca-certificates \
  python-dev-is-python3 \
  wget \
  git \
  curl \
  unzip \
  procps \
  redis-tools \
  libmariadb-dev \
  libncurses6 && \
  rm -rf /var/lib/apt/lists/*

# Install Oracle MySQL 8.x client binary for correct architecture
RUN if [ "$TARGETARCH" = "arm64" ]; then \
      MYSQL_TARBALL="mysql-8.0.36-linux-glibc2.28-aarch64.tar.xz"; \
      MYSQL_DIR="mysql-8.0.36-linux-glibc2.28-aarch64"; \
    else \
      MYSQL_TARBALL="mysql-8.0.36-linux-glibc2.28-x86_64.tar.xz"; \
      MYSQL_DIR="mysql-8.0.36-linux-glibc2.28-x86_64"; \
    fi && \
    wget "https://dev.mysql.com/get/Downloads/MySQL-8.0/${MYSQL_TARBALL}" && \
    tar -xf "$MYSQL_TARBALL" && \
    cp "$MYSQL_DIR/bin/mysql" /usr/local/bin/ && \
    chmod +x /usr/local/bin/mysql && \
    rm -rf "$MYSQL_TARBALL" "$MYSQL_DIR"

# Install kubectl, required for smarter/common/helpers/k8s_helpers.py used for ChatBot/Agent
# deployments in which dedicated Kubernetes ingress and TLS certificates are created. There
# are Kubernetes builds for both amd64 and arm64 architectures (we build both for DockerHub
# multi-arch support).
RUN if [ "$TARGETARCH" = "arm64" ]; then \
      KUBECTL_ARCH="arm64"; \
    else \
      KUBECTL_ARCH="amd64"; \
    fi && \
    curl -LO "https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/${KUBECTL_ARCH}/kubectl" && \
    chmod +x ./kubectl && \
    mv ./kubectl /usr/local/bin/kubectl

# install aws cli, required for smarter/common/helpers/aws/
# We rely extensively on AWS support, for Route53, S3, Simple Email Service,
# Elastic Kubernetes Service, etc. There are AWS CLI builds for both
# amd64 and arm64 architectures (we build both for DockerHub multi-arch support).
RUN if [ "$TARGETARCH" = "arm64" ]; then \
      curl "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o "awscliv2.zip"; \
    else \
      curl "https://d1vvhvl2y92vvt.cloudfront.net/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"; \
    fi && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf awscliv2.zip aws


############################## create app user #################################
FROM system_packages AS user_setup

# Create a non-root user to run the application
RUN adduser --disabled-password --gecos '' am_user

# create a data directory for the am_user that
# the application can use to store data.
# - add a .kube directory and an empty config file
# - add a celery directory for celerybeat to use to store its schedule.
RUN mkdir -p /home/am_user/data/.kube && touch /home/am_user/data/.kube/config && \
  mkdir -p /home/am_user/data/celery && \
  mkdir -p /home/am_user/data/media        # fallback Django storage when not using S3 or other external storage.

# Set the KUBECONFIG environment variable
ENV KUBECONFIG=/home/am_user/data/.kube/config

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

USER root
RUN chown -R am_user:am_user /home/am_user/ && \
  find /home/am_user/ -type f -exec chmod 400 {} + && \
  find /home/am_user/ -type d -exec chmod 500 {} + && \
  find /home/am_user/venv/bin/ -type f -exec chmod 500 {} + && \
  find /home/am_user/am/am/ -type d -name migrations -exec chmod 700 {} + && \
  chmod -R 700 /home/am_user/data && \
  chmod -R 700 /home/am_user/.cache && \
  chmod 755 /home/am_user/am/manage.py

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
