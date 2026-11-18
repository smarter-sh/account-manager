"""Test the project's url configuration, host patterns and Celery apps."""

from django.test import Client, TestCase
from django.urls import reverse

from am.common.conf import am_settings
from am.common.const import AMEnvironments
from am.hosts import host_patterns
from am.urls import api as api_urls
from am.urls import console as console_urls


class TestUrls(TestCase):
    """Test am.urls and am.hosts."""

    def test_console_home_redirects_to_admin(self):
        """The console's home page redirects to the Django admin."""
        response = Client().get(reverse("root_home"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("admin:index"))

    def test_console_url_names(self):
        """The console serves the api, the admin and swagger."""
        self.assertEqual(reverse("api:v1:tests:test_json_dict_unauthenticated"), "/api/v1/tests/unauthenticated/dict/")
        self.assertEqual(reverse("schema-swagger-ui"), "/swagger/")
        self.assertEqual(reverse("admin:index"), "/admin/")
        self.assertTrue(console_urls.urlpatterns)

    def test_api_urlconf(self):
        """The api host's urlconf includes the v1 api, auth and oauth routes."""
        routes = [str(pattern.pattern) for pattern in api_urls.urlpatterns]
        self.assertEqual(routes, ["", "auth/", "o/"])

    def test_host_patterns(self):
        """Every console and api host, local and per environment, has a host pattern."""
        names = {host.name for host in host_patterns}
        subdomain = am_settings.am_subdomain
        api = am_settings.api_subdomain
        self.assertIn(subdomain, names)
        self.assertIn(api, names)
        for environment in [AMEnvironments.ALPHA, AMEnvironments.BETA, AMEnvironments.NEXT]:
            self.assertIn(f"{environment}_{subdomain}", names)
            self.assertIn(f"{environment}_{api}", names)
        self.assertIn(f"{api}.{subdomain}.localhost", names)
        self.assertEqual(len(host_patterns), 12)


class TestCeleryApps(TestCase):
    """Test the Celery worker and beat modules."""

    def test_worker_app(self):
        """The worker module exposes the project's Celery app."""
        # pylint: disable=import-outside-toplevel
        from am.lib.celery_conf import APP
        from am.workers.celery import app

        self.assertIs(app, APP)

    def test_beat_schedule(self):
        """Celery Beat aggregates charges every hour on the beat_tasks queue."""
        # pylint: disable=import-outside-toplevel
        from am.workers.celerybeat import app

        schedule = app.conf.beat_schedule["aggregate-charges"]
        self.assertEqual(schedule["task"], "am.apps.account.tasks.aggregate_charges")
        self.assertEqual(schedule["schedule"].total_seconds(), 3600)
        self.assertEqual(schedule["options"], {"queue": "beat_tasks"})
