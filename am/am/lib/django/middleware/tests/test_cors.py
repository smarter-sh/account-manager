"""Test the SmarterCorsMiddleware class."""

from http import HTTPStatus
from typing import cast
from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from am.lib.django.middleware.cors import SmarterCorsMiddleware

ALLOWED_ORIGIN = "https://allowed.example.com"


@override_settings(
    CORS_ALLOWED_ORIGINS=[ALLOWED_ORIGIN],
    CORS_ALLOWED_ORIGIN_REGEXES=[r"^https://\w+\.regex\.example\.com$"],
    CORS_ALLOW_ALL_ORIGINS=False,
    ALLOWED_HOSTS=["*"],
)
class TestSmarterCorsMiddleware(TestCase):
    """Test the SmarterCorsMiddleware class."""

    def setUp(self):
        self.get_response = MagicMock(return_value=HttpResponse("OK"))
        self.middleware = SmarterCorsMiddleware(self.get_response)
        self.factory = RequestFactory()

    def respond(self, request) -> HttpResponse:
        """Run the middleware, which is synchronous here, on the request."""
        return cast(HttpResponse, self.middleware(request))

    def test_allowed_origin_gets_cors_header(self):
        request = self.factory.get("/accounts/", HTTP_ORIGIN=ALLOWED_ORIGIN)
        response = self.respond(request)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response["Access-Control-Allow-Origin"], ALLOWED_ORIGIN)

    def test_regex_origin_gets_cors_header(self):
        origin = "https://foo.regex.example.com"
        response = self.respond(self.factory.get("/accounts/", HTTP_ORIGIN=origin))
        self.assertEqual(response["Access-Control-Allow-Origin"], origin)

    def test_unknown_origin_gets_no_cors_header(self):
        response = self.respond(self.factory.get("/accounts/", HTTP_ORIGIN="https://evil.example.org"))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertNotIn("Access-Control-Allow-Origin", response)

    def test_health_check_passes(self):
        response = self.respond(self.factory.get("/healthz/", HTTP_ORIGIN=ALLOWED_ORIGIN))
        self.assertEqual(response.content, b"OK")
        self.assertEqual(response["Access-Control-Allow-Origin"], ALLOWED_ORIGIN)

    def test_internal_ip_host_passes(self):
        response = self.respond(self.factory.get("/accounts/", HTTP_HOST="192.168.1.10:8000"))
        self.assertEqual(response.content, b"OK")
        self.get_response.assert_called_once()

    def test_empty_host_is_a_server_error(self):
        request = self.factory.get("/accounts/")
        with patch.object(request, "get_host", return_value=""):
            response = self.respond(request)
        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.get_response.assert_not_called()
