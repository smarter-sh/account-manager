# pylint: disable=wrong-import-position
"""Test AMAuthToken."""

from account.common.exceptions import AMBusinessRuleViolation
from account.lib.drf.models import AMAuthToken

from .mixins import TestAccountMixin


class TestAMAuthToken(TestAccountMixin):
    """Test AMAuthToken."""

    def test_create_auth_token(self):
        """Test create auth token."""

        token_record, token_key = AMAuthToken.objects.create(
            user=self.admin_user,
            name="testToken" + self.hash_suffix,
            description="testToken" + self.hash_suffix,
        )

        # validate that token_key is not None
        self.assertIsNotNone(token_key)
        token_record.delete()

    def test_create_auth_token_non_admin_user(self):
        """Test create auth token."""

        with self.assertRaises(AMBusinessRuleViolation):
            AMAuthToken.objects.create(
                name="testToken",
                user=self.non_admin_user,
                description="testToken" + self.hash_suffix,
            )
