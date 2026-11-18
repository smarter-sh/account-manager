SHELL := /bin/bash
export PATH := /usr/local/bin:$(PATH)
export

ifeq ($(OS),Windows_NT)
    PYTHON := python.exe
    ACTIVATE_VENV := venv/Scripts/activate
else
    PYTHON := python3.14
    ACTIVATE_VENV := source venv/bin/activate
endif
PIP := $(PYTHON) -m pip

# scaffold .env from .env.example before it is included.
ifeq ("$(wildcard .env)","")
    $(shell cp .env.example .env)
endif
include .env

# scaffold Terraform's variables from the example, for the terraform/ commands.
ifeq ("$(wildcard terraform/aws/terraform/terraform.tfvars)","")
    $(shell cp terraform/aws/terraform/terraform.tfvars.example terraform/aws/terraform/terraform.tfvars)
endif

.PHONY: all init activate build run test clean tear-down lint analyze coverage pre-commit-init pre-commit-run release change-log \
	docker-check docker-init docker-shell docker-build docker-run docker-test docker-prune \
	python-init python-lint python-clean python-requirements check-python \
	helm-update \
	help

# A bare `make` prints the menu of commands. Each target's description is the `## `
# comment after the colon on the target's own line, e.g. `build: ## Build Docker containers`.
.DEFAULT_GOAL := help

all: help

# initialize local development environment.
# takes around 5 minutes to complete
init: ## Initialize local and Docker environments
	make check-python		# verify Python 3.14 is installed
	make docker-check		# verify Docker is installed and running
	make python-init		# create/replace Python virtual environment and install dependencies
	make docker-build		# build the Account Manager containers
	make docker-init		# initialize MySQL and create the am database
	make pre-commit-init	# install and configure pre-commit
	@echo ""
	@echo "==============================================================================="
	@echo "Initialization complete!"
	@echo ""
	@echo "Run 'source venv/bin/activate' to activate the Python virtual environment."
	@echo "Run 'make run' to start the application, at http://localhost:8000/"
	@echo "    'make help' to see all available commands."
	@echo "==============================================================================="

activate: ## Activate Python virtual environment
	./scripts/activate.sh

# complete Docker build.
build: ## Build Docker containers
	make docker-build

# run the web application from Docker. Never returns: it is docker compose up, attached to the logs.
run: ## Run web application from Docker
	make docker-run

test: ## Run Python-Django unit tests in Docker
	make docker-test

clean: ## Delete all local artifacts, virtual environment, node_modules, and Docker containers
	make python-clean
	make docker-prune

# destroy all Docker build and local artifacts
tear-down: ## Destroy all Docker build and local artifacts
	make python-clean
	make docker-prune

# ---------------------------------------------------------
# Code management
# ---------------------------------------------------------

lint: ## Run all code linters and formatters
	make python-lint

analyze: ## Generate code analysis report using cloc
	cloc . --exclude-ext=svg,zip --fullpath --not-match-d=am/am/static/ --vcs=git

# The options are in am/.coveragerc. Celery Beat is stopped while the tests run, as in docker-test.
coverage: ## Generate Docker-based code coverage report
	docker stop am-beat > /dev/null || true
	docker exec am-app bash -c "coverage run manage.py test am && coverage report -m && coverage xml"; status=$$?; \
	docker start am-beat > /dev/null; \
	exit $$status

change-log: ## Update CHANGELOG.md file
	npx conventional-changelog -p angular -i CHANGELOG.md -s

pre-commit-init: ## Install and configure pre-commit
	pre-commit install
	pre-commit autoupdate

pre-commit-run: ## Run all pre-commit hooks on all files
	pre-commit run --all-files

release: ## Force a new Github release
	git commit -m "fix: force a new release" --allow-empty && git push


# ---------------------------------------------------------
# Docker
# ---------------------------------------------------------
docker-check: ## Verify Docker is installed and running
	@docker ps >/dev/null 2>&1 || { echo >&2 "This project requires Docker but it's not running.  Aborting."; exit 1; }

