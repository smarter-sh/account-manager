"""Test am.apps.account.utils."""

from unittest import mock

from django.contrib.auth.models import AnonymousUser

from am.apps.account.models import (
    Account,
    AccountContact,
    User,
    UserProfile,
)
from am.apps.account.tests.mixins import AccountTestCase
from am.apps.account.utils import (
    _get_account_for_user,
    _get_cached_user_profile,
    account_number_from_url,
    cache_invalidate,
    get_cached_account,
    get_cached_account_for_user,
    get_cached_admin_user_for_account,
    get_cached_default_account,
    get_cached_smarter_admin_user_profile,
    get_cached_user_for_user_id,
    get_cached_user_profile,
)
from am.common.conf import am_settings
from am.common.const import ACCOUNT_ACCOUNT_NUMBER
from am.common.exceptions import AMConfigurationError, AMValueError


def make_user(username: str, **kwargs) -> User:
    """Create a user with an example.com address."""
    return User.objects.create_user(username=username, email=f"{username}@example.com", password="12345", **kwargs)


class TestUtils(AccountTestCase):
    """Test the cached account, user and subscription lookups."""

    @classmethod
    def setUpTestData(cls):
        cls.account = Account.objects.create(company_name="Utils Test Co")
        cls.user = make_user("utils_user")
        cls.user_profile = UserProfile.objects.create(user=cls.user, account=cls.account, is_test=True)

    # -------------------------------------------------------------------------
    # get_cached_account(), get_cached_default_account()
    # -------------------------------------------------------------------------
    def test_get_cached_account(self):
        """An account is found by id or by number; a missing one is None."""
        self.assertEqual(get_cached_account(account_id=self.account.pk), self.account)
        self.assertEqual(get_cached_account(account_number=self.account.account_number), self.account)
        self.assertIsNone(get_cached_account(account_id=self.account.pk, invalidate=True))
        self.assertIsNone(get_cached_account(account_number=self.account.account_number, invalidate=True))
        self.assertIsNone(get_cached_account(account_id=999999999))
        self.assertIsNone(get_cached_account(account_number="0000-0000-0001"))
        self.assertIsNone(get_cached_account())

    def test_get_cached_account_is_cached(self):
        """A second lookup is served from the cache, without a query."""
        get_cached_account(account_id=self.account.pk)
        with self.assertNumQueries(0):
            self.assertEqual(get_cached_account(account_id=self.account.pk), self.account)

    def test_get_cached_default_account(self):
        """The account flagged is_default_account is returned."""
        Account.objects.filter(is_default_account=True).update(is_default_account=False)
        Account.objects.filter(pk=self.account.pk).update(is_default_account=True)
        self.assertEqual(get_cached_default_account(), self.account)
        self.assertIsNone(get_cached_default_account(invalidate=True))

    # -------------------------------------------------------------------------
    # get_cached_account_for_user()
    # -------------------------------------------------------------------------
    def test_account_for_user(self):
        """A user's account is found through their UserProfile."""
        self.assertEqual(get_cached_account_for_user(self.user), self.account)
        self.assertIsNone(get_cached_account_for_user(self.user, invalidate=True))

    def test_account_for_user_prefers_default_account(self):
        """A user with several accounts gets the default one, whatever the logging switches say."""
        default_account = Account.objects.create(company_name="Utils Default Co", is_default_account=True)
        UserProfile.objects.create(user=self.user, account=default_account, is_test=True)
        self.assertEqual(get_cached_account_for_user(self.user), default_account)

    def test_account_for_user_edge_cases(self):
        """Anonymous, missing, unsaved and profile-less users have no account."""
        self.assertIsNone(get_cached_account_for_user(AnonymousUser()))
        self.assertIsNone(get_cached_account_for_user(None))
        self.assertIsNone(_get_account_for_user(User(username="unsaved")))
        self.assertIsNone(get_cached_account_for_user(make_user("utils_noprofile")))

    # -------------------------------------------------------------------------
    # get_cached_user_profile()
    # -------------------------------------------------------------------------
    def test_get_cached_user_profile(self):
        """The profile is found with or without the account."""
        self.assertEqual(get_cached_user_profile(self.user, account=self.account), self.user_profile)
        self.assertEqual(get_cached_user_profile(self.user), self.user_profile)
        self.assertIsNone(get_cached_user_profile(self.user, account=self.account, invalidate=True))

    def test_get_cached_user_profile_not_found(self):
        """No account, or an unresolvable user, gives no profile."""
        self.assertIsNone(get_cached_user_profile(make_user("utils_noaccount")))
        self.assertIsNone(get_cached_user_profile(mock.MagicMock(), account=self.account))
        self.assertIsNone(_get_cached_user_profile(None, self.account))  # type: ignore[arg-type]
        self.assertIsNone(_get_cached_user_profile(self.user, None))

    def test_get_cached_user_profile_wrong_account(self):
        """A user who doesn't belong to the account raises UserProfile.DoesNotExist."""
        other_account = Account.objects.create(company_name="Utils Other Co")
        with self.assertRaises(UserProfile.DoesNotExist):
            get_cached_user_profile(self.user, account=other_account)

    # -------------------------------------------------------------------------
    # get_cached_user_for_user_id()
    # -------------------------------------------------------------------------
    def test_get_cached_user_for_user_id(self):
        """A user is found by id; a missing one is None."""
        self.assertEqual(get_cached_user_for_user_id(self.user.pk), self.user)
        self.assertIsNone(get_cached_user_for_user_id(self.user.pk, invalidate=True))
        self.assertIsNone(get_cached_user_for_user_id(999999999))

    # -------------------------------------------------------------------------
    # get_cached_admin_user_for_account()
    # -------------------------------------------------------------------------
    def test_admin_user_existing_staff(self):
        """An existing staff user of the account is its admin."""
        staff = make_user("utils_staff", is_staff=True)
        UserProfile.objects.create(user=staff, account=self.account, is_test=True)
        self.assertEqual(get_cached_admin_user_for_account(self.account), staff)
        self.assertIsNone(get_cached_admin_user_for_account(self.account, invalidate=True))

    def test_admin_user_created_for_test_account(self):
        """
        An account without staff gets a new staff admin, named after the account number.

        The account's profiles are all test profiles, so the admin's profile is too, and so
        is its account contact. Nobody is emailed.
        """
        admin = get_cached_admin_user_for_account(self.account)
        self.assertEqual(admin.username, self.account.account_number)
        self.assertTrue(admin.is_staff)
        self.assertEqual(admin.email, f"{self.account.account_number}@{am_settings.root_domain}")
        profile = UserProfile.objects.get(user=admin, account=self.account)
        self.assertTrue(profile.is_test)
        self.assertTrue(AccountContact.objects.get(account=self.account, email=admin.email).is_test)
        self.send_email.assert_not_called()

    def test_admin_user_created_for_real_account(self):
        """An account with no profiles, or a non-test profile, gets a non-test admin profile."""
        account = Account.objects.create(company_name="Utils Real Co")
        admin = get_cached_admin_user_for_account(account)
        self.assertFalse(UserProfile.objects.get(user=admin, account=account).is_test)

    def test_admin_user_errors(self):
        """No account, an account without a number, or an unsaved account, raise."""
        with self.assertRaises(AMValueError):
            get_cached_admin_user_for_account(None)  # type: ignore[arg-type]
        with self.assertRaises(AMValueError):
            get_cached_admin_user_for_account(Account(company_name="x", account_number=None))
        with self.assertRaises(AMConfigurationError):
            get_cached_admin_user_for_account(Account(company_name="x", account_number="0000-0000-0002"))

    # -------------------------------------------------------------------------
    # get_cached_smarter_admin_user_profile()
    # -------------------------------------------------------------------------
    def smarter_account(self) -> Account:
        """Return the platform's own account, creating it if necessary."""
        account, _ = Account.objects.get_or_create(
            account_number=ACCOUNT_ACCOUNT_NUMBER, defaults={"company_name": "Smarter"}
        )
        return account

    def test_smarter_admin_user_profile_missing_account(self):
        """Without the platform's account, it raises."""
        with mock.patch("am.apps.account.utils.get_cached_account", return_value=None):
            with self.assertRaises(AMConfigurationError):
                get_cached_smarter_admin_user_profile()

    def test_smarter_admin_user_profile_superuser(self):
        """A superuser profile of the platform's account is preferred."""
        account = self.smarter_account()
        UserProfile.objects.filter(account=account).delete()
        superuser = make_user("utils_super", is_staff=True, is_superuser=True)
        profile = UserProfile.objects.create(user=superuser, account=account, is_test=True)
        self.assertEqual(get_cached_smarter_admin_user_profile(), profile)
        self.assertIsNone(get_cached_smarter_admin_user_profile(invalidate=True))

    def test_smarter_admin_user_profile_staff(self):
        """Without a superuser, a staff profile is returned, whatever the logging switches say."""
        account = self.smarter_account()
        UserProfile.objects.filter(account=account).delete()
        staff = make_user("utils_smarter_staff", is_staff=True)
        profile = UserProfile.objects.create(user=staff, account=account, is_test=True)
        self.assertEqual(get_cached_smarter_admin_user_profile(), profile)

    def test_smarter_admin_user_profile_none(self):
        """Without a superuser or staff profile, it raises."""
        account = self.smarter_account()
        UserProfile.objects.filter(account=account).delete()
        UserProfile.objects.create(user=make_user("utils_smarter_mortal"), account=account, is_test=True)
        with self.assertRaises(AMConfigurationError):
            get_cached_smarter_admin_user_profile()

    # -------------------------------------------------------------------------
    # account_number_from_url()
    # -------------------------------------------------------------------------
    def test_account_number_from_url(self):
        """The account number is extracted from a url, if it has one."""
        url = "https://hr.3141-5926-5359.alpha.api.example.com/"
        self.assertEqual(account_number_from_url(url), "3141-5926-5359")
        self.assertIsNone(account_number_from_url(url, invalidate=True))
        self.assertIsNone(account_number_from_url("https://www.example.com/"))
        self.assertIsNone(account_number_from_url(""))

    # -------------------------------------------------------------------------
    # cache_invalidate()
    # -------------------------------------------------------------------------
    def test_cache_invalidate_requires_user_or_account(self):
        """Neither a user nor an account raises."""
        with self.assertRaises(AMValueError):
            cache_invalidate()

    def test_cache_invalidate_user(self):
        """Invalidating a user drops the cached account and user entries."""
        get_cached_account(account_id=self.account.pk)
        get_cached_account_for_user(self.user)
        get_cached_user_for_user_id(self.user.pk)
        cache_invalidate(user=self.user)
        with self.assertNumQueries(1):
            get_cached_account(account_id=self.account.pk)
        with self.assertNumQueries(1):
            get_cached_user_for_user_id(self.user.pk)

    def test_cache_invalidate_account(self):
        """Invalidating an account drops the cached account."""
        get_cached_account(account_id=self.account.pk)
        cache_invalidate(account=self.account)
        with self.assertNumQueries(1):
            get_cached_account(account_id=self.account.pk)

    def test_cache_invalidate_user_without_profile(self):
        """A user without a profile is a no-op, e.g. during platform bootstrap."""
        user = make_user("utils_bootstrap")
        with mock.patch("am.apps.account.utils.get_cached_account") as get_account:
            cache_invalidate(user=user)
        get_account.assert_not_called()
