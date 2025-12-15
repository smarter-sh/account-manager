"""Test the SmarterCsrfViewMiddleware class."""

# pylint: disable=W0718,W0212

from unittest.mock import MagicMock, patch

from account.lib.django.middleware.csrf import SmarterCsrfViewMiddleware
from account.lib.unittest.base_classes import AMTestBase


class TestSmarterCsrfViewMiddleware(AMTestBase):
    """Test the SmarterCsrfViewMiddleware class."""

    def setUp(self):
        super().setUp()
        self.get_response = MagicMock()
        self.middleware = SmarterCsrfViewMiddleware(self.get_response)
        self.request = MagicMock()
        self.request.COOKIES = {}
        self.request.META = {}

    @patch("account.lib.django.middleware.csrf.settings")
    @patch("account.lib.django.middleware.csrf.waffle")
    def test_CSRF_TRUSTED_ORIGINS_without_chatbot(self, mock_waffle, mock_settings):
        mock_settings.CSRF_TRUSTED_ORIGINS = ["http://example.3141-5926-5359.api.localhost:8000/"]
        mock_waffle.switch_is_active.return_value = False
        self.middleware.request = self.request
        origins = self.middleware.CSRF_TRUSTED_ORIGINS
        self.assertEqual(origins, ["http://example.3141-5926-5359.api.localhost:8000/"])

    @patch("account.lib.django.middleware.csrf.settings")
    def test_csrf_trusted_origins_hosts(self, mock_settings):
        mock_settings.CSRF_TRUSTED_ORIGINS = ["https://foo.com", "https://*.bar.com"]
        self.middleware.request = self.request
        hosts = self.middleware.csrf_trusted_origins_hosts
        self.assertIn("foo.com", hosts)
        self.assertIn(".bar.com", hosts)

    @patch("account.lib.django.middleware.csrf.settings")
    def test_allowed_origins_exact(self, mock_settings):
        mock_settings.CSRF_TRUSTED_ORIGINS = ["https://foo.com", "https://*.bar.com"]
        self.middleware.request = self.request
        allowed = self.middleware.allowed_origins_exact
        self.assertIn("https://foo.com", allowed)
        self.assertNotIn("https://*.bar.com", allowed)

    @patch("account.lib.django.middleware.csrf.settings")
    def test_allowed_origin_subdomains(self, mock_settings):
        mock_settings.CSRF_TRUSTED_ORIGINS = ["https://foo.com", "https://*.bar.com"]
        self.middleware.request = self.request
        allowed = self.middleware.allowed_origin_subdomains
        self.assertIn("https", allowed)
        self.assertIn(".bar.com", allowed["https"])

    @patch("account.lib.django.middleware.csrf.waffle")
    def test_process_request_with_chatbot(self, mock_waffle):
        self.request.build_absolute_uri.return_value = "https://example.com/"
        # Set up a mock user with a valid id
        mock_user = MagicMock()
        mock_user.id = 1
        self.request.user = mock_user
        self.middleware.request = self.request
        result = self.middleware.process_request(self.request)
        self.assertIsNone(result)

    @patch("account.lib.django.middleware.csrf.account_settings")
    @patch("account.lib.django.middleware.csrf.waffle")
    def test_process_view_local_env(self, mock_waffle, mock_smarter_settings):
        mock_smarter_settings.environment = "local"
        mock_waffle.switch_is_active.return_value = False
        self.middleware.request = self.request
        result = self.middleware.process_view(self.request, MagicMock(), [], {})
        self.assertIsNone(result)
