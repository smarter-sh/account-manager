"""Test the SmarterBlockExcessive404Middleware class."""

from http import HTTPStatus
from unittest.mock import MagicMock

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse, HttpResponseNotFound
from django.test import RequestFactory, TestCase

from am.lib.cache import lazy_cache as cache
from am.lib.django.middleware.excessive_404 import (
    SmarterBlockExcessive404Middleware,
)

CLIENT_IP = "93.184.216.34"
"""A public ip address (example.com's), as the load balancer reports it in X-Forwarded-For."""

THROTTLE_KEY = f"excessive_404_throttle:{CLIENT_IP}"


class TestSmarterBlockExcessive404Middleware(TestCase):
    """Test the SmarterBlockExcessive404Middleware class."""

    def setUp(self):
        cache.delete(THROTTLE_KEY)
        self.addCleanup(cache.delete, THROTTLE_KEY)
        self.middleware = SmarterBlockExcessive404Middleware(MagicMock())
        self.factory = RequestFactory()

    def request(self, user=None, **extra):
        """Return an anonymous (or the given user's) GET request from the public client ip."""
        request = self.factory.get("/missing/", HTTP_X_FORWARDED_FOR=CLIENT_IP, **extra)
        request.user = user or AnonymousUser()
        return request

    def test_non_404_response_is_untouched(self):
        response = HttpResponse("OK")
        self.assertIs(self.middleware.process_response(self.request(), response), response)
        self.assertIsNone(cache.get(THROTTLE_KEY))

    def test_404_is_counted(self):
        response = HttpResponseNotFound()
        self.assertIs(self.middleware.process_response(self.request(), response), response)
        self.assertEqual(cache.get(THROTTLE_KEY), 1)
        self.middleware.process_response(self.request(), HttpResponseNotFound())
        self.assertEqual(cache.get(THROTTLE_KEY), 2)

    def test_client_over_limit_is_blocked(self):
        cache.set(THROTTLE_KEY, SmarterBlockExcessive404Middleware.THROTTLE_LIMIT, timeout=60)
        response = self.middleware.process_response(self.request(), HttpResponseNotFound())
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("too many invalid requests", response.content.decode())

    def test_authenticated_user_is_exempt(self):
        user = MagicMock(is_authenticated=True)
        response = HttpResponseNotFound()
        self.assertIs(self.middleware.process_response(self.request(user=user), response), response)
        self.assertIsNone(cache.get(THROTTLE_KEY))

    def test_request_without_client_ip_is_not_counted(self):
        request = self.factory.get("/missing/")
        request.user = AnonymousUser()
        response = HttpResponseNotFound()
        self.assertIs(self.middleware.process_response(request, response), response)
