# Smarter Account Manager Helm Chart

A Helm chart for deploying Smarter Account Manager, the account, subscription
and payment microservice of the [Smarter](https://github.com/smarter-sh/smarter)
platform. It is modeled on Smarter's own chart, `helm/charts/smarter`.

- **Website:** [https://am.smarter.sh](https://am.smarter.sh)
- **Source:** [https://github.com/smarter-sh/account-manager](https://github.com/smarter-sh/account-manager)

## What it deploys

| Resource                                    | Template                | Purpose                                                                                                                    |
| ------------------------------------------- | ----------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Deployment `account-manager`                | `deployment_app.yaml`   | gunicorn `am.wsgi:application` on port 8000                                                                                |
| Service `account-manager`                   | `service_app.yaml`      | the app's ClusterIP Service, which the ingress in `terraform/` routes to                                                   |
| Deployment `account-manager-worker`         | `deployment_worker.yaml` | the Celery worker (`default_celery_task_queue,beat_tasks`)                                                                |
| Deployment `account-manager-beat`           | `deployment_beat.yaml`  | Celery beat, one replica                                                                                                   |
| Job `<release>-job-init-<timestamp>`        | `job-init.yaml`         | post-install/post-upgrade hook: creates the database and its user, migrates, initializes                                   |
| Job `<release>-job-migrate-<timestamp>`     | `job-migrate.yaml`      | pre-upgrade hook: `migrate`, so that the new pods never run without their schema                                          |
| Secret `account-manager-env`                | `secret-env.yaml`       | `.Values.env`, which every pod reads with `envFrom`                                                                        |
| ServiceAccount `account-manager`            | `serviceaccount.yaml`   | the pods' identity; no Kubernetes API access, optional IRSA role                                                           |
| Redis `am-redis`                            | bitnami `redis` subchart | the cache and the Celery broker                                                                                           |

## The database: Smarter's shared MariaDB server

Account Manager has **no database server of its own**. It uses the MariaDB
server that the smarter Helm chart runs (the bitnami `mariadb` subchart), the
Service `smarter-mariadb` in the Smarter platform's namespace, with a database
and a user of its own on that server:

```yaml
env:
  AM_MYSQL_HOST: smarter-mariadb.<smarter-namespace>.svc.cluster.local # e.g. smarter-ubc-alpha
  AM_MYSQL_PORT: "3306"
  AM_MYSQL_DATABASE: smarter_am_alpha
  AM_MYSQL_USER: smarter_am_alpha
  AM_MYSQL_PASSWORD: <password>
  AM_MYSQL_ROOT_USERNAME: root
  AM_MYSQL_ROOT_PASSWORD: <the shared server's root password>
```

The init job connects as the root user with the `mariadb` client, passing the
root password in `MYSQL_PWD` and each statement on stdin, so no password is on
a command line. It runs `CREATE DATABASE ... CHARACTER SET utf8mb4 COLLATE
utf8mb4_unicode_ci` (and `ALTER DATABASE`), `CREATE USER` and `ALTER USER`,
and grants that user Account Manager's database only. Then it runs `migrate`,
`initialize_waffle`, `initialize_site`, `oscar_populate_countries
--initial-only` and `create_account_admin`. Any failed step fails the job, and
so the Helm hook.

The MariaDB server must admit connections from Account Manager's pods. Their
`app.kubernetes.io/application-group` label is `account-manager`.

## Security

- **Secrets:** every value of `env` is written into the Secret
  `account-manager-env`, never into a pod spec or a command line. Each pod
  carries a `checksum/env` annotation, so a changed value rolls the pods. A
  `null` value is left out of the Secret.
- **Pods:** `global.podSecurityContext` (non-root, uid and gid 1000, the image's
  `am_user`, RuntimeDefault seccomp) and `global.containerSecurityContext` (no
  privilege escalation, read-only root filesystem, all capabilities dropped)
  apply to every pod. The directories the processes write (`/tmp`,
  `~/.cache`, `~/data/celery`, `~/data/media`) are emptyDirs
  (`am.writableVolumes` in `templates/_helpers.tpl`).
- **ServiceAccount:** the pods don't call the Kubernetes API, so their token is
  not mounted. With `serviceAccount.awsRoleArn`, the pods use that IAM role
  (IRSA) instead of `env.AWS_ACCESS_KEY_ID` and `env.AWS_SECRET_ACCESS_KEY`.

## Prerequisites

- Kubernetes >=1.28.0
- Helm 3.8+
- The Smarter platform deployed to the same cluster, with its MariaDB server

## Installing

The repository's Deploy workflow (`.github/workflows/deploy.yml` and
`.github/actions/deploy/action.yml`) installs the chart. It reads the
credentials from the Kubernetes secrets that `terraform/aws` creates in
Account Manager's namespace (`mysql-am`, `mysql-root`, `am-admin`,
`am-django-secret-key`, `aws-ses-config`), writes them into a values file and
runs:

```bash
helm upgrade --install --force account-manager ./helm/charts/account-manager/ \
  --namespace smarter-am-alpha \
  --timeout 900s \
  --values values.yaml
```

To install by hand, put the values in a file rather than on the command line,
so that no credential is left in your shell history:

```yaml
env:
  AM_DOCKER_IMAGE: <registry>/smarter-am-alpha:latest
  DJANGO_SETTINGS_MODULE: am.settings.alpha
  ENVIRONMENT: alpha
  ROOT_DOMAIN: example.com
  SECRET_KEY: <django secret key>
  CACHES_LOCATION: redis://:am@am-redis-master.smarter-am-alpha.svc.cluster.local:6379/1
  CELERY_BROKER_URL: redis://:am@am-redis-master.smarter-am-alpha.svc.cluster.local:6379/0
  CELERY_RESULT_BACKEND: redis://:am@am-redis-master.smarter-am-alpha.svc.cluster.local:6379/0
  AM_MYSQL_HOST: smarter-mariadb.smarter-ubc-alpha.svc.cluster.local
  AM_MYSQL_DATABASE: smarter_am_alpha
  AM_MYSQL_USER: smarter_am_alpha
  AM_MYSQL_PASSWORD: <password>
  AM_MYSQL_ROOT_PASSWORD: <the shared server's root password>
  AM_ADMIN_PASSWORD: <password>
```

## Uninstalling

```bash
helm uninstall account-manager --namespace smarter-am-alpha
```

This leaves Account Manager's database and user on the shared server.

## Configuration

See [values.yaml](./values.yaml) for every option.
