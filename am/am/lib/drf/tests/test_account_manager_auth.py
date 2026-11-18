"""Test the AMAuthentication class."""

from rest_framework.test import APIRequestFactory

from am.apps.account.models import UserProfile
from am.apps.account.tests.mixins import TestAccountMixin
from am.lib.drf.auth.account_manager_auth import AMAuthentication


class TestAMAuthentication(TestAccountMixin):
    """Test authentication by the X-API-KEY header, which holds an account number."""

    def setUp(self):
        super().setUp()
        self.auth = AMAuthentication()
        self.factory = APIRequestFactory()

    def test_account_number_authenticates_the_account_admin(self):
        request = self.factory.get("/api/", HTTP_X_API_KEY=self.account.account_number)
        result = self.auth.authenticate(request)
        assert result is not None
        user, token = result
        self.assertEqual(token, self.account.account_number)
        self.assertTrue(user.is_staff)
        self.assertTrue(UserProfile.objects.filter(user=user, account=self.account).exists())

    def test_no_header(self):
        self.assertIsNone(self.auth.authenticate(self.factory.get("/api/")))

    def test_unknown_account_number(self):
        self.assertIsNone(self.auth.authenticate(self.factory.get("/api/", HTTP_X_API_KEY="0000-0000-0000")))
