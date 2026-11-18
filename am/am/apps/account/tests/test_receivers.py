"""Test am.apps.account.receivers."""

from datetime import date
from unittest import mock

from django.contrib.auth.signals import user_logged_in

from am.apps.account.models import (
    Account,
    Charge,
    DailyBillingRecord,
    User,
    UserProfile,
)
from am.apps.account.tests.mixins import AccountTestCase


class TestReceivers(AccountTestCase):
    """Test the account app's signal receivers."""

    @classmethod
    def setUpTestData(cls):
        Account.objects.filter(is_default_account=True).update(is_default_account=False)
        cls.default_account = Account.objects.create(company_name="Receivers Default Co", is_default_account=True)
        cls.user = User.objects.create_user(username="receivers_user", email="receivers@example.com")

    def setUp(self):
        super().setUp()
        patcher = mock.patch("am.apps.account.receivers.cache_invalidate")
        self.cache_invalidate = patcher.start()
        self.addCleanup(patcher.stop)

    def test_login_creates_missing_profile(self):
        """A user without a profile is added to the default account at login."""
        user_logged_in.send(sender=User, request=None, user=self.user)
        self.assertTrue(UserProfile.objects.filter(user=self.user, account=self.default_account).exists())

    def test_login_keeps_existing_profile(self):
        """A user with a profile is not given another one at login."""
        account = Account.objects.create(company_name="Receivers Co")
        UserProfile.objects.create(user=self.user, account=account, is_test=True)
        user_logged_in.send(sender=User, request=None, user=self.user)
        self.assertEqual(
            list(UserProfile.objects.filter(user=self.user).values_list("account", flat=True)), [account.pk]
        )

    def test_user_save_invalidates_cache_on_update_only(self):
        """Updating a user invalidates its cache; creating one does not."""
        user = User.objects.create_user(username="receivers_new", email="receivers_new@example.com")
        self.cache_invalidate.assert_not_called()
        user.first_name = "New"
        user.save()
        self.cache_invalidate.assert_called_once_with(user=user)
        user.delete()

    def test_user_profile_save_invalidates_cache_on_update_only(self):
        """Updating a profile invalidates its user's and account's cache; creating one does not."""
        profile = UserProfile.objects.create(user=self.user, account=self.default_account, is_test=True)
        self.cache_invalidate.assert_not_called()
        profile.save()
        self.cache_invalidate.assert_called_once_with(user=self.user, account=self.default_account)
        profile.delete()
        self.assertFalse(UserProfile.objects.filter(pk=profile.pk).exists())

    def test_account_save_invalidates_cache_on_update_only(self):
        """Updating an account invalidates its cache; creating one does not."""
        account = Account.objects.create(company_name="Receivers Co")
        self.cache_invalidate.assert_not_called()
        account.company_name = "Receivers Renamed Co"
        account.save()
        self.cache_invalidate.assert_called_once_with(account=account)
        account.delete()
        self.assertFalse(Account.objects.filter(company_name="Receivers Renamed Co").exists())

    def test_billing_receivers(self):
        """Saving charges and daily billing records only logs."""
        Charge.objects.create(
            account=self.default_account,
            user=self.user,
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            model="gpt-4",
            reference="ref",
        )
        DailyBillingRecord.objects.create(
            account=self.default_account,
            user=self.user,
            provider="openai",
            date=date(2026, 1, 1),
            charge_type="completion",
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
        )
        self.cache_invalidate.assert_not_called()
