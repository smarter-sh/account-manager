# pylint: disable=wrong-import-position
"""Test User."""

from celery import Celery

# python stuff
from account.lib.unittest.base_classes import AMTestBase

# our stuff
from account.workers.celery import app


class TestCelery(AMTestBase):
    """Test Account model"""

    def test_celery_is_running(self):
        """Test that Celery is running."""
        try:
            replies = app.control.ping()
            self.assertTrue(replies, "Celery is not running")
        except OSError as e:
            self.fail(f"Celery is not running: {e}")

    def test_celery_configuration(self):
        """Test that the Celery configuration is correct."""
        APP = Celery("account")
        APP.conf.task_protocol = 1
        APP.config_from_object("django.conf:settings", namespace="CELERY")
        APP.autodiscover_tasks()

        with APP.connection() as conn:
            conn.ensure_connection(max_retries=3)
