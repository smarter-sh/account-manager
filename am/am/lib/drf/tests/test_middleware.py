"""Test AMTokenAuthenticationMiddleware."""

from datetime import timedelta
from http import HTTPStatus
from typing import cast
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone

from am.apps.account.tests.mixins import TestAccountMixin
from am.lib import json
from am.lib.drf.middleware import AMTokenAuthenticationMiddleware
from am.lib.drf.models import AMAuthToken
from am.lib.drf.signals import (
    smarter_token_authentication_failure,
    smarter_token_authentication_success,
)


class TestAMTokenAuthenticationMiddleware(TestAccountMixin):
    """Test AMTokenAuthenticationMiddleware."""

    def setUp(self) -> None:
        super().setUp()
        self.token_record, self.token_key = AMAuthToken.objects.create(
            name=self.name,
            user=self.admin_user,
            description="TestAMTokenAuthenticationMiddleware() test description",
        )  # type: ignore
        self.addCleanup(self.token_record.delete)
        self.get_response = MagicMock(return_value=HttpResponse(status=HTTPStatus.OK))
        self.middleware = AMTokenAuthenticationMiddleware(self.get_response)
        self.factory = RequestFactory()

    def api_request(self, path="/api/v1/accounts/", **headers):
        """Return a request with a session and an anonymous user, as the earlier middleware leave it."""
        request = self.factory.get(path, **headers)
        SessionMiddleware(lambda r: HttpResponse()).process_request(request)
        request.user = AnonymousUser()
        return request

    def respond(self, request) -> HttpResponse:
        """Run the middleware, which is synchronous here, on the request."""
        return cast(HttpResponse, self.middleware(request))

    def receive(self, signal):
        """Connect a mock receiver to a signal for the duration of the test."""
        receiver = MagicMock()
        signal.connect(receiver)
        self.addCleanup(signal.disconnect, receiver)
        return receiver

    def test_valid_token_authenticates_and_logs_in(self):
        on_success = self.receive(smarter_token_authentication_success)
        request = self.api_request(HTTP_AUTHORIZATION=f"Token {self.token_key}")
        response = self.respond(request)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.get_response.assert_called_once_with(request)
        self.assertEqual(request.user, self.admin_user)
        self.assertEqual(str(request.session["_auth_user_id"]), str(self.admin_user.pk))
        on_success.assert_called_once()
        self.assertNotIn(self.token_key, str(on_success.call_args))

    def test_invalid_token_is_401_json(self):
        on_failure = self.receive(smarter_token_authentication_failure)
        request = self.api_request(HTTP_AUTHORIZATION="Token " + "0" * 64)
        response = self.respond(request)
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertEqual(json.loads(response.content), {"detail": "Authentication failed."})
        self.get_response.assert_not_called()
        on_failure.assert_called_once()

    def test_inactive_token_is_401(self):
        self.token_record.is_active = False
        self.token_record.save()
        response = self.respond(self.api_request(HTTP_AUTHORIZATION=f"Token {self.token_key}"))
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_authenticate_returning_none_is_401(self):
        with patch("am.lib.drf.middleware.AMTokenAuthentication") as mock_auth:
            mock_auth.return_value.authenticate.return_value = None
            response = self.respond(self.api_request(HTTP_AUTHORIZATION=f"Token {self.token_key}"))
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_non_api_url_is_skipped(self):
        request = self.api_request(path="/accounts/", HTTP_AUTHORIZATION="Token " + "0" * 64)
        self.assertEqual(self.respond(request).status_code, HTTPStatus.OK)
        self.assertIsInstance(request.user, AnonymousUser)

    def test_no_authorization_header_is_skipped(self):
        request = self.api_request()
        self.assertEqual(self.respond(request).status_code, HTTPStatus.OK)
        self.assertIsInstance(request.user, AnonymousUser)

    def test_other_auth_scheme_is_skipped(self):
        request = self.api_request(HTTP_AUTHORIZATION="Bearer some.jwt.token")
        self.assertEqual(self.respond(request).status_code, HTTPStatus.OK)
        self.assertIsInstance(request.user, AnonymousUser)

    def test_already_authenticated_request_is_skipped(self):
        request = self.api_request(HTTP_AUTHORIZATION="Token " + "0" * 64)
        request.auth = "authenticated elsewhere"
        self.assertEqual(self.respond(request).status_code, HTTPStatus.OK)

    @patch("am.lib.drf.middleware.knox_settings")
    def test_get_token_with_bytes_prefix(self, mock_knox_settings):
        mock_knox_settings.AUTH_HEADER_PREFIX = b"Token"
        request = self.factory.get("/", HTTP_AUTHORIZATION="token abc")
        self.assertEqual(AMTokenAuthenticationMiddleware.get_token(request), "abc")
        request = self.factory.get("/", HTTP_AUTHORIZATION="Token")
        self.assertIsNone(AMTokenAuthenticationMiddleware.get_token(request))

    def test_warn_if_expired(self):
        self.assertFalse(self.middleware.warn_if_expired(self.token_record, self.admin_user))
        self.token_record.created = timezone.now() - timedelta(days=10000)
        with patch("am.lib.drf.middleware.logger") as mock_logger:
            self.assertTrue(self.middleware.warn_if_expired(self.token_record, self.admin_user))
        mock_logger.warning.assert_called_once()
