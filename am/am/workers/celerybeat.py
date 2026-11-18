"""Celery Beat schedule for the Account Manager."""

import os

from celery.schedules import timedelta

# Set the default Django settings module for the 'celery' program
# and then instantiate the Celery singleton.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "am.settings.local")

# pylint: disable=wrong-import-position,unused-import
from am.lib.celery_conf import APP as app  # noqa: E402

app.conf.beat_schedule = {
    "aggregate-charges": {
        "task": "am.apps.account.tasks.aggregate_charges",
        "schedule": timedelta(hours=1),
        "options": {"queue": "beat_tasks"},
    },
}
app.conf.beat_schedule_filename = "/home/am_user/data/celery/celerybeat-schedule"

__all__ = ["app"]