docker-shell: ## Open a shell in the am-app Docker container
	make docker-check && \
	docker exec -it am-app /bin/bash

docker-init: ## Initialize MySQL and create the am database
	make docker-check && \
	docker compose up -d && \
	docker exec am-mysql bash -c "sleep 20; until echo '\q' | mysql -u am -pam; do echo 'Waiting for MySQL to be ready...'; sleep 10; done" && \
	docker exec am-mysql mysql -u root -pam -e "DROP DATABASE IF EXISTS am; CREATE DATABASE am; GRANT ALL PRIVILEGES ON *.* TO 'am'@'%'; FLUSH PRIVILEGES;" && \
	docker exec am-app bash -c "\
		python manage.py migrate && \
		python manage.py initialize_waffle && \
		python manage.py initialize_site && \
		python manage.py oscar_populate_countries --initial-only && \
		python manage.py create_account_admin --username admin --email admin@smarter.sh --password am" && \
	echo "Docker and Account Manager are initialized." && \
	docker ps

docker-build: ## Build all Docker containers using docker compose
	make docker-check && \
	docker compose build && \
	docker image prune -f

docker-run: ## Start all Docker containers using docker compose
	make docker-check && \
	docker compose up

# Celery Beat is stopped while the tests run, and started again afterwards, even when a
# test fails, so that its scheduled tasks don't change the rows of running tests.
docker-test: ## Run Python-Django unit tests in Docker
	make docker-check
	docker stop am-beat > /dev/null || true
	docker exec am-app bash -c "python manage.py test am"; status=$$?; \
	docker start am-beat > /dev/null; \
	exit $$status

docker-prune: ## Remove unused Docker objects and clean up Docker artifacts
	make docker-check && \
	docker compose down && \
	docker builder prune -a -f && \
	docker image prune -a -f
	rm -rf ./mysql-data && \
	find ./ -name celerybeat-schedule -type f -exec rm -f {} + && \
	docker system prune -a --volumes && \
	docker volume prune -f && \
	docker network prune -f && \
	images=$$(docker images -q) && [ -n "$$images" ] && docker rmi $$images -f || echo "No images to remove"

# ---------------------------------------------------------
# Python
# ---------------------------------------------------------
check-python: ## Verify Python 3.14 is installed
	@command -v $(PYTHON) >/dev/null 2>&1 || { echo >&2 "This project requires $(PYTHON) but it's not installed.  Aborting."; exit 1; }

python-init: ## Create a Python virtual environment and install dependencies
	mkdir -p .pypi_cache && \
	make check-python
	make python-clean && \
	npm install && \
	$(PYTHON) -m venv venv && \
	$(ACTIVATE_VENV) && \
	PIP_CACHE_DIR=.pypi_cache $(PIP) install --upgrade pip && \
	$(PIP) install setuptools wheel pip-tools && \
	PIP_CACHE_DIR=.pypi_cache $(PIP) install -r am/requirements/local.txt

python-lint: ## Run Python linting using pre-commit and pylint
	make check-python
	make pre-commit-run
	pylint am/am

python-clean: ## Destroy the Python virtual environment and remove __pycache__ directories
	rm -rf venv
	find ./am/ -name __pycache__ -type d -exec rm -rf {} +

# The .in files name the packages; the compiled .txt files pin them. Add --upgrade to move the pins.
python-requirements: ## Compile and update Python dependency files
	# pip 25.3 removed InstallRequirement.use_pep517, which pip-tools 7.x still reads.
	pip install --upgrade setuptools wheel "pip<25.3" "pip-tools>=7.6.1"
	pip-compile am/requirements/in/local.in -o am/requirements/local.txt
	pip-compile am/requirements/in/docker.in -o am/requirements/docker.txt

# -------------------------------------------------------------------------
# Helm
# -------------------------------------------------------------------------
helm-update: ## Update Helm chart dependencies
	cd helm/charts/account-manager && \
	helm dependency update

######################
# HELP
######################

help: ## Show this menu of commands
	@grep -hE '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'
