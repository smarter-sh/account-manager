"""Test AMTokenAuthentication class."""

from unittest.mock import patch

from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from am.apps.account.tests.mixins import TestAccountMixin
from am.lib.drf.models import AMAuthToken
from am.lib.drf.token_authentication import AMTokenAuthentication


class TestAMTokenAuthentication(TestAccountMixin):
    """Test the AMTokenAuthentication class."""

    smarter_auth_token: AMAuthToken

    def setUp(self):
        super().setUp()
        self.auth = AMTokenAuthentication()
        self.smarter_auth_token, self.token_key = AMAuthToken.objects.create(
            name=self.name,
            user=self.admin_user,
            description="TestAMTokenAuthentication() test description",
        )  # type: ignore
        self.addCleanup(self.smarter_auth_token.delete)

    def test_authenticate_credentials_active_token(self):
        start_time = timezone.now()
        user, auth_token = self.auth.authenticate_credentials(self.token_key.encode())
        self.assertEqual(user, self.admin_user)
        self.assertEqual(auth_token, self.smarter_auth_token)
        self.smarter_auth_token.refresh_from_db()
        self.assertLessEqual(start_time, self.smarter_auth_token.last_used_at)

    def test_authenticate_via_header(self):
        request = APIRequestFactory().get("/api/", HTTP_AUTHORIZATION=f"Token {self.token_key}")
        result = self.auth.authenticate(request)
        assert result is not None
        user, auth_token = result
        self.assertEqual(user, self.admin_user)
        self.assertEqual(auth_token.pk, self.smarter_auth_token.pk)

    def test_inactive_token_is_refused_at_once(self):
        """Deactivating a key takes effect on the next request (no cached authentication)."""
        self.auth.authenticate_credentials(self.token_key.encode())
        self.smarter_auth_token.is_active = False
        self.smarter_auth_token.save()
        with self.assertRaisesRegex(AuthenticationFailed, "Api key is not activated."):
            self.auth.authenticate_credentials(self.token_key.encode())

    def test_token_must_be_bytes(self):
        with self.assertRaisesRegex(AuthenticationFailed, "Expected bytes"):
            self.auth.authenticate_credentials(self.token_key)  # type: ignore[arg-type]

    def test_unknown_token(self):
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate_credentials(b"0" * 64)

    def test_non_user_is_refused(self):
        with patch("knox.auth.TokenAuthentication.authenticate_credentials", return_value=(object(), None)):
            with self.assertRaisesRegex(AuthenticationFailed, "Invalid token"):
                self.auth.authenticate_credentials(self.token_key.encode())
