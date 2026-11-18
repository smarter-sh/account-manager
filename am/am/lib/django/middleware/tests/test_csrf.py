"""Test the SmarterCsrfViewMiddleware class."""

from http import HTTPStatus
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.test import RequestFactory, TestCase, override_settings

from am.lib.django.middleware.csrf import SmarterCsrfViewMiddleware


def view(request):
    """A view without csrf_exempt."""
    return HttpResponse("OK")


@override_settings(ALLOWED_HOSTS=["*"], CSRF_USE_SESSIONS=False)
class TestSmarterCsrfViewMiddleware(TestCase):
    """Test the SmarterCsrfViewMiddleware class."""

    def setUp(self):
        self.middleware = SmarterCsrfViewMiddleware(MagicMock(return_value=HttpResponse("OK")))
        self.factory = RequestFactory()

    def test_process_request_reads_csrf_cookie(self):
        request = self.factory.get("/accounts/")
        request.COOKIES["csrftoken"] = "a" * 32
        self.assertIsNone(self.middleware.process_request(request))
        self.assertEqual(request.META["CSRF_COOKIE"], "a" * 32)

    def test_process_request_does_not_change_user(self):
        """An unauthenticated request stays anonymous: the middleware never substitutes a user."""
        request = self.factory.get("/accounts/")
        request.user = AnonymousUser()
        self.middleware.process_request(request)
        self.assertIsInstance(request.user, AnonymousUser)

    @patch.object(CsrfViewMiddleware, "process_request")
    def test_process_request_skips_health_checks(self, mock_super_process_request):
        request = self.factory.get("/healthz/")
        self.assertIsNone(self.middleware.process_request(request))
        mock_super_process_request.assert_not_called()

    @patch.object(CsrfViewMiddleware, "process_request")
    def test_process_request_skips_internal_ip_hosts(self, mock_super_process_request):
        request = self.factory.get("/accounts/", HTTP_HOST="192.168.1.10")
        self.assertIsNone(self.middleware.process_request(request))
        mock_super_process_request.assert_not_called()

    def test_process_request_empty_host_is_a_server_error(self):
        request = self.factory.get("/accounts/")
        with patch.object(request, "get_host", return_value=""):
            response = self.middleware.process_request(request)
        assert response is not None
        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)

    @patch("am.lib.django.middleware.csrf.am_settings")
    def test_process_view_local_environment_skips_check(self, mock_am_settings):
        mock_am_settings.environment = "local"
        request = self.factory.post("/accounts/")
        self.assertIsNone(self.middleware.process_view(request, view, (), {}))

    @patch("am.lib.django.middleware.csrf.am_settings")
    def test_process_view_rejects_post_without_token(self, mock_am_settings):
        mock_am_settings.environment = "prod"
        request = self.factory.post("/accounts/")
        # an attribute that the test client sets, and django-stubs doesn't declare
        setattr(request, "_dont_enforce_csrf_checks", False)
        self.middleware.process_request(request)
        response = self.middleware.process_view(request, view, (), {})
        assert response is not None
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    @patch("am.lib.django.middleware.csrf.am_settings")
    def test_process_view_accepts_safe_method(self, mock_am_settings):
        mock_am_settings.environment = "prod"
        request = self.factory.get("/accounts/")
        self.middleware.process_request(request)
        self.assertIsNone(self.middleware.process_view(request, view, (), {}))
