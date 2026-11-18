"""Test AMAuthToken, AMAuthTokenManager class."""

from datetime import datetime, timedelta
from logging import getLogger
from unittest.mock import patch

from django.utils import timezone

from am.apps.account.tests.factories import (
    admin_user_factory,
    factory_account_teardown,
)
from am.common.exceptions import AMBusinessRuleViolation
from am.lib.unittest.base_classes import AMTestBase

from ..models import AMAuthToken

logger = getLogger(__name__)


class TestAMAuthTokenModels(AMTestBase):
    """Test the AMAuthToken class."""

    def setUp(self):
        super().setUp()
        self.admin_user, self.account, self.user_profile = admin_user_factory()
        self.auth_token, self.token_key = AMAuthToken.objects.create(
            user=self.admin_user,
            name=self.admin_user.username,
            description=self.admin_user.username,
        )

    def tearDown(self) -> None:
        try:
            self.auth_token.delete()
        except AMAuthToken.DoesNotExist:
            pass
        factory_account_teardown(user=self.admin_user, account=self.account, user_profile=self.user_profile)
        super().tearDown()

    def test_save_only_staff(self):
        self.auth_token.user.is_staff = False
        with self.assertRaises(AMBusinessRuleViolation):
            self.auth_token.save()

    def test_save_sets_created(self):
        self.auth_token.user.is_staff = True
        # deliberately None: save() sets it
        self.auth_token.created = None  # pyright: ignore[reportAttributeAccessIssue]
        with patch("am.lib.drf.models.timezone") as mock_tz:
            now = datetime(2024, 1, 1)
            mock_tz.now.return_value = now
            with patch("am.lib.drf.models.AuthToken.save") as mock_super_save:
                self.auth_token.save()
                self.assertEqual(self.auth_token.created, now)
                mock_super_save.assert_called_once()

    def test_create_returns_record_and_token(self):
        """The manager returns the saved record and the clear-text token, which only its digest is stored for."""
        self.assertIsNotNone(self.auth_token.pk)
        self.assertTrue(self.auth_token.is_active)
        self.assertIsNone(self.auth_token.expiry)
        self.assertTrue(self.token_key.startswith(self.auth_token.token_key))
        self.assertNotIn(self.token_key, self.auth_token.digest)

    def test_create_logs_key_id_not_token(self):
        with patch("am.lib.drf.models.logger") as mock_logger:
            auth_token, token = AMAuthToken.objects.create(user=self.admin_user, name="logged")
        self.addCleanup(auth_token.delete)
        logged = str(mock_logger.info.call_args)
        self.assertIn(str(auth_token.key_id), logged)
        self.assertNotIn(auth_token.token_key, logged)
        self.assertNotIn(token, logged)

    def test_create_with_expiry_and_prefix(self):
        before = timezone.now()
        auth_token, token = AMAuthToken.objects.create(
            user=self.admin_user, name="expiring", expiry=timedelta(days=1), prefix="am_"
        )
        self.addCleanup(auth_token.delete)
        self.assertTrue(token.startswith("am_"))
        self.assertGreater(auth_token.expiry, before + timedelta(hours=23))

    def test_identifier_masks_digest(self):
        self.assertEqual(self.auth_token.identifier, "******" + self.auth_token.digest[-4:])

    def test_str_returns_identifier(self):
        self.auth_token.digest = "digestvalue"
        logger.info(str(self.auth_token))
        self.assertTrue(str(self.auth_token).endswith("******alue"))
