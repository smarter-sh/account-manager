"""Test am.common.classes."""

import logging
from unittest.mock import patch

from django.core.exceptions import AppRegistryNotReady
from django.http import HttpResponse
from django.test import RequestFactory

from am.common import classes
from am.common.classes import (
    AMHelperMixin,
    AMMiddlewareMixin,
    Singleton,
    mixin_logging_is_active,
    should_log,
)
from am.lib.unittest.base_classes import AMTestBase


class OnlyOne(metaclass=Singleton):
    """A singleton for the test."""

    def __init__(self, value=None):
        self.value = value


class ExampleMiddleware(AMMiddlewareMixin):
    """A middleware for the test."""


class TestClasses(AMTestBase):
    """Test the Singleton metaclass and the helper mixins."""

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.middleware = ExampleMiddleware(get_response=lambda request: HttpResponse())

    def test_singleton(self):
        """A Singleton class is instantiated once."""
        first = OnlyOne(value=1)
        self.assertIs(OnlyOne(value=2), first)
        self.assertEqual(OnlyOne().value, 1)

    def test_mixin_logging_is_active(self):
        """Mixin_logging_is_active() follows the waffle switch, and is False before apps are ready."""
        with patch("am.lib.django.waffle.switch_is_active", return_value=True):
            self.assertTrue(mixin_logging_is_active())
        with patch("am.lib.django.waffle.switch_is_active", side_effect=AppRegistryNotReady()):
            self.assertFalse(mixin_logging_is_active())

    def test_should_log(self):
        """Should_log() needs the switch on and a level at or above the log level."""
        with patch.object(classes, "mixin_logging_is_active", return_value=True):
            self.assertTrue(should_log(logging.CRITICAL))
        with patch.object(classes, "mixin_logging_is_active", return_value=False):
            self.assertFalse(should_log(logging.CRITICAL))

    def test_helper_mixin(self):
        """AMHelperMixin's names, readiness, amnesty urls and json."""
        helper = AMHelperMixin()
        self.assertEqual(helper.unformatted_class_name, "AMHelperMixin")
        self.assertIn("AMHelperMixin", helper.formatted_class_name)
        self.assertNotEqual(helper.formatted_class_name, "AMHelperMixin")
        self.assertTrue(helper.ready)
        self.assertIn("healthz", helper.amnesty_urls)
        self.assertEqual(helper.to_json(), {"class_name": "AMHelperMixin"})
        request = self.factory.get("/some/path/")
        self.assertEqual(helper.smarter_build_absolute_uri(request), "http://testserver/some/path/")

    def test_get_client_ip_forwarded_for(self):
        """The first public X-Forwarded-For address is the client."""
        request = self.factory.get("/", HTTP_X_FORWARDED_FOR="93.184.216.5, 10.0.0.1")
        self.assertEqual(self.middleware.get_client_ip(request), "93.184.216.5")

    def test_get_client_ip_real_ip(self):
        """A private X-Forwarded-For falls back to X-Real-IP."""
        request = self.factory.get("/", HTTP_X_FORWARDED_FOR="10.0.0.1", HTTP_X_REAL_IP=" 93.184.216.6 ")
        self.assertEqual(self.middleware.get_client_ip(request), "93.184.216.6")

    def test_get_client_ip_cloudflare(self):
        """Cloudflare's CF-Connecting-IP is used next."""
        request = self.factory.get("/", HTTP_CF_CONNECTING_IP="93.184.216.7")
        self.assertEqual(self.middleware.get_client_ip(request), "93.184.216.7")

    def test_get_client_ip_remote_addr(self):
        """A public REMOTE_ADDR is used last."""
        request = self.factory.get("/", REMOTE_ADDR="93.184.216.8")
        self.assertEqual(self.middleware.get_client_ip(request), "93.184.216.8")

    def test_get_client_ip_none(self):
        """Without a public address there is no client ip; outside local environments that is logged."""
        request = self.factory.get("/some/path/", REMOTE_ADDR="10.0.0.2", HTTP_X_REAL_IP="not-an-ip")
        with patch.object(classes, "am_settings") as mock_settings, patch.object(classes, "logger") as mock_logger:
            mock_settings.environment_is_local = False
            self.assertIsNone(self.middleware.get_client_ip(request))
            mock_logger.warning.assert_called()
            self.assertIn("Could not determine client IP", mock_logger.warning.call_args.args[0])

            mock_logger.reset_mock()
            healthz = self.factory.get("/healthz/", REMOTE_ADDR="10.0.0.2")
            self.assertIsNone(self.middleware.get_client_ip(healthz))
            mock_logger.warning.assert_not_called()

    def test_get_client_ip_without_meta(self):
        """An object without META has no client ip."""
        self.assertIsNone(self.middleware.get_client_ip(object()))

    def test_is_private_ip(self):
        """Private, loopback, link-local and invalid addresses are private."""
        for ip in ["10.0.0.1", "192.168.1.1", "127.0.0.1", "169.254.0.1", "::1", "garbage"]:
            self.assertTrue(self.middleware._is_private_ip(ip), ip)  # pylint: disable=protected-access
        self.assertFalse(self.middleware._is_private_ip("93.184.216.1"))  # pylint: disable=protected-access
