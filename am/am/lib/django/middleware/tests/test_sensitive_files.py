"""Test the SmarterBlockSensitiveFilesMiddleware class."""

from http import HTTPStatus
from typing import cast
from unittest.mock import MagicMock

from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from am.lib.cache import lazy_cache as cache
from am.lib.django.middleware.sensitive_files import (
    SmarterBlockSensitiveFilesMiddleware,
)

CLIENT_IP = "93.184.216.34"
"""A public ip address (example.com's), as the load balancer reports it in X-Forwarded-For."""

THROTTLE_KEY = f"sensitive_files_throttle:{CLIENT_IP}"


class TestSmarterBlockSensitiveFilesMiddleware(TestCase):
    """
    Test the SmarterBlockSensitiveFilesMiddleware class.

    The middleware counts blocked requests per client ip, so it only inspects requests whose
    client ip it can determine: a public address, which in production comes from the load
    balancer's X-Forwarded-For header. A request from a private address (RequestFactory's
    default REMOTE_ADDR is 127.0.0.1) passes through untouched.
    """

    def setUp(self):
        cache.delete(THROTTLE_KEY)
        self.addCleanup(cache.delete, THROTTLE_KEY)
        self.get_response = MagicMock(return_value=HttpResponse("OK"))
        self.middleware = SmarterBlockSensitiveFilesMiddleware(self.get_response)
        self.factory = RequestFactory()

    def get(self, path: str, **extra) -> HttpResponse:
        """Send a GET request from the public client ip through the middleware, which is synchronous here."""
        request = self.factory.get(path, HTTP_X_FORWARDED_FOR=CLIENT_IP, **extra)
        return cast(HttpResponse, self.middleware(request))

    def assertBlocked(self, response):
        """Assert that the middleware refused the request."""
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("blocked by Smarter", response.content.decode())

    def assertPassed(self, response):
        """Assert that the middleware handed the request to the next handler."""
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.content, b"OK")

    def test_sensitive_file_blocked(self):
        for sensitive in [
            "/.env",
            "/config.php",
            "/db.sqlite3",
            "/backup.sql",
            "/.git/config",
            "/credentials.json",
            "/secrets.json",
            "/id_rsa",
            "/package-lock.json",
            "/Gemfile.lock",
            "/requirements.txt",
            "/ecp/Current/exporttool/microsoft.exchange.ediscovery.exporttool.application",
        ]:
            with self.subTest(sensitive=sensitive):
                cache.delete(THROTTLE_KEY)
                self.assertBlocked(self.get(sensitive))
        self.get_response.assert_not_called()

    def test_sensitive_file_blocked_case_insensitive(self):
        self.assertBlocked(self.get("/ID_RSA"))

    def test_sensitive_file_wildcards(self):
        """Glob patterns match the last path segment."""
        for path in ["/foo/bar/.env.local", "/foo/bar/secret.pem", "/foo/bar/backup.bak", "/logs/app.log"]:
            with self.subTest(path=path):
                cache.delete(THROTTLE_KEY)
                self.assertBlocked(self.get(path))

    def test_sensitive_file_in_subdirectory(self):
        self.assertBlocked(self.get("/foo/.git/config"))
        cache.delete(THROTTLE_KEY)
        self.assertBlocked(self.get("/backup/db.sqlite3"))

    def test_query_string_is_ignored(self):
        """The middleware inspects the path, not the query string."""
        self.assertBlocked(self.get("/.env", data={"foo": "bar"}))
        cache.delete(THROTTLE_KEY)
        self.assertPassed(self.get("/accounts/", data={"file": ".env"}))

    def test_non_sensitive_path_allowed(self):
        self.assertPassed(self.get("/some/normal/path/"))
        self.get_response.assert_called_once()

    def test_amnesty_patterns_allowed(self):
        """Paths matching settings.ACCOUNT_SENSITIVE_FILES_AMNESTY_PATTERNS pass even if they look sensitive."""
        for amnesty in [
            "/api/v1/backup/",
            "/api/v1/.env",
            "/admin/database/",
            "/.well-known/acme-challenge/db.token",
        ]:
            with self.subTest(amnesty=amnesty):
                self.assertPassed(self.get(amnesty))
        self.assertIsNone(cache.get(THROTTLE_KEY))

    def test_amnesty_pattern_requires_exact_shape(self):
        """A path that only resembles an amnesty pattern is inspected like any other."""
        self.assertBlocked(self.get("/apiary/.env"))
        cache.delete(THROTTLE_KEY)
        self.assertBlocked(self.get("/administrator/backup.sql"))

    def test_amnesty_urls_allowed(self):
        """Health checks and the like are never inspected."""
        self.assertPassed(self.get("/healthz/"))
        self.assertPassed(self.get("/robots.txt"))

    def test_request_without_client_ip_passes(self):
        """Without a public client ip there is nothing to throttle on, so the request passes."""
        request = self.factory.get("/.env")
        self.assertPassed(self.middleware(request))

    def test_blocked_requests_are_counted(self):
        self.get("/.env")
        self.assertEqual(cache.get(THROTTLE_KEY), 1)
        self.get("/id_rsa")
        self.assertEqual(cache.get(THROTTLE_KEY), 2)

    def test_throttled_client_is_blocked(self):
        """A client over the throttle limit is refused, even for an ordinary path."""
        cache.set(THROTTLE_KEY, SmarterBlockSensitiveFilesMiddleware.THROTTLE_LIMIT, timeout=60)
        response = self.get("/some/normal/path/")
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("too many suspicious requests", response.content.decode())
        self.get_response.assert_not_called()
