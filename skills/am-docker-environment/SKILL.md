---
name: am-docker-environment
description: Use whenever Account Manager code must run in its Docker containers (am-app, am-worker, am-beat, am-mariadb, am-redis), for tests, migrations, manage.py commands or the local server, e.g. "run migrate", "the container has old code", "MariaDB won't start", "port 3306 is already allocated". Explains the image and why host edits don't reach the containers, make build / make run / docker compose up -d, syncing with docker cp or testing the host tree with scripts/docker-test.sh, the zsh word-splitting trap, and the database rules (make docker-init drops the am database).
---

# Account Manager Docker Environment

> **The host shell is zsh, and zsh does not word-split.** A loop such as
> `for f in $FILES; do docker cp "$f" ...; done`, with `FILES=$(git diff --name-only)`,
> runs **once**, with every path joined into one file name. `docker cp` fails,
> the container keeps the old code, and the tests "fail for no reason". Loop
> with `while read -r f; do ...; done` or `xargs`, and never discard
> `docker cp`'s errors. The same goes for any variable holding several
> arguments (`-e A=1 -e B=2`): use an array, `"${args[@]}"`.

## The containers

Services in `docker-compose.yml` (compose project `account-manager`, network
`account-manager_default`):

| Container    | Role                                                                                      |
| ------------ | ----------------------------------------------------------------------------------------- |
| `am-app`     | gunicorn on http://localhost:8000, under `watchmedo auto-restart`; where `manage.py` runs |
| `am-worker`  | Celery worker (`am.workers.celery.app`, queue `default_celery_task_queue`)                |
| `am-beat`    | Celery Beat (`am.workers.celerybeat.app`)                                                 |
| `am-mariadb` | MariaDB on host port 3306: database `am`, user `am`, password `am`, root password `am`    |
| `am-redis`   | Redis on host port 6379                                                                   |

`am-app`, `am-worker` and `am-beat` run the image `am`, built from the
`Dockerfile`, as `am_user`, with `.env` as their environment. The working
directory is `/home/am_user/am` (where `manage.py` is), so host path
`am/am/<path>` is `/home/am_user/am/am/<path>`.

```console
docker exec am-app bash -c "python manage.py <command>"
make docker-shell            # an interactive shell in am-app
```

## The containers don't see your edits

The image holds a **copy** of `am/` at `/home/am_user/am`. Compose also
bind-mounts the host's `am/` at `/am`, but nothing runs from there, so in
effect there is no bind mount: host edits do nothing until they reach the
containers.

Three ways, from the best:

1. **To run tests, skip the sync**: `scripts/docker-test.sh` runs them in a
   throwaway container of the `am` image with the host's `am/` mounted over
   `/home/am_user/am`. See `am-python-testing`.
2. **Rebuild.** `make build` (`docker compose build`, then
   `docker image prune -f`), then recreate the containers:

   ```console
   make build && docker compose up -d
   ```

3. **Copy single files** into a running container:

   ```console
   docker cp am/am/apps/account/views/foo.py am-app:/home/am_user/am/am/apps/account/views/foo.py
   docker exec -u root am-app chown am_user /home/am_user/am/am/apps/account/views/foo.py
   ```

   gunicorn restarts by itself when a `.py` file changes (`watchmedo`). The
   Celery containers don't: copy task code into `am-worker` and `am-beat`
   too, then `docker restart am-worker am-beat`.

### make run never returns

`make run` is `make docker-run`, which is `docker compose up`, attached to the
logs. Run in the foreground, it blocks until the timeout. Start it only with
`run_in_background: true`, or use `docker compose up -d`, which returns.
Wait for the server before using it:

```console
until curl -s -o /dev/null localhost:8000/; do sleep 2; done
```

## The database

- **`make docker-init` drops the local `am` database** (`DROP DATABASE IF
EXISTS am`), then migrates and creates the `admin` user. Never run it unless
  the user asks. To bring the database up to date:

  ```console
  docker exec am-app bash -c "python manage.py migrate"
  ```

- **Port 3306 is shared with Smarter.** `smarter-mariadb`, from the smarter
  repository's stack, also binds host port 3306, so `am-mariadb` fails to start
  ("port is already allocated") while it runs. Stop it first, and tell the
  user you did: `docker stop smarter-mariadb`.
- The data lives in `./mariadb-data` on the host (git-ignored). `make
docker-prune`, `make clean` and `make tear-down` delete it, and every Docker
  image, volume and network on the machine. Never run them unless asked.
- A MariaDB shell: `docker exec -it am-mariadb mariadb -u am -pam am`.

## docker cp traps

- **Copying a directory into an existing directory nests it**
  (`.../views/views`). Copy files one by one.
- **Copied files are owned by root**, so `am_user` can't change them, and
  `makemigrations` can fail. `chown` them as shown above.
- **Don't `rm -rf` in a container before diffing.** Files made there (a
  migration, `coverage.xml`) may not exist on the host.

## Copying files out

Generated files are written in the container. Copy them to the host so they
become part of the change:

```console
docker cp am-app:/home/am_user/am/am/apps/account/migrations/0001_initial.py am/am/apps/account/migrations/
```

`make coverage` also writes `coverage.xml` in the container
(`/home/am_user/am/coverage.xml`). It isn't git-ignored on the host, so don't
copy it into the repository.

## Safety

The containers read `.env`, which holds real SMTP credentials,
and whatever AWS or Stripe keys the developer added. A `manage.py` command or
a test that reaches one of those services does it for real. See
`am-python-testing`, "Mock every outside service". Don't run `docker system
prune`, `make docker-prune` or anything that removes other projects'
containers or volumes.
