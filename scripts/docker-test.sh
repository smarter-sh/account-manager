#!/usr/bin/env bash
#------------------------------------------------------------------------------
# Run unit tests against the host's working tree, in a throwaway container of
# the am image, without rebuilding it or copying files into am-app.
#
#   scripts/docker-test.sh                                   # every test
#   scripts/docker-test.sh am.apps.account.tests.test_user   # a module, class or method
#   COVERAGE=1 scripts/docker-test.sh am.lib                 # under coverage.py, with a report
#   AM_TEST_DATABASE_NAME=test_am_2 scripts/docker-test.sh am.lib   # a test database of its own
#
# The host's am/ folder is mounted over /home/am_user/am, so edits are tested at
# once. It needs the am image (make build), and am-mysql and am-redis running
# (docker compose up -d). Concurrent runs need different AM_TEST_DATABASE_NAMEs,
# because each one creates and drops its test database. Coverage data is written
# to am/.coverage.<test database name>.
#------------------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")/.."
labels="${*:-am}"
db="${AM_TEST_DATABASE_NAME:-test_am}"

if [ -n "${COVERAGE:-}" ]; then
  command="coverage run --data-file=.coverage.${db} manage.py test ${labels} --noinput; status=\$?; coverage report -m --data-file=.coverage.${db}; exit \$status"
else
  command="python manage.py test ${labels} --noinput"
fi

exec docker run --rm \
  --network account-manager_default \
  --env-file .env \
  -e AM_TEST_DATABASE_NAME="${db}" \
  -v "$PWD/am:/home/am_user/am" \
  -w /home/am_user/am \
  am bash -c "${command}"
