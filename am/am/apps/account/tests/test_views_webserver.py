"""Test the web server views (``am.apps.account.views.webserver``)."""

from http import HTTPStatus

from django.test import Client, TestCase
from django.urls import reverse


class TestViewsWebserver(TestCase):
    """Test the favicon, robots.txt, health check and readiness routes of the console."""

    def setUp(self):
        """An anonymous client."""
        self.client = Client()

    def test_favicon(self):
        """The favicon is served as an icon."""
        response = self.client.get(reverse("root_favicon"))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response["Content-Type"], "image/x-icon")
        self.assertTrue(b"".join(response.streaming_content))  # type: ignore[attr-defined]

    def test_robots_txt(self):
        """Robots.txt is served as plain text."""
        response = self.client.get(reverse("root_robots_txt"))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(response["Content-Type"].startswith("text/plain"))
        self.assertIn(b"User-agent", response.content)

    def test_healthz(self):
        """The health check answers OK."""
        response = self.client.get(reverse("root_healthz"))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.content, b"OK")

    def test_readiness(self):
        """The readiness check answers OK."""
        response = self.client.get(reverse("root_readiness"))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.content, b"OK")
